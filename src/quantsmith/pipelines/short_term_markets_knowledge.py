"""Validation helpers for spec 0063's short-term-markets domain pack.

The module validates the committed knowledge contracts under
``knowledge/short_term_markets`` and runs the small golden-case operations that
future runtimes must preserve. It deliberately exposes no pricing, trading,
allocation, or optimization API.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import json
import re
from typing import Any, Dict, Iterable, List, Mapping, Sequence


PACK_DIR = Path("knowledge/short_term_markets")
SOURCE_DIR = Path("sources")

ALLOWED_RECORD_TYPES = {
    "concept",
    "convention",
    "lifecycle",
    "capability",
    "golden_case",
}
ALLOWED_KNOWLEDGE_CLASSES = {
    "stable_mechanic",
    "contractual_convention",
    "regulatory_policy",
    "market_observation",
    "empirical_finding",
    "model_assumption",
}
ALLOWED_REVIEW_STATUSES = {"draft", "reviewed", "superseded", "retired"}
ALLOWED_COVERAGE_LEVELS = {
    "absent",
    "prose_only",
    "contract_only",
    "reference_runtime",
    "validated_runtime",
}
ALLOWED_GOLDEN_OPERATIONS = {
    "rate_difference_bps",
    "securities_lending_fee_rebate_signs",
    "tbill_discount_yield_to_price",
    "simple_accrual",
    "haircut_amount",
    "transition_allowed",
    "point_in_time_admission",
}

REQUIRED_CAPABILITY_DOMAINS = {
    "repo_reverse_repo",
    "securities_lending",
    "collateral_margin_substitution",
    "treasury_cash_products",
    "approved_cash_product_universe",
    "clearing_settlement_reporting_regulatory",
    "financing_portfolio_backtest_risk_liquidity_capacity",
}

REQUIRED_DISCREPANCY_IDS = {
    "D-0063-001",
    "D-0063-002",
    "D-0063-003",
    "D-0063-004",
    "D-0063-005",
    "D-0063-006",
}


class ShortTermMarketsValidationError(ValueError):
    """Raised when the 0063 domain pack is structurally invalid."""


@dataclass(frozen=True)
class ValidationReport:
    """Result of validating the short-term-markets pack."""

    errors: tuple[str, ...]
    counts: Mapping[str, int]

    @property
    def ok(self) -> bool:
        return not self.errors

    def raise_if_errors(self) -> None:
        if self.errors:
            joined = "\n".join(f"- {error}" for error in self.errors)
            raise ShortTermMarketsValidationError(joined)


def repository_root() -> Path:
    """Return the source checkout root for tests and local CLI use."""

    return Path(__file__).resolve().parents[3]


def load_json(path: Path) -> Any:
    """Load JSON with a path-rich failure message."""

    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise ShortTermMarketsValidationError(f"{path}: invalid JSON: {exc}") from exc


def load_domain_pack(root: Path | None = None) -> Dict[str, Any]:
    """Load the 0063 machine-readable artifacts from a checkout root."""

    root = root or repository_root()
    pack = root / PACK_DIR
    return {
        "taxonomy": load_json(pack / "taxonomy.json"),
        "conventions": load_json(pack / "conventions.json"),
        "lifecycles": load_json(pack / "lifecycles.json"),
        "coverage": load_json(pack / "coverage.json"),
        "golden_cases": load_json(pack / "golden_cases.json"),
    }


def normalize_alias(value: str) -> str:
    """Case-fold and punctuation-normalize an alias for deterministic lookup."""

    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def registered_source_ids(root: Path | None = None) -> set[str]:
    """Read source IDs from ``sources/*.yml`` without adding a YAML dependency."""

    root = root or repository_root()
    ids: set[str] = set()
    for path in (root / SOURCE_DIR).glob("*.yml"):
        match = re.search(r'^source_id:\s*"?([^"\n#]+)"?', path.read_text(encoding="utf-8"), re.M)
        if match:
            ids.add(match.group(1).strip())
    return ids


def all_records(pack: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    """Flatten top-level machine-readable records across pack files."""

    records: List[Mapping[str, Any]] = []
    records.extend(pack["taxonomy"].get("concepts", []))
    records.extend(pack["conventions"].get("conventions", []))
    records.extend(pack["lifecycles"].get("lifecycles", []))
    records.extend(pack["coverage"].get("capabilities", []))
    records.extend(pack["golden_cases"].get("golden_cases", []))
    return records


def validate_domain_pack(root: Path | None = None) -> ValidationReport:
    """Validate structure, references, temporal fields, and golden cases."""

    root = root or repository_root()
    pack = load_domain_pack(root)
    sources = registered_source_ids(root)
    records = all_records(pack)
    errors: List[str] = []

    _validate_common_records(records, sources, errors)
    concept_ids = _validate_taxonomy(pack["taxonomy"], errors)
    convention_ids = _validate_conventions(pack["conventions"], concept_ids, errors)
    lifecycle_ids = _validate_lifecycles(pack["lifecycles"], concept_ids, errors)
    _validate_coverage(pack["coverage"], concept_ids, root, errors)
    _validate_golden_cases(
        pack["golden_cases"],
        pack["lifecycles"],
        concept_ids,
        convention_ids,
        lifecycle_ids,
        errors,
    )
    _validate_handoff(root, errors)
    _validate_gap_register(root, errors)
    _validate_agent_links(root, errors)

    counts = {
        "records": len(records),
        "concepts": len(pack["taxonomy"].get("concepts", [])),
        "conventions": len(pack["conventions"].get("conventions", [])),
        "lifecycles": len(pack["lifecycles"].get("lifecycles", [])),
        "capabilities": len(pack["coverage"].get("capabilities", [])),
        "golden_cases": len(pack["golden_cases"].get("golden_cases", [])),
        "reviewed": sum(1 for record in records if record.get("review_status") == "reviewed"),
        "draft": sum(1 for record in records if record.get("review_status") == "draft"),
    }
    return ValidationReport(errors=tuple(errors), counts=counts)


def validate_or_raise(root: Path | None = None) -> ValidationReport:
    """Validate the pack and raise a compact error if anything fails."""

    report = validate_domain_pack(root)
    report.raise_if_errors()
    return report


def records_available_as_of(
    records: Sequence[Mapping[str, Any]],
    *,
    as_of: str,
    effective_date: str,
) -> List[Mapping[str, Any]]:
    """Return records knowable as of one date and effective on another."""

    as_of_date = _date(as_of, "as_of")
    effective = _date(effective_date, "effective_date")
    admitted = []
    for record in records:
        knowledge_as_of = _date(str(record["knowledge_as_of"]), "knowledge_as_of")
        if knowledge_as_of > as_of_date:
            continue
        effective_from = record.get("effective_from")
        effective_to = record.get("effective_to")
        if effective_from is not None and _date(str(effective_from), "effective_from") > effective:
            continue
        if effective_to is not None and _date(str(effective_to), "effective_to") <= effective:
            continue
        admitted.append(record)
    return admitted


def run_golden_cases(root: Path | None = None) -> Dict[str, Any]:
    """Run all allow-listed golden cases and return deterministic outputs."""

    root = root or repository_root()
    pack = load_domain_pack(root)
    results: Dict[str, Any] = {}
    lifecycles = {
        lifecycle["id"]: lifecycle
        for lifecycle in pack["lifecycles"].get("lifecycles", [])
    }
    for case in pack["golden_cases"].get("golden_cases", []):
        results[case["case_id"]] = run_golden_case(case, lifecycles)
    return results


def run_golden_case(
    case: Mapping[str, Any],
    lifecycles: Mapping[str, Mapping[str, Any]] | None = None,
) -> Any:
    """Run one allow-listed golden-case operation."""

    operation = str(case["operation"])
    inputs = case.get("inputs", {})
    if operation == "rate_difference_bps":
        return (float(inputs["gc_repo_rate"]["value"]) - float(inputs["specific_repo_rate"]["value"])) * 10_000.0
    if operation == "securities_lending_fee_rebate_signs":
        notional = float(inputs["notional"]["value"])
        fee_rate = float(inputs["borrow_fee_bps"]["value"]) / 10_000.0
        rebate_rate = float(inputs["rebate_bps"]["value"]) / 10_000.0
        days = float(inputs["days"]["value"])
        basis = float(inputs["day_count_basis"]["value"])
        fee = notional * fee_rate * days / basis
        rebate = notional * rebate_rate * days / basis
        return {
            "borrower_borrow_fee_cost": fee,
            "lender_borrow_fee_income": fee,
            "borrower_rebate_income": rebate,
            "lender_rebate_cost": rebate,
            "net_borrower_cost": fee - rebate,
        }
    if operation == "tbill_discount_yield_to_price":
        par = float(inputs["par"]["value"])
        discount_yield = float(inputs["discount_yield"]["value"])
        days = float(inputs["days_to_maturity"]["value"])
        basis = float(inputs["day_count_basis"]["value"])
        return par * (1.0 - discount_yield * days / basis)
    if operation == "simple_accrual":
        notional = float(inputs["notional"]["value"])
        rate = float(inputs["annual_rate"]["value"])
        days = float(inputs["days"]["value"])
        basis = float(inputs["day_count_basis"]["value"])
        return notional * rate * days / basis
    if operation == "haircut_amount":
        collateral_value = float(inputs["collateral_market_value"]["value"])
        haircut = float(inputs["haircut"]["value"])
        return {
            "haircut_amount": collateral_value * haircut,
            "max_cash_advance": collateral_value * (1.0 - haircut),
        }
    if operation == "transition_allowed":
        if lifecycles is None:
            raise ShortTermMarketsValidationError("transition_allowed needs lifecycle data")
        lifecycle = lifecycles[str(inputs["lifecycle_id"]["value"])]
        from_state = str(inputs["from_state"]["value"])
        event_id = str(inputs["event_id"]["value"])
        to_state = str(inputs["to_state"]["value"])
        return any(
            transition["event_id"] == event_id
            and transition["from_state_id"] == from_state
            and transition["to_state_id"] == to_state
            for transition in lifecycle.get("transitions", [])
        )
    if operation == "point_in_time_admission":
        records = inputs["records"]["value"]
        admitted = records_available_as_of(
            records,
            as_of=str(inputs["as_of"]["value"]),
            effective_date=str(inputs["effective_date"]["value"]),
        )
        admitted_ids = {str(record["id"]) for record in admitted}
        all_ids = {str(record["id"]) for record in records}
        return {
            "included_record_ids": sorted(admitted_ids),
            "excluded_record_ids": sorted(all_ids - admitted_ids),
        }
    raise ShortTermMarketsValidationError(f"unknown golden operation {operation!r}")


def _validate_common_records(
    records: Sequence[Mapping[str, Any]],
    sources: set[str],
    errors: List[str],
) -> None:
    seen: set[str] = set()
    for record in records:
        rid = str(record.get("id") or record.get("case_id") or "<missing-id>")
        for field in (
            "id",
            "record_type",
            "name",
            "jurisdiction",
            "knowledge_class",
            "knowledge_as_of",
            "effective_from",
            "effective_to",
            "source_refs",
            "review_status",
            "review",
            "supersedes",
        ):
            if field not in record:
                errors.append(f"{rid}: missing common field {field}")
        if rid in seen:
            errors.append(f"{rid}: duplicate record id")
        seen.add(rid)
        if record.get("record_type") not in ALLOWED_RECORD_TYPES:
            errors.append(f"{rid}: invalid record_type {record.get('record_type')!r}")
        if record.get("knowledge_class") not in ALLOWED_KNOWLEDGE_CLASSES:
            errors.append(f"{rid}: invalid knowledge_class {record.get('knowledge_class')!r}")
        if record.get("review_status") not in ALLOWED_REVIEW_STATUSES:
            errors.append(f"{rid}: invalid review_status {record.get('review_status')!r}")
        if record.get("jurisdiction") != "US":
            errors.append(f"{rid}: jurisdiction must be US for the initial pack")
        _validate_dates(record, rid, errors)
        _validate_source_refs(record, rid, sources, errors)
        validate_review_envelope(record, errors)


def validate_review_envelope(record: Mapping[str, Any], errors: List[str] | None = None) -> List[str]:
    """Validate review metadata for a proposed reviewed record."""

    local_errors: List[str] = [] if errors is None else errors
    rid = str(record.get("id") or record.get("case_id") or "<missing-id>")
    if record.get("review_status") != "reviewed":
        return local_errors
    review = record.get("review")
    if not isinstance(review, Mapping):
        local_errors.append(f"{rid}: reviewed record requires review object")
        return local_errors
    reviewer = str(review.get("reviewer") or "")
    if not reviewer or "@" in reviewer:
        local_errors.append(f"{rid}: reviewed record requires non-email reviewer handle")
    if not review.get("review_date"):
        local_errors.append(f"{rid}: reviewed record requires review_date")
    else:
        _date(str(review["review_date"]), f"{rid}.review_date")
    if not review.get("scope"):
        local_errors.append(f"{rid}: reviewed record requires review scope")
    if not review.get("evidence_refs"):
        local_errors.append(f"{rid}: reviewed record requires evidence_refs")
    if review.get("blocks_high_severity_discrepancy"):
        local_errors.append(f"{rid}: reviewed record is blocked by severity-high discrepancy")
    return local_errors


def _validate_dates(record: Mapping[str, Any], rid: str, errors: List[str]) -> None:
    try:
        _date(str(record["knowledge_as_of"]), f"{rid}.knowledge_as_of")
        effective_from = record.get("effective_from")
        effective_to = record.get("effective_to")
        if effective_from is not None:
            from_date = _date(str(effective_from), f"{rid}.effective_from")
        else:
            from_date = None
        if effective_to is not None:
            to_date = _date(str(effective_to), f"{rid}.effective_to")
        else:
            to_date = None
        if from_date is not None and to_date is not None and from_date >= to_date:
            errors.append(f"{rid}: effective_from must be before effective_to")
    except ValueError as exc:
        errors.append(str(exc))


def _validate_source_refs(
    record: Mapping[str, Any],
    rid: str,
    sources: set[str],
    errors: List[str],
) -> None:
    source_refs = record.get("source_refs")
    if not isinstance(source_refs, list):
        errors.append(f"{rid}: source_refs must be a list")
        return
    if not source_refs and record.get("knowledge_class") != "model_assumption":
        errors.append(f"{rid}: non-assumption record requires at least one source_ref")
    for ref in source_refs:
        ref_str = str(ref)
        if ref_str.startswith("source."):
            source_id = ref_str.split(".", 1)[1]
            if source_id not in sources:
                errors.append(f"{rid}: unresolved source_ref {ref_str}")
        elif not ref_str.startswith("assumption."):
            errors.append(f"{rid}: unsupported source_ref namespace {ref_str}")


def _validate_taxonomy(taxonomy: Mapping[str, Any], errors: List[str]) -> set[str]:
    concepts = taxonomy.get("concepts", [])
    concept_ids = {str(concept.get("id")) for concept in concepts}
    ambiguities = {
        normalize_alias(rule["alias"])
        for rule in taxonomy.get("ambiguity_rules", [])
        if "alias" in rule
    }
    alias_map: Dict[str, str] = {}
    preferred_names: set[str] = set()
    for concept in concepts:
        cid = str(concept.get("id"))
        if concept.get("record_type") != "concept":
            errors.append(f"{cid}: taxonomy records must have record_type concept")
        if not concept.get("kind"):
            errors.append(f"{cid}: concept kind is required")
        preferred = str(concept.get("name", ""))
        if preferred in preferred_names:
            errors.append(f"{cid}: duplicate preferred name {preferred!r}")
        preferred_names.add(preferred)
        for ref_field in ("parent_ids", "related_ids"):
            refs = concept.get(ref_field, [])
            if not isinstance(refs, list):
                errors.append(f"{cid}: {ref_field} must be a list")
                continue
            for ref in refs:
                if ref not in concept_ids:
                    errors.append(f"{cid}: unresolved {ref_field} reference {ref}")
        for alias in [preferred, *concept.get("aliases", [])]:
            normalized = normalize_alias(str(alias))
            existing = alias_map.get(normalized)
            if existing and existing != cid and normalized not in ambiguities:
                errors.append(f"{cid}: alias {alias!r} collides with {existing}")
            alias_map[normalized] = cid
    for left, right in taxonomy.get("non_interchangeable_pairs", []):
        if left not in concept_ids or right not in concept_ids:
            errors.append(f"non_interchangeable pair references unknown ids: {left}, {right}")
        if left == right:
            errors.append(f"non_interchangeable pair uses the same id twice: {left}")
    return concept_ids


def _validate_conventions(
    conventions: Mapping[str, Any],
    concept_ids: set[str],
    errors: List[str],
) -> set[str]:
    ids = set()
    for convention in conventions.get("conventions", []):
        cid = str(convention.get("id"))
        ids.add(cid)
        if convention.get("record_type") != "convention":
            errors.append(f"{cid}: convention records must have record_type convention")
        for field in (
            "quantity",
            "quote_style",
            "unit",
            "day_count",
            "compounding",
            "calendar",
            "business_day_adjustment",
            "settlement",
            "rounding",
            "viewpoint_ids",
            "formula",
        ):
            if field not in convention:
                errors.append(f"{cid}: missing convention field {field}")
        for role_id in convention.get("viewpoint_ids", []):
            if role_id not in concept_ids:
                errors.append(f"{cid}: unresolved viewpoint_id {role_id}")
        formula = convention.get("formula")
        if not isinstance(formula, Mapping) or not formula.get("id"):
            errors.append(f"{cid}: formula must declare an id")
        for threshold in convention.get("thresholds", []):
            basis = threshold.get("basis")
            if basis not in {"parameterized_model_assumption", "sourced_rule"}:
                errors.append(f"{cid}: threshold {threshold.get('name')} has invalid basis {basis!r}")
            if basis == "parameterized_model_assumption" and convention.get("knowledge_class") != "model_assumption":
                errors.append(f"{cid}: parameterized threshold must be a model_assumption")
            if basis == "sourced_rule" and not convention.get("source_refs"):
                errors.append(f"{cid}: sourced threshold requires source_refs")
    return ids


def _validate_lifecycles(
    lifecycles: Mapping[str, Any],
    concept_ids: set[str],
    errors: List[str],
) -> set[str]:
    ids = set()
    for lifecycle in lifecycles.get("lifecycles", []):
        lid = str(lifecycle.get("id"))
        ids.add(lid)
        if lifecycle.get("record_type") != "lifecycle":
            errors.append(f"{lid}: lifecycle records must have record_type lifecycle")
        state_ids = {state.get("id") for state in lifecycle.get("states", [])}
        initial_ids = set(lifecycle.get("initial_state_ids", []))
        terminal_ids = set(lifecycle.get("terminal_state_ids", []))
        if not initial_ids:
            errors.append(f"{lid}: at least one initial_state_id is required")
        if not terminal_ids:
            errors.append(f"{lid}: at least one terminal_state_id is required")
        for state_id in initial_ids | terminal_ids:
            if state_id not in state_ids:
                errors.append(f"{lid}: state reference {state_id} is not declared")
        outgoing: Dict[str, set[str]] = {str(state_id): set() for state_id in state_ids}
        for transition in lifecycle.get("transitions", []):
            from_state = transition.get("from_state_id")
            to_state = transition.get("to_state_id")
            event_id = transition.get("event_id")
            if from_state not in state_ids or to_state not in state_ids:
                errors.append(f"{lid}: transition {event_id} references unknown state")
            else:
                outgoing[str(from_state)].add(str(to_state))
            role_fields = [transition.get("initiating_role_id"), *transition.get("affected_role_ids", [])]
            for role_id in role_fields:
                if role_id not in concept_ids:
                    errors.append(f"{lid}: transition {event_id} references unknown role {role_id}")
            for field in ("preconditions", "cashflows", "security_movements", "margin_events"):
                if field not in transition:
                    errors.append(f"{lid}: transition {event_id} missing {field}")
        reachable = set(initial_ids)
        frontier = list(initial_ids)
        while frontier:
            current = frontier.pop()
            for next_state in outgoing.get(str(current), set()):
                if next_state not in reachable:
                    reachable.add(next_state)
                    frontier.append(next_state)
        unreachable = state_ids - reachable
        if unreachable:
            errors.append(f"{lid}: unreachable states {sorted(unreachable)}")
    return ids


def _validate_coverage(
    coverage: Mapping[str, Any],
    concept_ids: set[str],
    root: Path,
    errors: List[str],
) -> None:
    domains_seen = {
        capability.get("capability_domain")
        for capability in coverage.get("capabilities", [])
    }
    missing = REQUIRED_CAPABILITY_DOMAINS - domains_seen
    if missing:
        errors.append(f"coverage: missing required capability domains {sorted(missing)}")
    for capability in coverage.get("capabilities", []):
        cid = str(capability.get("id"))
        if capability.get("record_type") != "capability":
            errors.append(f"{cid}: coverage records must have record_type capability")
        if capability.get("coverage_level") not in ALLOWED_COVERAGE_LEVELS:
            errors.append(f"{cid}: invalid coverage_level {capability.get('coverage_level')!r}")
        if not capability.get("owner_spec"):
            errors.append(f"{cid}: owner_spec is required")
        if not capability.get("limitations"):
            errors.append(f"{cid}: limitations must be explicit")
        for product_id in capability.get("product_ids", []):
            if product_id not in concept_ids:
                errors.append(f"{cid}: unresolved product_id {product_id}")
        for path_value in [*capability.get("artifact_paths", []), *capability.get("test_paths", [])]:
            path = str(path_value).split(":", 1)[0]
            if path and not (root / path).exists():
                errors.append(f"{cid}: path does not exist: {path}")


def _validate_golden_cases(
    golden_cases: Mapping[str, Any],
    lifecycles: Mapping[str, Any],
    concept_ids: set[str],
    convention_ids: set[str],
    lifecycle_ids: set[str],
    errors: List[str],
) -> None:
    lifecycle_map = {
        lifecycle["id"]: lifecycle
        for lifecycle in lifecycles.get("lifecycles", [])
    }
    seen: set[str] = set()
    for case in golden_cases.get("golden_cases", []):
        case_id = str(case.get("case_id"))
        if case_id in seen:
            errors.append(f"{case_id}: duplicate case_id")
        seen.add(case_id)
        if case.get("id") != case_id:
            errors.append(f"{case_id}: id must equal case_id")
        if case.get("record_type") != "golden_case":
            errors.append(f"{case_id}: golden cases must have record_type golden_case")
        if case.get("operation") not in ALLOWED_GOLDEN_OPERATIONS:
            errors.append(f"{case_id}: operation is not allow-listed")
        for role_id in case.get("viewpoint_ids", []):
            if role_id not in concept_ids:
                errors.append(f"{case_id}: unresolved viewpoint_id {role_id}")
        for convention_id in case.get("convention_ids", []):
            if convention_id not in convention_ids:
                errors.append(f"{case_id}: unresolved convention_id {convention_id}")
        lifecycle_id = case.get("lifecycle_id")
        if lifecycle_id is not None and lifecycle_id not in lifecycle_ids:
            errors.append(f"{case_id}: unresolved lifecycle_id {lifecycle_id}")
        try:
            actual = run_golden_case(case, lifecycle_map)
        except Exception as exc:  # noqa: BLE001 - validation should report all bad cases.
            errors.append(f"{case_id}: golden case failed to run: {exc}")
            continue
        if not _matches_expected(actual, case.get("expected_outputs", {})):
            errors.append(f"{case_id}: golden output does not match expected")


def _validate_handoff(root: Path, errors: List[str]) -> None:
    text = (root / "docs/handoff.md").read_text(encoding="utf-8")
    for spec_id in ("0064", "0065", "0066", "0067", "0068", "0069"):
        if f"`{spec_id}`" not in text:
            errors.append(f"handoff: missing reserved child spec {spec_id}")
    for required in (
        "0063-short-term-markets-domain-foundation/",
        # 0063 was Draft at authoring time; it is now Approved (0072's owner
        # approved 0063/0070/0071/0072 together). This checks the CURRENT
        # activation state named in the handoff, not a frozen string — update
        # it again if 0063's status prose changes.
        "Approved and implemented (`0063`)",
        "Do not draft all six child specs at once",
    ):
        if required not in text:
            errors.append(f"handoff: missing required activation text {required!r}")

    next_spec = re.search(r"Next unreserved spec number: `(\d{4})`", text)
    if next_spec is None:
        errors.append("handoff: missing next unreserved spec number")
    else:
        next_spec_id = next_spec.group(1)
        if int(next_spec_id) <= 69:
            errors.append("handoff: next unreserved spec must follow reserved spec 0069")
        if any((root / "specs").glob(f"{next_spec_id}-*")):
            errors.append(
                f"handoff: next unreserved spec {next_spec_id} already has a spec directory"
            )


def _validate_gap_register(root: Path, errors: List[str]) -> None:
    text = (root / PACK_DIR / "gap_register.md").read_text(encoding="utf-8")
    for discrepancy_id in REQUIRED_DISCREPANCY_IDS:
        if discrepancy_id not in text:
            errors.append(f"gap_register: missing required discrepancy {discrepancy_id}")
    for field in ("Evidence", "Severity", "Disposition", "Owning spec"):
        if field not in text:
            errors.append(f"gap_register: missing field heading {field}")


def _validate_agent_links(root: Path, errors: List[str]) -> None:
    required_paths = (
        "instructions/securities_financing.md",
        "instructions/asset_class_mechanics.md",
        "agents/securities_financing/README.md",
        "agents/securities_financing/securities_lending/instructions.md",
        "agents/securities_financing/repo_financing/instructions.md",
        "agents/securities_financing/collateral_management/instructions.md",
        "agents/securities_financing/financing_cost_analysis/instructions.md",
        "agents/asset_classes/fixed_income_rates/instructions.md",
    )
    for path in required_paths:
        text = (root / path).read_text(encoding="utf-8")
        if "knowledge/short_term_markets/" not in text:
            errors.append(f"{path}: missing canonical short-term-markets pack link")
        if "instructions/short_term_markets.md" not in text:
            errors.append(f"{path}: missing short-term-markets instruction link")


def _matches_expected(actual: Any, expected_outputs: Mapping[str, Any]) -> bool:
    if isinstance(actual, Mapping):
        for key, expected in expected_outputs.items():
            if key not in actual:
                return False
            if not _value_matches(actual[key], expected):
                return False
        return True
    if "value" not in expected_outputs:
        return False
    return _value_matches(actual, expected_outputs["value"])


def _value_matches(actual: Any, expected: Mapping[str, Any]) -> bool:
    expected_value = expected.get("value")
    tolerance = float(expected.get("tolerance", 0.0) or 0.0)
    if isinstance(expected_value, list):
        return list(actual) == expected_value
    if isinstance(expected_value, bool):
        return bool(actual) is expected_value
    if isinstance(expected_value, str):
        return str(actual) == expected_value
    try:
        return abs(float(actual) - float(expected_value)) <= tolerance
    except (TypeError, ValueError):
        return actual == expected_value


def _date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field}: expected ISO date, got {value!r}") from exc


def _main() -> int:
    report = validate_domain_pack()
    if report.errors:
        for error in report.errors:
            print(error)
        return 1
    counts = ", ".join(f"{key}={value}" for key, value in sorted(report.counts.items()))
    print(f"short-term-markets validation OK ({counts})")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
