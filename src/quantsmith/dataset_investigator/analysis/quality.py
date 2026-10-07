"""Data-quality tools. Spec ``0099`` (REQ-004, REQ-006).

Missingness, duplicate rows and identifiers, constant and near-constant
columns, impossible values, unexpected (mixed) types, and cardinality issues.
Results are counts and shares only — never the offending values.
"""

from __future__ import annotations

import re
from typing import List, Optional

import pandas as pd

from .registry import Params, ToolContext, analysis_tool
from .utils import ID_ROLES, NUMERIC_ROLES, TIME_ROLES, to_datetime

ALL_ROLES = frozenset({
    "identifier", "entity_identifier", "timestamp", "continuous_numeric", "discrete_numeric",
    "categorical", "boolean", "binary_target", "multiclass_target", "free_text", "constant",
})

# Quantities that cannot be negative, recognised by column name.
NONNEGATIVE_NAME = re.compile(r"(^|_)(amount|amt|price|qty|quantity|count|age|volume|duration|size|weight|fee|fees)(_|$)", re.IGNORECASE)


class MissingnessParams(Params):
    columns: Optional[List[str]] = None


@analysis_tool(name="analyze_missingness", category="quality", version="1.0.0",
               params=MissingnessParams, columns={"columns": ALL_ROLES})
def analyze_missingness(df: pd.DataFrame, p: MissingnessParams, ctx: ToolContext) -> dict:
    """Missing count and share per column, and how many rows have any missing value."""
    cols = p.columns or list(df.columns)
    rows = int(len(df))
    per = []
    for col in cols:
        m = int(df[col].isna().sum())
        per.append({"column": col, "missing": m, "missing_pct": (m / rows) if rows else 0.0})
    per.sort(key=lambda r: (-r["missing"], r["column"]))
    any_missing = int(df[cols].isna().any(axis=1).sum()) if cols else 0
    return {"rows": rows, "columns": per, "rows_with_missing": any_missing,
            "rows_with_missing_pct": (any_missing / rows) if rows else 0.0}


class DuplicatesParams(Params):
    id_columns: Optional[List[str]] = None


@analysis_tool(name="analyze_duplicates", category="quality", version="1.0.0",
               params=DuplicatesParams, columns={"id_columns": frozenset({"identifier"})})
def analyze_duplicates(df: pd.DataFrame, p: DuplicatesParams, ctx: ToolContext) -> dict:
    """Exact duplicate rows, and repeated values in columns that should be unique identifiers."""
    rows = int(len(df))
    dup_rows = int(df.duplicated().sum())
    id_cols = p.id_columns if p.id_columns is not None else ctx.columns({"identifier"}, allow_pii=True)
    ids = []
    for col in id_cols:
        values = df[col].dropna()
        counts = values.value_counts()
        ids.append({"column": col, "duplicate_rows": int(values.duplicated().sum()),
                    "ids_repeated": int((counts > 1).sum())})
    return {"rows": rows, "duplicate_rows": dup_rows,
            "duplicate_rows_pct": (dup_rows / rows) if rows else 0.0, "identifiers": ids}


class ColumnQualityParams(Params):
    as_of: Optional[str] = None


def _mixed_type_share(s: pd.Series) -> Optional[float]:
    values = s.dropna()
    if not len(values) or pd.api.types.is_numeric_dtype(s) or pd.api.types.is_datetime64_any_dtype(s):
        return None
    probe = values if len(values) <= 5000 else values.sample(n=5000, random_state=0)
    share = float(pd.to_numeric(probe.astype(str).str.strip(), errors="coerce").notna().mean())
    if share == 0.0:
        return share  # a sample of pure text: not worth a full pass
    return float(pd.to_numeric(values.astype(str).str.strip(), errors="coerce").notna().mean())


@analysis_tool(name="analyze_column_quality", category="quality", version="1.0.0", params=ColumnQualityParams)
def analyze_column_quality(df: pd.DataFrame, p: ColumnQualityParams, ctx: ToolContext) -> dict:
    """Constant and near-constant columns, impossible values, mixed types, cardinality issues."""
    rows = int(len(df))
    as_of = p.as_of or ctx.as_of
    constant, near_constant, negatives, mixed, high_card, time_issues = [], [], [], [], [], []
    for col in df.columns:
        s = df[col]
        role = ctx.roles.get(col)
        values = s.dropna()
        if role == "constant":
            constant.append({"column": col, "n_unique": int(values.nunique())})
        elif len(values):
            top_share = float(values.value_counts(normalize=True).iloc[0])
            if top_share >= ctx.near_constant:
                near_constant.append({"column": col, "top_share": top_share})
        if role in NUMERIC_ROLES and NONNEGATIVE_NAME.search(col):
            neg = int((pd.to_numeric(s, errors="coerce") < 0).sum())
            if neg:
                negatives.append({"column": col, "negative": neg, "negative_pct": neg / rows})
        share = _mixed_type_share(s)
        non_numeric = int(round((1 - share) * len(values))) if share is not None else 0
        if share is not None and share >= 0.05 and non_numeric >= 1:
            mixed.append({"column": col, "numeric_like_share": share, "non_numeric": non_numeric})
        if role == "categorical" and len(values) and values.nunique() > 50 and values.nunique() / len(values) > 0.5:
            high_card.append({"column": col, "n_unique": int(values.nunique()),
                              "unique_ratio": float(values.nunique() / len(values))})
        if role in TIME_ROLES:
            t = to_datetime(s)
            early = int((t < pd.Timestamp("1900-01-01")).sum())
            future = int((t > pd.Timestamp(as_of)).sum()) if as_of else None
            unparsed = int((t.isna() & s.notna()).sum())
            if early or future or unparsed:
                time_issues.append({"column": col, "before_1900": early, "after_as_of": future,
                                    "unparseable": unparsed, "as_of": as_of})
    issues = len(constant) + len(near_constant) + len(negatives) + len(mixed) + len(high_card) + len(time_issues)
    return {"rows": rows, "constant": constant, "near_constant": near_constant,
            "negative_in_nonnegative": negatives, "mixed_types": mixed,
            "high_cardinality_categoricals": high_card, "timestamp_issues": time_issues,
            "issue_count": issues, "id_roles_checked": sorted(ID_ROLES)}
