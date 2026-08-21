"""Reference pipeline for spec 0039 — ingestion data contract emission.

Given a caller-supplied, already-pulled row set (this module does not fetch
data itself — see the spec's Non-Goals, matching ``agents/data_ingestion/*``'s
own advisory-brief scope) and a declared schema/key/quality-rule contract,
``validate_ingestion`` checks the rows against that contract, collecting every
violation rather than stopping at the first, and ``render_data_contract``
renders a Markdown document matching ``templates/data/data_contract.md``'s
section structure, populated entirely from the real, computed validation
results — never a filled-in-by-hand template.

Every rendered claim about the data (duplicate keys, missingness) states what
was actually found "in the validated sample", never an unqualified guarantee
over data beyond what was checked.
"""

from __future__ import annotations

import datetime
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

from quantsmith.pipelines.workflow_memory import CandidateSpec


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    type: str  # "date" | "string" | "int" | "float" | "bool"
    nullable: bool
    description: str = ""


@dataclass(frozen=True)
class QualityRule:
    name: str
    threshold: str
    action_on_breach: str
    column: Optional[str] = None
    max_missing_fraction: Optional[float] = None


@dataclass(frozen=True)
class PointInTimeSpec:
    availability: str
    use_original_vintage: bool
    as_of_join_semantics: str


@dataclass(frozen=True)
class SchemaViolation:
    row_index: int
    column: str
    reason: str


@dataclass(frozen=True)
class QualityRuleResult:
    rule: QualityRule
    observed: str
    passed: bool


@dataclass(frozen=True)
class IngestionValidationResult:
    row_count: int
    schema_violations: List[SchemaViolation]
    duplicate_key_count: int
    missingness_by_column: Dict[str, float]
    rule_results: List[QualityRuleResult]

    @property
    def is_clean(self) -> bool:
        return (
            not self.schema_violations
            and self.duplicate_key_count == 0
            and all(r.passed for r in self.rule_results)
        )


def _is_date(value: object) -> bool:
    if isinstance(value, datetime.date):
        return True
    if isinstance(value, str):
        try:
            datetime.date.fromisoformat(value)
            return True
        except ValueError:
            return False
    return False


_TYPE_CHECKS: Dict[str, Callable[[object], bool]] = {
    "date": _is_date,
    "string": lambda v: isinstance(v, str),
    "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "float": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "bool": lambda v: isinstance(v, bool),
}


def validate_ingestion(
    rows: Sequence[Dict[str, object]],
    schema: Sequence[ColumnSpec],
    key_columns: Sequence[str],
    missingness_rules: Sequence[QualityRule],
) -> IngestionValidationResult:
    """Validate ``rows`` against a declared schema, key uniqueness, and quality rules.

    Collects every violation found rather than stopping at the first.
    Deterministic: the same rows, schema, and rules always return the same
    result.
    """
    row_count = len(rows)
    schema_violations: List[SchemaViolation] = []
    missing_counts: Dict[str, int] = {col.name: 0 for col in schema}

    for i, row in enumerate(rows):
        for col in schema:
            value = row.get(col.name)
            if value is None:
                missing_counts[col.name] += 1
                if not col.nullable:
                    schema_violations.append(
                        SchemaViolation(row_index=i, column=col.name, reason="null in non-nullable column")
                    )
                continue
            check = _TYPE_CHECKS.get(col.type)
            if check is not None and not check(value):
                schema_violations.append(
                    SchemaViolation(
                        row_index=i,
                        column=col.name,
                        reason=f"expected type {col.type!r}, got {type(value).__name__}",
                    )
                )

    seen_keys: Dict[tuple, int] = {}
    for row in rows:
        key = tuple(row.get(k) for k in key_columns)
        seen_keys[key] = seen_keys.get(key, 0) + 1
    duplicate_key_count = sum(count - 1 for count in seen_keys.values() if count > 1)

    missingness_by_column = {
        name: (missing_counts[name] / row_count if row_count else 0.0) for name in missing_counts
    }

    rule_results: List[QualityRuleResult] = []
    for rule in missingness_rules:
        if rule.column is not None and rule.max_missing_fraction is not None:
            observed_fraction = missingness_by_column.get(rule.column, 0.0)
            passed = observed_fraction <= rule.max_missing_fraction
            observed = f"{observed_fraction:.4f} missing"
        elif rule.name.lower() == "duplicate keys":
            passed = duplicate_key_count == 0
            observed = f"{duplicate_key_count} duplicate(s) found"
        else:
            passed = True
            observed = "not evaluated (no column/threshold declared)"
        rule_results.append(QualityRuleResult(rule=rule, observed=observed, passed=passed))

    return IngestionValidationResult(
        row_count=row_count,
        schema_violations=schema_violations,
        duplicate_key_count=duplicate_key_count,
        missingness_by_column=missingness_by_column,
        rule_results=rule_results,
    )


