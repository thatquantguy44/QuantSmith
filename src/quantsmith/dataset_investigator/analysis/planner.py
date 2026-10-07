"""Investigation planner. Spec ``0099`` (REQ-003, REQ-017).

The deterministic planner turns the profile into a list of tool calls, each
with the reason it is planned, and lists every analysis it skips with the
reason it is skipped. A language-model planner may only choose, drop, and
order analyses from :data:`ANALYSES`; :func:`validate_plan` rejects anything
else, and the tool calls themselves always come from the same rules.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import pandas as pd

from .models import Config, InvestigationState, Plan, PlannedAnalysis, SkippedAnalysis
from .registry import TOOL_REGISTRY
from .roles import target_column, timestamp_column
from .utils import to_datetime

ANALYSES = (
    "profile", "data_quality", "target_balance", "numeric_distributions", "categorical_distributions",
    "correlations", "target_relationships", "missingness_relationships", "segments", "temporal_trends",
    "temporal_drift", "period_patterns", "entity_concentration", "anomaly_detection",
)

MAX_GROUPING_COLUMNS = 15
MAX_BANDED_COLUMNS = 10
MAX_SHIFT_COLUMNS = 10


class PlanError(ValueError):
    """A proposed plan names an analysis the planner does not know."""


def _cols(state: InvestigationState, roles: Sequence[str], *, allow_pii: bool = False) -> List[str]:
    wanted = set(roles)
    return [c.name for c in state.columns if c.role in wanted and (allow_pii or not c.pii)]


def _intraday(df: pd.DataFrame, ts: str) -> bool:
    t = to_datetime(df[ts]).dropna()
    return bool(len(t)) and t.dt.hour.nunique() > 1


def _span_days(df: pd.DataFrame, ts: str) -> int:
    t = to_datetime(df[ts]).dropna()
    return int((t.max() - t.min()).days) if len(t) else 0


def _rules(df: pd.DataFrame, state: InvestigationState) -> Dict[str, object]:
    """Every analysis's tool calls and reason, or the reason it cannot run."""
    cfg: Config = state.config
    rows = state.dataset.rows
    target = target_column(state.columns, cfg)
    target_role = next((c.role for c in state.columns if c.name == target), None)
    binary = target_role == "binary_target"
    ts = timestamp_column(state.columns, cfg)
    numeric = _cols(state, ("continuous_numeric", "discrete_numeric"))
    continuous = _cols(state, ("continuous_numeric",))
    cats = _cols(state, ("categorical", "boolean"))
    entities = _cols(state, ("entity_identifier",), allow_pii=True)
    ids = _cols(state, ("identifier",), allow_pii=True)
    big = rows > cfg.sample_threshold
    sample_note = (f"; expensive methods sampled to {cfg.expensive_sample:,} rows (seed {cfg.seed})"
                   if big else "")
    R: Dict[str, object] = {}

    def calls(*items):
        return [(tool, params) for tool, params in items]

    R["profile"] = (calls(("profile_dataset", {})), "always: shape, roles, missingness")
    R["data_quality"] = (calls(("analyze_missingness", {}), ("analyze_duplicates", {"id_columns": ids}),
                               ("analyze_column_quality", {"as_of": cfg.as_of})),
                         "always: missingness, duplicates, impossible values, types")
    if target:
        R["target_balance"] = (calls(("analyze_target_balance", {"target": target})),
                               f"target `{target}` ({target_role}): class balance")
    else:
        R["target_balance"] = "no target column detected or supplied"
    R["numeric_distributions"] = ((calls(("analyze_distributions", {})), f"{len(numeric)} numeric column(s)")
                                  if numeric else "no numeric columns")
    R["categorical_distributions"] = ((calls(("analyze_categories", {})), f"{len(cats)} categorical column(s)")
                                      if cats else "no categorical columns (or all flagged PII)")
    R["correlations"] = ((calls(("calculate_correlations", {})), "at least two numeric columns")
                         if len(numeric) >= 2 else "fewer than two numeric columns")
    if binary:
        group_cols = cats[:MAX_GROUPING_COLUMNS] + continuous[:MAX_BANDED_COLUMNS]
        items = [("compare_target_rates", {"target": target, "by": c}) for c in group_cols]
        items.append(("mutual_information", {"target": target}))
        R["target_relationships"] = (calls(*items), f"binary target `{target}`: rates by {len(group_cols)} column(s)")
        partly_missing = [c.name for c in state.columns if 0.01 <= c.missing_pct <= 0.99 and c.name != target]
        R["missingness_relationships"] = ((calls(("compare_target_rates_by_missingness", {"target": target})),
                                           f"{len(partly_missing)} partly missing column(s)")
                                          if partly_missing else "no column is between 1% and 99% missing")
    else:
        reason = "no binary target: supervised relationships skipped"
        R["target_relationships"] = reason if not target else (
            calls(("mutual_information", {"target": target})), f"multiclass target `{target}`: mutual information only")
        R["missingness_relationships"] = reason
    if continuous and cats:
        items = [("compare_segments", {"metric": m, "by": c}) for m in continuous[:3] for c in cats[:5]]
        R["segments"] = (calls(*items), "numeric metrics by categorical groups")
    else:
        R["segments"] = "needs a continuous numeric and a categorical column"
    if ts:
        items = [("analyze_time_series", {"timestamp": ts, "metric": continuous[0] if continuous else None,
                                          "target": target if binary else None})]
        R["temporal_trends"] = (calls(*items), f"timestamp `{ts}`")
        shift_cols = (continuous + cats)[:MAX_SHIFT_COLUMNS]
        R["temporal_drift"] = ((calls(*[("detect_distribution_shift", {"column": c, "timestamp": ts}) for c in shift_cols]),
                                f"distribution shift of {len(shift_cols)} column(s) over `{ts}`")
                               if shift_cols else "no numeric or categorical column to test for drift")
        if binary:
            parts = []
            if _intraday(df, ts):
                parts.append("hour")
            if _span_days(df, ts) >= 14:
                parts.append("weekday")
            R["period_patterns"] = ((calls(*[("compare_period_rates", {"timestamp": ts, "target": target, "part": p})
                                             for p in parts]), f"target rate by {', '.join(parts)}")
                                    if parts else "timestamp has no intraday detail and spans under 14 days")
        else:
            R["period_patterns"] = "no binary target: period patterns skipped"
    else:
        for a in ("temporal_trends", "temporal_drift", "period_patterns"):
            R[a] = "no timestamp column detected or supplied"
    if entities:
        items = [("analyze_entity_concentration", {"entity": e, "target": target if binary else None,
                                                   "value": continuous[0] if continuous else None})
                 for e in entities]
        R["entity_concentration"] = (calls(*items), f"entity identifier(s): {', '.join(entities)}")
    else:
        R["entity_concentration"] = "no entity identifier columns"
    if continuous:
        items = [("detect_outliers", {})]
        if len(continuous) >= 2:
            items += [("detect_multivariate_outliers", {"method": m}) for m in ("mahalanobis", "isolation_forest", "lof")]
        R["anomaly_detection"] = (calls(*items), f"{len(continuous)} continuous column(s){sample_note}")
    else:
        R["anomaly_detection"] = "no continuous numeric columns"
    return R


