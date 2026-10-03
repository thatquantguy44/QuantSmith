"""Authorize and execute evidence before composing a story (0093 REQ-002/006/012)."""
from __future__ import annotations

import fnmatch
import hashlib
import json
import math
from dataclasses import asdict, dataclass, replace

from quantsmith.nl_analytics.authorize import AccessPolicy, authorize_plan
from quantsmith.nl_analytics.execute import Result, execute
from quantsmith.nl_analytics.plan import Clarification, PlanError, validate_plan
from quantsmith.pipelines import analytics_packs
from quantsmith.pipelines.metrics_semantic_layer import GovernanceError

from .catalog import VIEWS, VisualizationError


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def result_payload(result):
    return {
        "plan": result.plan.to_canonical_dict(),
        "values": [[list(k), v] for k, v in sorted(result.values.items())],
        "series": [[p, [[list(k), v] for k, v in sorted(values.items())]] for p, values in sorted(result.series.items())],
        "row_count": result.row_count, "latest_period": result.latest_period,
        "as_of": result.as_of, "content_hash": result.content_hash,
    }


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    status: str
    reason: str
    analytics_pack_id: str = ""
    view: str = ""
    source: str = ""
    unit: str = ""
    result: Result | None = None
    definition: str = ""
    caveats: tuple[str, ...] = ()
    digest: str = ""

    def payload(self):
        return {"evidence_id": self.evidence_id, "status": self.status,
                "reason": self.reason, "analytics_pack_id": self.analytics_pack_id,
                "view": self.view, "source": self.source, "unit": self.unit,
                "definition": self.definition, "caveats": list(self.caveats),
                "result": result_payload(self.result) if self.result else None}

    def fingerprint(self):
        return hashlib.sha256(canonical(self.payload()).encode()).hexdigest()