def candidates_from_validation(
    result: IngestionValidationResult, *, dataset_scope: str, source_run: str,
    target_catalog: str,
) -> List[CandidateSpec]:
    """Turn what ``validate_ingestion`` actually found into memory candidates.

    Spec ``0049`` REQ-012 — the worked proof that capture belongs at the
    runtime boundary: this looked at real rows and found a real column and a
    real rule, not a gate finding naming a source file. One candidate per
    distinct schema-violation shape (column, reason) — grouped so ten rows
    breaking the same way become one observation, not ten — and one per
    failed quality rule. Every statement names what was found "in the
    validated sample", matching this module's own disclosure convention
    (never an unqualified guarantee about data beyond what was checked).

    Returns candidates only; nothing is proposed, staged, or promoted here —
    that decision belongs to this function's caller (spec RISK-004).
    """
    specs: List[CandidateSpec] = []
    evidence = ({"source_run": source_run},)

    violation_counts = Counter(
        (v.column, v.reason) for v in result.schema_violations)
    for (column, reason), count in sorted(violation_counts.items()):
        specs.append(CandidateSpec(
            scope=f"field:{column}", type="pitfall",
            statement=(f"{count} row(s) in the validated sample ({source_run}) "
                       f"violated: {reason}."),
            confidence="low", pit_scope="<= run date", evidence=evidence,
            target_catalog=target_catalog,
        ))

    for rr in result.rule_results:
        if rr.passed:
            continue
        scope = f"field:{rr.rule.column}" if rr.rule.column else f"dataset:{dataset_scope}"
        specs.append(CandidateSpec(
            scope=scope, type="pitfall",
            statement=(f"Quality rule {rr.rule.name!r} failed in the validated "
                       f"sample ({source_run}): {rr.observed} "
                       f"(threshold {rr.rule.threshold})."),
            confidence="low", pit_scope="<= run date", evidence=evidence,
            target_catalog=target_catalog,
        ))

    return specs


def render_data_contract(
    dataset_name: str,
    owner: str,
    source_id: str,
    schema: Sequence[ColumnSpec],
    key_columns: Sequence[str],
    grain: str,
    point_in_time: PointInTimeSpec,
    validation: IngestionValidationResult,
    lineage_access: str,
    refresh_schedule: str,
    change_policy: str,
    spec_id: str = "",
    last_updated: str = "",
) -> str:
    """Render a Markdown data contract matching ``templates/data/data_contract.md``.

    Populated from real, computed ``validation`` results — the Grain & Keys and
    Missingness sections state what was actually found in the validated
    sample, never a default/unexamined statement.
    """
    lines: List[str] = []
    lines.append(f"# Data Contract: {dataset_name}")
    lines.append("")
    lines.append(f"- **Owner:** {owner}")
    lines.append(f"- **Source:** `sources/{source_id}.yml`")
    if spec_id:
        lines.append(f"- **Spec:** {spec_id}")
    if last_updated:
        lines.append(f"- **Last updated:** {last_updated}")
    lines.append("")

    lines.append("## Grain & Keys")
    lines.append("")
    lines.append(f"- **Grain:** {grain}")
    lines.append(f"- **Primary/join key(s):** {', '.join(key_columns)}")
    if validation.duplicate_key_count == 0:
        lines.append(
            f"- **Uniqueness:** the key is unique per grain — no duplicates "
            f"found in the validated sample ({validation.row_count} row(s) checked)."
        )
    else:
        lines.append(
            f"- **Uniqueness:** NOT unique — {validation.duplicate_key_count} "
            f"duplicate key combination(s) found in the validated sample "
            f"({validation.row_count} row(s) checked)."
        )
    lines.append("")

    lines.append("## Schema")
    lines.append("")
    lines.append("| Column | Type | Nullable | Description |")
    lines.append("| --- | --- | --- | --- |")
    for col in schema:
        lines.append(f"| {col.name} | {col.type} | {'yes' if col.nullable else 'no'} | {col.description} |")
    lines.append("")

    lines.append("## Point-in-Time Rules")
    lines.append("")
    lines.append(f"- Availability: {point_in_time.availability}")
    lines.append(
        f"- Vintage: use original vintage, not latest revision? "
        f"{'yes' if point_in_time.use_original_vintage else 'no'}."
    )
    lines.append(f"- As-of join semantics: {point_in_time.as_of_join_semantics}")
    lines.append("")

    lines.append("## Missingness & Quality Rules")
    lines.append("")
    lines.append("| Rule | Threshold | Action on breach | Observed | Status |")
    lines.append("| --- | --- | --- | --- | --- |")
    for result in validation.rule_results:
        status = "pass" if result.passed else "BREACH"
        lines.append(
            f"| {result.rule.name} | {result.rule.threshold} | "
            f"{result.rule.action_on_breach} | {result.observed} | {status} |"
        )
    lines.append("")
    lines.append("Missingness by column, in the validated sample:")
    lines.append("")
    lines.append("| Column | Missing fraction |")
    lines.append("| --- | --- |")
    for name, fraction in validation.missingness_by_column.items():
        lines.append(f"| {name} | {fraction:.4f} |")
    lines.append("")

    lines.append("## Lineage & Access")
    lines.append("")
    lines.append(lineage_access)
    lines.append(f"- Refresh schedule: {refresh_schedule}")
    lines.append("")

    lines.append("## Change Policy")
    lines.append("")
    lines.append(change_policy)
    lines.append("")

    return "\n".join(lines)
