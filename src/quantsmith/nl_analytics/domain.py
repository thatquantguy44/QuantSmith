"""Analytics domain packs applied to an answer. Spec ``0080`` (REQ-015,
REQ-016, REQ-017; T-021, T-022).

The packs themselves (``knowledge/analytics_packs/*.json``) and their
validator ship with spec ``0081`` (:mod:`quantsmith.pipelines.analytics_packs`).
This module is the 0080 side: given the packs a dataset's ``domain:`` tags
select, it decides

* the **metric policy** an insight set is computed under — the metric's unit
  and additivity, and which insight kinds must not appear for it;
* the **vocabulary** the interpreter may use (pack synonyms for metrics and
  dimensions that are already governed in the ``0008`` registry — a pack can
  never add a metric the registry does not define);
* whether the question uses a **term two selected packs disagree on**, which
  is a clarification, never a guess;
* the **caveats** the response must carry: pack caveats, chart conventions,
  suppressed-insight notices, the unreviewed-pack notice (REQ-016), and the
  generic-behavior notice when no pack matched (REQ-017);
* whether **write-back** is allowed (only when every applied pack is
  ``reviewed`` — REQ-016).

Packs only ever restrict (REQ-017): additivity is the *stricter* of the
generic rule and every pack's declaration, and suppressed insights are the
*union* of the generic rule and every pack's rules, so the set of insights a
pack permits is always a subset of the generic set (AC-026).

Generic behavior reads the ``0008`` definition only: a summed or counted
measure is additive; a mean or a ratio is not additive across groups or time
(a mean of yields across tenors is not a yield, and neither is their sum).

Standard library only.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, replace
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from quantsmith.pipelines.analytics_packs import (
    ADDITIVITY,
    ADDITIVITY_RULES,
    INSIGHT_KINDS,
    Selection,
    is_reviewed,
    select_packs,
    suppressed_insights,
)
from quantsmith.pipelines.metrics_semantic_layer import SemanticLayer

from .interpret import InterpretContext, _matches_phrase, _tokens
from .plan import Clarification, QueryPlan

GENERIC = "generic"

# Most to least permissive; packs may only move a metric to the right.
_STRICTNESS = {name: i for i, name in enumerate(ADDITIVITY)}

# Units whose changes are reported in basis points, never as a percent
# change of the level (a yield from 4.00% to 4.20% is +20 bp, not +5%).
_BPS_FACTOR = {"pct": 100.0, "bps": 1.0}


@dataclass(frozen=True)
class MetricPolicy:
    """How one metric may be aggregated and reported.

    The default is the legacy, fully additive policy with no unit — what
    :func:`~quantsmith.nl_analytics.insights.compute_insights` assumes when
    called without one. :func:`resolve_policy` is what ``answer()`` uses.
    """

    metric: str = ""
    unit: str = ""
    additivity: str = "additive"
    suppressed: Tuple[str, ...] = ()
    basis: str = GENERIC  # "generic" or "pack:<id>[,<id>...]"
    reasons: Tuple[str, ...] = ()
    # The metric's declared 0008 dimensions: an ungrouped answer about a
    # non-additive metric pools rows across these.
    declared_dimensions: Tuple[str, ...] = ()

    @property
    def sums_across_dimensions(self) -> bool:
        return ADDITIVITY_RULES[self.additivity][0]

    @property
    def sums_across_time(self) -> bool:
        return ADDITIVITY_RULES[self.additivity][1]

    @property
    def bps_factor(self) -> Optional[float]:
        """Multiplier from a change in ``unit`` to basis points, or ``None``."""
        return _BPS_FACTOR.get(self.unit)

    @property
    def display_unit(self) -> str:
        return {"pct": "%", "bps": "bp"}.get(self.unit, "")

    def allows(self, kind: str) -> bool:
        return kind not in self.suppressed


def select(domains: Sequence[str], packs: Sequence[Mapping]) -> Selection:
    """The packs ``domains`` select (spec ``0081`` REQ-004); empty when no tags."""
    return select_packs(tuple(domains), tuple(packs))


def generic_additivity(layer: SemanticLayer, metric: str) -> str:
    """Additivity from the ``0008`` definition alone (REQ-017)."""
    defn = layer.definition(metric)
    if defn.kind == "ratio" or defn.agg == "mean":
        return "non_additive"
    return "additive"


def _pack_metric(pack: Mapping, metric: str) -> Optional[Mapping]:
    return next((m for m in pack["metrics"] if m["name"] == metric), None)


def resolve_policy(layer: SemanticLayer, metric: str, selection: Optional[Selection] = None) -> MetricPolicy:
    """The policy ``metric`` is answered under: generic, restricted by every selected pack."""
    additivity = generic_additivity(layer, metric)
    suppressed = set()
    reasons: List[str] = []

    unit = ""
    applied: List[str] = []
    for pack in (selection.packs if selection is not None else ()):
        declared = _pack_metric(pack, metric)
        if declared is not None:
            applied.append(pack["pack_id"])
            unit = unit or declared["unit"]
            if _STRICTNESS[declared["additivity"]] > _STRICTNESS[additivity]:
                additivity = declared["additivity"]
        for kind in suppressed_insights(pack, metric):
            suppressed.add(kind)
        for rule in pack["insight_rules"]:
            if fnmatch.fnmatchcase(metric, rule["applies_to"]):
                reasons.append(f"{pack['pack_id']} rule {rule['id']}: {rule['reason']}")
    if not ADDITIVITY_RULES[additivity][0]:
        suppressed.update(("contributor", "concentration"))

    return MetricPolicy(
        declared_dimensions=tuple(layer.definition(metric).dimensions),
        metric=metric,
        unit=unit,
        additivity=additivity,
        suppressed=tuple(k for k in INSIGHT_KINDS if k in suppressed),
        basis=("pack:" + ",".join(applied)) if applied else GENERIC,
        reasons=tuple(dict.fromkeys(reasons)),
    )


def extend_interpret_context(
    context: InterpretContext, layer: SemanticLayer, selection: Selection
) -> InterpretContext:
    """Add selected packs' synonyms for metrics and dimensions the registry
    already governs (REQ-015). A pack term for anything outside the registry
    is ignored: packs extend vocabulary, never access."""
    governed = set(layer._defs)  # same governed vocabulary the interpreter reads
    governed_dims = {d for name in governed for d in layer.definition(name).dimensions}
    metric_syn: Dict[str, Tuple[str, ...]] = dict(context.known_metric_synonyms)
    dim_syn: Dict[str, Tuple[str, ...]] = dict(context.known_dimension_synonyms)
    for pack in selection.packs:
        for item, target, known in (
            *((m, metric_syn, governed) for m in pack["metrics"]),
            *((d, dim_syn, governed_dims) for d in pack["dimensions"]),
        ):
            if item["name"] in known and item.get("synonyms"):
                merged = tuple(target.get(item["name"], ())) + tuple(item["synonyms"])
                target[item["name"]] = tuple(dict.fromkeys(merged))
    return replace(context, known_metric_synonyms=metric_syn, known_dimension_synonyms=dim_syn)


def term_conflict(question: str, selection: Selection) -> Optional[Clarification]:
    """A clarification when the question uses a term two selected packs map to
    different metrics (REQ-015, AC-024); ``None`` otherwise."""
    tokens = set(_tokens(question))
    for term, owners in selection.synonym_conflicts:
        if _matches_phrase(" ".join(_tokens(term)), tokens):
            metrics = tuple(sorted({o.split(".", 1)[1] for o in owners}))
            packs = sorted({o.split(".", 1)[0] for o in owners})
            return Clarification(
                reason=f"the term {term!r} means a different metric in each of the packs {', '.join(packs)}",
                candidates=metrics,
                question=question,
            )
    return None


def domain_caveats(selection: Selection, policy: MetricPolicy, plan: QueryPlan) -> Tuple[str, ...]:
    """Caveats the domain adds to an answer (REQ-015, REQ-016, REQ-017)."""
    out: List[str] = []
    if not selection.packs:
        out.append(
            f"No analytics domain pack matched this dataset; generic behavior was used "
            f"({plan.metric} treated as {policy.additivity}, from its metric definition only)."
        )
    for pack in selection.packs:
        if not is_reviewed(pack):
            out.append(
                f"Unreviewed domain pack: {pack['pack_id']} (status {pack['review']['status']}); "
                f"its conventions are applied here but have not been signed off, and write-back is refused."
            )
    for pack in selection.packs:
        for c in pack["caveats"]:
            trig = c["trigger"]
            if (
                trig == "always"
                or (trig.startswith("metric:") and fnmatch.fnmatchcase(plan.metric, trig[7:]))
                or (trig.startswith("dimension:") and trig[10:] in plan.dimensions)
            ):
                out.append(c["text"])
        if _pack_metric(pack, plan.metric) is not None:
            out.extend(f"Chart convention: {c['rule']}" for c in pack["chart_conventions"])
    if not policy.sums_across_dimensions and policy.declared_dimensions and not plan.dimensions:
        dims = ", ".join(policy.declared_dimensions)
        out.append(
            f"{plan.metric} is {policy.additivity}: this single value pools every matching row. If the rows "
            f"span several values of {dims}, it is not a {plan.metric} of any of them (a sum or average of "
            f"{plan.metric} across groups is not a {plan.metric}); ask by {dims} instead."
        )
    if policy.suppressed:
        why = "; ".join(policy.reasons) or f"{plan.metric} is {policy.additivity}, so its groups do not add up"
        out.append(f"Not shown for {plan.metric}: {', '.join(policy.suppressed)} insights ({why}).")
    return tuple(dict.fromkeys(out))


def writeback_refusal(selection: Selection) -> Optional[str]:
    """Why write-back is refused, or ``None`` when every applied pack is
    ``reviewed`` (REQ-016). No applied pack means generic behavior, which the
    packs' review gate does not cover."""
    unreviewed = [p["pack_id"] for p in selection.packs if not is_reviewed(p)]
    if not unreviewed:
        return None
    return f"write-back refused: applied domain pack(s) not reviewed: {', '.join(unreviewed)}"