def collect_evidence(
    evidence_id, analytics_pack_id, plan, view, *, catalog, layer, reader,
    source, as_of, access_policy=None, viewer_clearance="public", synthetic=False,
    caveats=(), max_age=2, upstream_status="answered",
):
    """Read once, enforce domain rules, then delegate arithmetic to 0008/0080.

    The injected reader must enforce source publication/vintage availability;
    Fact's period is an observation period, not a release timestamp.
    No refused evidence carries its source, metric, rows, or query plan.
    """
    def refuse(status, reason):
        return Evidence(evidence_id, status, reason)

    if upstream_status != "answered":
        statuses = {"masked", "empty", "stale", "clarification_needed", "write_rejected"}
        if upstream_status not in statuses:
            return refuse("invalid", "Unknown upstream response status.")
        return refuse(upstream_status, "Upstream did not provide an answer; no visual story can be produced.")
    policy = access_policy or AccessPolicy()
    # Unlike 0080's optional dimension dropping, this boundary refuses the whole
    # requested shape. Filters must also be authorized before the reader runs.
    auth = authorize_plan(plan, policy, viewer_clearance)
    if isinstance(auth, Clarification) or auth != plan or any(
        not policy.dimension_allowed(f.dimension, viewer_clearance) for f in plan.filters
    ):
        return refuse("masked", "No authorized evidence is available.")
    try:
        validate_plan(plan, layer)
        if view not in VIEWS or not isinstance(evidence_id, str) or not evidence_id.strip():
            raise VisualizationError("An evidence ID and supported view are required.")
        if not isinstance(source, str) or not source.strip():
            raise VisualizationError("A source citation is required.")
        if not isinstance(as_of, int) or isinstance(as_of, bool) or not isinstance(max_age, int) or max_age < 0:
            raise VisualizationError("as_of and nonnegative max_age must be integer period values.")
        if not isinstance(synthetic, bool) or any(not isinstance(c, str) or not c.strip() for c in caveats):
            raise VisualizationError("Provenance requires a boolean synthetic flag and text caveats.")
        if analytics_pack_id not in catalog.analytics:
            raise VisualizationError("Unknown analytics pack.")
        pack = catalog.analytics[analytics_pack_id]
        metrics = {m["name"]: m for m in pack["metrics"]}
        metric = metrics.get(plan.metric)
        if metric is None:
            raise VisualizationError("Metric is not defined in the specified analytics pack.")
        definition = layer.definition(plan.metric)
        dimensions = {d["name"] for d in pack["dimensions"]}
        used = set(plan.dimensions) | {f.dimension for f in plan.filters}
        if used - dimensions or len(set(plan.dimensions)) != len(plan.dimensions):
            raise VisualizationError("Unknown or duplicate domain dimension.")
        if plan.window.grain != definition.grain:
            raise VisualizationError("Query grain differs from the governed metric definition.")
        if plan.window.end_period > as_of:
            raise VisualizationError("Requested window extends beyond the as-of boundary.")
        if plan.comparison is not None or plan.rank is not None:
            raise VisualizationError("Supply comparison evidence explicitly; implicit comparisons and ranks are unsupported.")
        if view in ("level", "trend", "comparison") and plan.dimensions:
            raise VisualizationError("This view requires an ungrouped result.")
        if view in ("breakdown", "attribution") and not plan.dimensions:
            raise VisualizationError("This view requires declared dimensions.")
        if view == "attribution" and "contributor" in analytics_packs.suppressed_insights(pack, plan.metric):
            raise VisualizationError("The analytics pack suppresses contributor attribution for this metric.")
        insight_kind = {"trend": "trend", "comparison": "change"}.get(view, "level")
        if insight_kind in analytics_packs.suppressed_insights(pack, plan.metric):
            raise VisualizationError(f"The analytics pack suppresses {insight_kind} interpretation for this metric.")
        if metric["additivity"] == "non_additive" and definition.kind == "measure" and definition.agg in ("sum", "count"):
            raise VisualizationError("A non-additive metric cannot use sum/count aggregation.")
        if view != "trend" and plan.window.start_period != plan.window.end_period and not analytics_packs.can_sum(metric, "time"):
            raise VisualizationError("This metric cannot aggregate across time; use a snapshot or period-by-period trend.")
        rows = list(reader(plan))
        needed = {definition.numerator, definition.denominator} if definition.kind == "ratio" else ({definition.source} if definition.agg != "count" else set())
        selected = []
        for row in rows:
            if not plan.window.start_period <= row.period <= plan.window.end_period or row.period > as_of:
                continue
            if any(f.dimension not in row.dims for f in plan.filters):
                raise VisualizationError("Missing filter dimension; cannot establish the requested population.")
            if not all(row.dims[f.dimension] in f.values for f in plan.filters):
                continue
            if any(d not in row.dims or not isinstance(row.dims[d], str) or not row.dims[d] for d in used):
                raise VisualizationError("Missing or invalid dimension value; no implicit group is permitted.")
            if any(n not in row.measures or isinstance(row.measures[n], bool) or not isinstance(row.measures[n], (int, float)) or not math.isfinite(row.measures[n]) for n in needed):
                raise VisualizationError("Missing or non-finite measure; no implicit zero is permitted.")
            selected.append(row)
        if not selected:
            return refuse("empty", "No rows match the requested evidence.")
        selected.sort(key=lambda r: canonical(asdict(r)))
        if view == "trend":
            period_results = []
            for period in sorted({r.period for r in selected}):
                period_plan = replace(plan, window=replace(plan.window, start_period=period, end_period=period))
                period_results.append(execute(period_plan, layer, lambda _: selected, as_of))
            series = {r.latest_period: r.values for r in period_results}
            content_hash = hashlib.sha256(canonical([result_payload(r) for r in period_results]).encode()).hexdigest()
            result = Result(plan, period_results[-1].values, series, len(selected), period_results[-1].latest_period, as_of, content_hash)
        else:
            result = execute(plan, layer, lambda _: selected, as_of)
        if as_of - result.latest_period > max_age:
            return refuse("stale", "The latest evidence exceeds the caller's freshness limit.")
        values = list(result.values.values()) + [v for period in result.series.values() for v in period.values()]
        if any(not math.isfinite(v) for v in values):
            raise VisualizationError("Governed computation returned a non-finite value (check denominators).")
        notes = list(caveats)
        if synthetic:
            notes.append("Synthetic demonstration data; not firm data or an investment conclusion.")
        if not analytics_packs.is_reviewed(pack):
            notes.append(f"Unreviewed analytics pack: {analytics_pack_id} ({pack['review']['status']}).")
        for caveat in pack["caveats"]:
            trigger = caveat["trigger"]
            if trigger == "always" or (trigger.startswith("metric:") and fnmatch.fnmatchcase(plan.metric, trigger[7:])) or (trigger.startswith("dimension:") and trigger[10:] in used):
                notes.append("Domain convention: " + caveat["text"])
        if view == "trend":
            notes.append("Each point is computed independently at its observed period; missing periods are not imputed.")
        evidence = Evidence(evidence_id, "ready", "Authorized governed evidence.", analytics_pack_id, view, source,
                            metric["unit"], result, canonical(asdict(definition)), tuple(sorted(set(notes))))
        return replace(evidence, digest=evidence.fingerprint())
    except (VisualizationError, PlanError, GovernanceError) as exc:
        return refuse("invalid", str(exc))


@dataclass(frozen=True)
class Claim:
    evidence_id: str
    evidence_digest: str
    metric: str
    unit: str
    population: tuple[str, ...]
    period: int | None
    as_of: int
    value: float
    source: str


def bind_claim(evidence, population=(), period=None):
    if evidence.status != "ready" or evidence.digest != evidence.fingerprint():
        raise VisualizationError("Evidence is not ready or has changed since collection.")
    result = evidence.result
    if evidence.view == "trend" and period is None:
        period = result.latest_period
    values = result.series.get(period, {}) if period is not None else result.values
    if population not in values:
        raise VisualizationError("Claim does not identify an observed population/period.")
    return Claim(evidence.evidence_id, evidence.digest, result.plan.metric, evidence.unit,
                 population, period, result.as_of, values[population], evidence.source)


def validate_claim(claim, evidence):
    try:
        expected = bind_claim(evidence, claim.population, claim.period)
        return () if claim == expected else ("Claim differs from its exact evidence binding.",)
    except (VisualizationError, ValueError):
        return ("Claim has no valid evidence binding.",)