def plan(df: pd.DataFrame, state: InvestigationState, analyses: Optional[Sequence[str]] = None,
         source: str = "rules") -> Plan:
    """Plan the investigation (REQ-003). ``analyses`` (validated) chooses and orders analyses."""
    rules = _rules(df, state)
    order = list(analyses) if analyses is not None else list(ANALYSES)
    planned, skipped = [], []
    for name in order:
        rule = rules[name]
        if isinstance(rule, str):
            skipped.append(SkippedAnalysis(analysis=name, reason=rule))
            continue
        items, reason = rule
        for tool, params in items:
            clean = {k: v for k, v in params.items() if v is not None}
            planned.append(PlannedAnalysis(analysis=name, tool=tool, params=clean, reason=reason))
    for name in ANALYSES:
        if name not in order:
            skipped.append(SkippedAnalysis(analysis=name, reason="not chosen by the planner"))
    for pa in planned:
        assert pa.tool in TOOL_REGISTRY, pa.tool
    return Plan(source=source, analyses=planned, skipped=skipped)


def validate_plan(proposal: object) -> List[str]:
    """Check a model-proposed plan: a list (or ``{"analyses": [...]}``) of known analysis names (REQ-017)."""
    names = proposal.get("analyses") if isinstance(proposal, dict) else proposal
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise PlanError("a plan is a list of analysis names")
    unknown = [n for n in names if n not in ANALYSES]
    if unknown:
        raise PlanError(f"unregistered analysis {unknown}; choose from {list(ANALYSES)}")
    if len(set(names)) != len(names):
        raise PlanError("an analysis is listed twice")
    if "profile" not in names:
        names = ["profile"] + names
    return names
