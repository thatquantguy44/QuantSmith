"""Governed ``0080`` Reader over reviewed SFMeridian metric sources.

This is deliberately inside :mod:`sfmeridian.governed`: it is the adapter
that may import QuantSmith's ``QueryPlan`` and ``Fact`` contracts while the
plugin's SQL composition, verification, and execution core remains usable
without the SDK.

Only a metric source reported ``available`` by ``0115`` mapping validation is
eligible.  The reviewed source is verified again against the current catalog
and executed through the query-only capability.  Result columns are mapped
exactly as declared by ``governed_tier.metric_sources``.  Because ``0008``'s
``Fact`` is intentionally provenance-free, each returned batch is registered
by a deterministic fact hash with its execution provenance.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from quantsmith.nl_analytics.plan import QueryPlan  # type: ignore[import-untyped]
from quantsmith.pipelines.metrics_semantic_layer import (  # type: ignore[import-untyped]
    Fact,
)

from ..access import REDACTED, Caller, column_requirements, scrub
from ..config import Config
from ..execute import ExecutionError, ExecutionProvenance, QueryOnlyAdapter, execute
from ..index import Index
from ..verify import VerificationRequest, trusted_predicate_literals, verify

__all__ = [
    "EvidenceRegistry",
    "FactBatchEvidence",
    "MetricSourceUnavailable",
    "Reader",
    "fact_batch_hash",
]


class MetricSourceUnavailable(RuntimeError):
    """Typed, stable refusal for every unavailable governed metric source."""

    code = "E_METRIC_SOURCE_UNAVAILABLE"

    def __init__(self, metric: str, reason: str) -> None:
        self.metric = metric
        self.reason = scrub(reason)
        super().__init__(f"{self.code}: metric {metric!r} is unavailable ({self.reason})")


@dataclass(frozen=True)
class FactBatchEvidence:
    """Run-scoped link from one immutable fact batch to SQL provenance."""

    batch_hash: str
    plan_hash: str
    metric: str
    source_query_id: str
    provenance: ExecutionProvenance

    def as_dict(self) -> dict[str, Any]:
        return {
            "batch_hash": self.batch_hash,
            "plan_hash": self.plan_hash,
            "metric": self.metric,
            "source_query_id": self.source_query_id,
            "provenance": self.provenance.as_dict(),
        }


class EvidenceRegistry:
    """In-memory evidence for fact batches produced during one caller run."""

    def __init__(self) -> None:
        self._by_hash: dict[str, FactBatchEvidence] = {}
        self._by_plan: dict[str, str] = {}

    def record(self, plan: QueryPlan, facts: Sequence[Fact], query_id: str,
               provenance: ExecutionProvenance) -> FactBatchEvidence:
        batch_hash = fact_batch_hash(facts)
        evidence = FactBatchEvidence(
            batch_hash=batch_hash,
            plan_hash=plan.content_hash(),
            metric=plan.metric,
            source_query_id=query_id,
            provenance=provenance,
        )
        self._by_hash[batch_hash] = evidence
        self._by_plan[evidence.plan_hash] = batch_hash
        return evidence

    def get(self, batch_hash: str) -> FactBatchEvidence | None:
        return self._by_hash.get(batch_hash)

    def for_plan(self, plan: QueryPlan) -> FactBatchEvidence | None:
        batch_hash = self._by_plan.get(plan.content_hash())
        return self._by_hash.get(batch_hash) if batch_hash else None

    def as_dict(self) -> dict[str, dict[str, Any]]:
        return {key: self._by_hash[key].as_dict() for key in sorted(self._by_hash)}


def fact_batch_hash(facts: Sequence[Fact]) -> str:
    """Content hash of facts, independent of database row order."""
    rows = [
        {
            "period": fact.period,
            "dims": dict(sorted(fact.dims.items())),
            "measures": dict(sorted(fact.measures.items())),
        }
        for fact in facts
    ]
    rows.sort(key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":")))
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


class Reader:
    """Callable implementation of ``quantsmith.nl_analytics.execute.Reader``."""

    def __init__(
        self,
        *,
        config: Config,
        index: Index,
        mapping_report: Mapping[str, Any],
        snapshot: Mapping[str, Any],
        join_graph: Sequence[Mapping[str, Any]],
        caller: Caller,
        source: QueryOnlyAdapter,
        key_id: str,
        signing_key: bytes,
        keys: Mapping[str, bytes],
        now: int | Callable[[], int],
        evidence: EvidenceRegistry | None = None,
    ) -> None:
        self.config = config
        self.index = index
        self.mapping_report = mapping_report
        self.snapshot = snapshot
        self.join_graph = join_graph
        self.caller = caller
        self.source = source
        self.key_id = key_id
        self.signing_key = signing_key
        self.keys = keys
        self._now = now if callable(now) else lambda: now
        self.evidence = evidence or EvidenceRegistry()

    def __call__(self, plan: QueryPlan) -> Sequence[Fact]:
        """Return governed facts or one typed unavailable-source refusal."""
        try:
            return self._read(plan)
        except MetricSourceUnavailable:
            raise
        except ExecutionError as exc:
            raise MetricSourceUnavailable(plan.metric, exc.code) from None
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise MetricSourceUnavailable(plan.metric, type(exc).__name__) from None

    def _read(self, plan: QueryPlan) -> tuple[Fact, ...]:
        source_config = self._source_config(plan.metric)
        source_status = self._source_status(plan.metric, str(source_config["exemplar_id"]))
        if source_status.get("status") != "available":
            raise MetricSourceUnavailable(plan.metric, "source-status")

        exemplar = self._exemplar(plan.metric, str(source_config["exemplar_id"]))
        profile_id = str(source_status.get("profile") or exemplar.get("profile") or "")
        if not profile_id or profile_id != self.snapshot.get("profile"):
            raise MetricSourceUnavailable(plan.metric, "profile-mismatch")
        profile = self.config.profile(profile_id)
        if (exemplar.get("review_status") != "reviewed"
                or exemplar.get("eligibility") != "primary"
                or exemplar.get("dialect") != profile.get("dialect")):
            raise MetricSourceUnavailable(plan.metric, "source-not-reviewed")

        dimensions = dict(source_config.get("dimension_columns") or {})
        measures = dict(source_config.get("measure_columns") or {})
        requested = set(plan.dimensions) | {item.dimension for item in plan.filters}
        if not requested <= set(dimensions):
            raise MetricSourceUnavailable(plan.metric, "dimension-mismatch")
        if set(measures) == set() or plan.metric not in measures:
            raise MetricSourceUnavailable(plan.metric, "measure-mismatch")
        self._authorize_outputs(exemplar, source_config)

        params = self._bind_params(plan, exemplar, dimensions)
        as_of = _period_to_date(plan.window.end_period)
        sql = exemplar.get("sql")
        if not isinstance(sql, str) or not sql.strip():
            raise MetricSourceUnavailable(plan.metric, "source-sql-missing")
        pit_columns = tuple(str(value) for value in exemplar.get("pit_columns") or ())
        request = VerificationRequest(
            sql=sql,
            params=params,
            profile=profile_id,
            as_of=as_of,
            pit_columns=pit_columns,
            require_pit=True,
            clearance=self.caller.clearance,
            composition_path="reuse",
            query_id=str(exemplar.get("query_id") or source_config["exemplar_id"]),
            trusted_literal_hashes=trusted_predicate_literals(sql, str(profile["dialect"])),
        )
        now = self._now()
        outcome = verify(
            request,
            profile=profile,
            snapshot=self.snapshot,
            join_graph=self.join_graph,
            config_hash=self.config.hash,
            key_id=self.key_id,
            signing_key=self.signing_key,
            now=now,
            ttl_s=int(self.config.data["verification"]["token_ttl_s"]),
        )
        if not outcome.ok or outcome.verified is None:
            reason = outcome.findings[0].code if outcome.findings else "verification-failed"
            raise MetricSourceUnavailable(plan.metric, reason)
        result = execute(
            outcome.verified,
            token=outcome.verified.token,
            params=params,
            keys=self.keys,
            now=now,
            config=self.config,
            snapshot_id=str(self.snapshot["snapshot_id"]),
            caller=self.caller,
            source=self.source,
            source_exemplars=(str(exemplar.get("query_id") or exemplar["exemplar_id"]),),
        )
        facts = self._facts(plan, source_config, exemplar, result.rows)
        query_id = str(exemplar.get("query_id") or source_config["exemplar_id"])
        self.evidence.record(plan, facts, query_id, result.provenance)
        return facts

    def _source_config(self, metric: str) -> Mapping[str, Any]:
        matches = [item for item in self.config.data.get("governed_tier", {}).get("metric_sources", [])
                   if item.get("metric") == metric]
        if len(matches) != 1:
            raise MetricSourceUnavailable(metric, "source-not-unique")
        return matches[0]

    def _source_status(self, metric: str, exemplar_id: str) -> Mapping[str, Any]:
        matches = [item for item in self.mapping_report.get("metric_sources", [])
                   if item.get("metric") == metric and item.get("exemplar_id") == exemplar_id]
        if len(matches) != 1:
            raise MetricSourceUnavailable(metric, "source-not-validated")
        return matches[0]

    def _exemplar(self, metric: str, reference: str) -> Mapping[str, Any]:
        matches = [item for item in self.index.exemplars
                   if item.get("exemplar_id") == reference or item.get("query_id") == reference]
        reviewed = [item for item in matches if item.get("review_status") == "reviewed"]
        if len(reviewed) != 1:
            raise MetricSourceUnavailable(metric, "source-not-indexed")
        return reviewed[0]

    def _authorize_outputs(self, exemplar: Mapping[str, Any], source_config: Mapping[str, Any]) -> None:
        requirements = column_requirements(self.config)
        outputs = set((source_config.get("dimension_columns") or {}).values())
        outputs.update((source_config.get("measure_columns") or {}).values())
        selected = {item.get("name"): item for item in exemplar.get("structure", {}).get("select", [])}
        for output in outputs:
            item = selected.get(output)
            if item is None:
                raise MetricSourceUnavailable(str(source_config.get("metric")), "output-mismatch")
            for column in item.get("columns") or ():
                parts = str(column).lower().split(".")
                key = ".".join(parts[-2:])
                rule = requirements.get(key) or requirements.get(str(column).lower())
                if rule and not self.caller.sees(rule["level"]):
                    raise MetricSourceUnavailable(str(source_config.get("metric")), "caller-unauthorized")

    def _bind_params(self, plan: QueryPlan, exemplar: Mapping[str, Any],
                     dimensions: Mapping[str, str]) -> dict[str, Any]:
        start = _period_to_date(plan.window.start_period)
        end = _period_to_date(plan.window.end_period)
        filters = {item.dimension: item for item in plan.filters}
        values: dict[str, Any] = {"as_of": end, "start_date": start, "end_date": end}
        for dimension, column in dimensions.items():
            item = filters.get(dimension)
            if item is not None and item.op == "eq":
                values[dimension] = item.values[0]
                values[str(column)] = item.values[0]
                values[str(column).rsplit(".", 1)[-1]] = item.values[0]

        bound: dict[str, Any] = {}
        for declaration in exemplar.get("params") or ():
            if not isinstance(declaration, Mapping) or not isinstance(declaration.get("name"), str):
                raise MetricSourceUnavailable(plan.metric, "parameter-declaration")
            name = str(declaration["name"])
            if name in values:
                bound[name] = values[name]
            elif "default" in declaration:
                bound[name] = declaration["default"]
            elif declaration.get("required", False):
                raise MetricSourceUnavailable(plan.metric, "parameter-mismatch")
        return bound

    def _facts(self, plan: QueryPlan, source_config: Mapping[str, Any], exemplar: Mapping[str, Any],
               rows: Sequence[Mapping[str, Any]]) -> tuple[Fact, ...]:
        dimension_columns = dict(source_config.get("dimension_columns") or {})
        measure_columns = dict(source_config.get("measure_columns") or {})
        period_column = str(source_config.get("period_column") or "")
        output_names = {item.get("name") for item in exemplar.get("structure", {}).get("select", [])}
        period_is_output = period_column in output_names
        facts: list[Fact] = []
        needed = set(dimension_columns.values()) | set(measure_columns.values())
        if period_is_output:
            needed.add(period_column)
        for row in rows:
            if not needed <= set(row):
                raise MetricSourceUnavailable(plan.metric, "output-mismatch")
            if any(row[name] == REDACTED for name in needed):
                raise MetricSourceUnavailable(plan.metric, "caller-unauthorized")
            dims = {name: str(row[column]) for name, column in sorted(dimension_columns.items())}
            measures = {name: _number(row[column]) for name, column in sorted(measure_columns.items())}
            period = _period(row[period_column]) if period_is_output else plan.window.end_period
            facts.append(Fact(period=period, dims=dims, measures=measures))
        return tuple(facts)


def _period_to_date(period: int) -> str:
    text = str(period)
    if len(text) != 8 or not text.isdigit():
        raise ValueError("day-grain periods must use YYYYMMDD")
    return f"{text[:4]}-{text[4:6]}-{text[6:]}"


def _period(value: Any) -> int:
    if isinstance(value, bool):
        raise TypeError("boolean is not a period")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.replace("-", "")
        if len(text) == 8 and text.isdigit():
            return int(text)
    raise ValueError("period output is not YYYYMMDD")


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("measure output is not numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("measure output is not finite")
    return result
