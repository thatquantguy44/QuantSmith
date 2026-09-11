"""Validation helpers for spec 0072's credit risk domain pack.

The module validates the committed knowledge contracts under
``knowledge/credit_risk`` and runs the small golden-case operations that future
credit runtimes must preserve. It deliberately exposes no scoring, provisioning,
capital, or underwriting API: nothing here decides anything about an obligor or
an applicant.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import json
import re
from typing import Any, Dict, List, Mapping, Sequence


PACK_DIR = Path("knowledge/credit_risk")
SOURCE_DIR = Path("sources")

ALLOWED_RECORD_TYPES = {
    "concept",
    "convention",
    "lifecycle",
    "capability",
    "golden_case",
    "decision_path",
    "governance_artifact",
    "workflow",
}
# Extends 0063's enum with the two credit-specific classes: an accounting
# standard and a supervisory rule have different freshness and effective-date
# behaviour from a market observation and must not share a class.
ALLOWED_KNOWLEDGE_CLASSES = {
    "stable_mechanic",
    "contractual_convention",
    "accounting_standard",
    "regulatory_supervisory_rule",
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
    "el_pd_lgd_ead",
    "ead_from_ccf",
    "ecl_lifetime_eir",
    "rwa_from_risk_weight",
    "score_points_to_odds",
    "adverse_action_ranking",
    "migration_matrix_rows",
    "point_in_time_admission",
    "adverse_impact_ratio",
}

REQUIRED_CAPABILITY_DOMAINS = {
    "wholesale_rating_pd_lgd_ead",
    "counterparty_exposure_limits_concentration",
    "retail_scoring_underwriting",
    "ifrs9_cecl_expected_credit_loss",
    "basel_irb_regulatory_capital",
    "supervisory_stress_capital_planning",
    "credit_document_intelligence",
    "credit_model_governance_monitoring",
}

# Obligations that attach to a decision about an identifiable consumer
# (0072 REQ-014). The unsafe configuration is unrepresentable rather than
# discouraged: a consumer path that misses any of these is only valid when it
# also forbids sole-basis adverse action.
CONSUMER_DECISION_OBLIGATIONS = (
    "reason_codes",
    "policy_version_field",
    "cutoff_field",
    "override_log_ref",
    "disparate_impact_hook",
)

# 0072 REQ-020. Attribute absence (REQ-014) is necessary but not sufficient:
# disparate impact arises from facially neutral features that correlate with
# protected class, so a contract that only checks a feature list certifies
# nothing. These are the substantive obligations.
FAIRNESS_TESTING_OBLIGATIONS = (
    "protected_class_basis",
    "disparity_metric",
    "disparity_threshold_param",
    "feature_proxy_association_recorded",
    "less_discriminatory_alternative",
)

REQUIRED_GOVERNANCE_ARTIFACTS = {
    "gov.model_card",
    "gov.independent_validation",
    "gov.challenger_comparison",
    "gov.monitoring_plan",
    "gov.override_log",
    "gov.owner",
    "gov.kill_switch",
}

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class CreditRiskValidationError(ValueError):
    """Raised when the 0072 credit risk pack is structurally invalid."""


@dataclass(frozen=True)
class ValidationReport:
    """Result of validating the credit risk pack."""

    errors: tuple[str, ...]
    counts: Mapping[str, int]

    @property
    def ok(self) -> bool:
        return not self.errors

    def raise_if_errors(self) -> None:
        if self.errors:
            joined = "\n".join(f"- {error}" for error in self.errors)
            raise CreditRiskValidationError(joined)


def repository_root() -> Path:
    """Return the source checkout root for tests and local CLI use."""

    return Path(__file__).resolve().parents[3]


def load_json(path: Path) -> Any:
    """Load JSON with a path-rich failure message."""

    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise CreditRiskValidationError(f"{path}: invalid JSON: {exc}") from exc


def load_domain_pack(root: Path | None = None) -> Dict[str, Any]:
    """Load the 0072 machine-readable artifacts from a checkout root."""

    root = root or repository_root()
    pack = root / PACK_DIR
    return {
        "taxonomy": load_json(pack / "taxonomy.json"),
        "conventions": load_json(pack / "conventions.json"),
        "lifecycles": load_json(pack / "lifecycles.json"),
        "decision_paths": load_json(pack / "decision_paths.json"),
        "governance": load_json(pack / "governance.json"),
        "workflows": load_json(pack / "workflows.json"),
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
        match = re.search(
            r'^source_id:\s*"?([^"\n#]+)"?', path.read_text(encoding="utf-8"), re.M
        )
        if match:
            ids.add(match.group(1).strip())
    return ids


def all_records(pack: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    """Flatten top-level machine-readable records across pack files."""

    records: List[Mapping[str, Any]] = []
    records.extend(pack["taxonomy"].get("concepts", []))
    records.extend(pack["conventions"].get("conventions", []))
    records.extend(pack["lifecycles"].get("lifecycles", []))
    records.extend(pack["decision_paths"].get("decision_paths", []))
    records.extend(pack["governance"].get("required_artifacts", []))
    records.extend(pack["workflows"].get("workflows", []))
    records.extend(pack["coverage"].get("capabilities", []))
    records.extend(pack["golden_cases"].get("golden_cases", []))
    return records


def _date(value: str, field: str) -> date:
    if not _ISO_DATE.match(str(value)):
        raise CreditRiskValidationError(f"{field}: expected ISO date, got {value!r}")
    return date.fromisoformat(str(value))


def _validate_common_records(
    records: Sequence[Mapping[str, Any]],
    sources: set[str],
    errors: List[str],
    *,
    blocking_gap_ids: set[str] = frozenset(),
) -> None:
    seen: set[str] = set()
    for record in records:
        rid = record.get("id")
        if not rid:
            errors.append("record without an id")
            continue
        if rid in seen:
            errors.append(f"{rid}: duplicate record id")
        seen.add(rid)

        if record.get("record_type") not in ALLOWED_RECORD_TYPES:
            errors.append(f"{rid}: unknown record_type {record.get('record_type')!r}")
        if record.get("knowledge_class") not in ALLOWED_KNOWLEDGE_CLASSES:
            errors.append(f"{rid}: unknown knowledge_class {record.get('knowledge_class')!r}")
        status = record.get("review_status")
        if status not in ALLOWED_REVIEW_STATUSES:
            errors.append(f"{rid}: unknown review_status {status!r}")
        if not record.get("jurisdiction"):
            errors.append(f"{rid}: jurisdiction must be declared, never inferred")

        try:
            _date(str(record.get("knowledge_as_of")), "knowledge_as_of")
        except CreditRiskValidationError as exc:
            errors.append(f"{rid}: {exc}")

        eff_from, eff_to = record.get("effective_from"), record.get("effective_to")
        if eff_from is not None and eff_to is not None:
            try:
                if _date(str(eff_from), "effective_from") >= _date(str(eff_to), "effective_to"):
                    errors.append(f"{rid}: effective_from must precede effective_to")
            except CreditRiskValidationError as exc:
                errors.append(f"{rid}: {exc}")

        for ref in record.get("source_refs", []):
            if ref not in sources:
                errors.append(f"{rid}: source_ref {ref!r} is not registered under sources/")

        # Promotion gate (0072 REQ-019): reviewed requires a named reviewer,
        # date, and scope. Automation cannot self-certify credit correctness.
        blocked_by = set(record.get("blocked_by_gap_ids", []))
        if status == "reviewed":
            review = record.get("review")
            if not isinstance(review, Mapping):
                errors.append(f"{rid}: review_status 'reviewed' requires a review object")
            else:
                for field in ("reviewer", "review_date", "scope"):
                    if not review.get(field):
                        errors.append(f"{rid}: reviewed record missing review.{field}")
                reviewer = str(review.get("reviewer", ""))
                if "@" in reviewer:
                    errors.append(f"{rid}: reviewer must be a handle, not an email address")
            if not record.get("source_refs"):
                errors.append(f"{rid}: reviewed record must cite at least one source")
            # A record naming a gap that is still open, high-severity, and
            # declared to affect it cannot be reviewed regardless of how
            # complete its review object looks -- a named reviewer is
            # necessary, not sufficient (0072 REQ-019).
            still_blocking = blocked_by & blocking_gap_ids
            if still_blocking:
                errors.append(
                    f"{rid}: cannot be reviewed while {sorted(still_blocking)} remain open "
                    "and high-severity"
                )


def _validate_taxonomy(taxonomy: Mapping[str, Any], errors: List[str]) -> set[str]:
    concepts = taxonomy.get("concepts", [])
    ids = {c["id"] for c in concepts if "id" in c}

    names: Dict[str, str] = {}
    alias_owner: Dict[str, str] = {}
    ambiguous = {
        normalize_alias(rule["alias"])
        for rule in taxonomy.get("ambiguity_rules", [])
        if rule.get("alias")
    }

    for concept in concepts:
        cid = concept.get("id", "<no id>")
        name = normalize_alias(str(concept.get("name", "")))
        if name in names:
            errors.append(f"{cid}: preferred name collides with {names[name]}")
        names[name] = cid
        for alias in concept.get("aliases", []):
            key = normalize_alias(alias)
            if key in ambiguous:
                # Deliberately shared: an ambiguity rule governs resolution.
                continue
            if key in alias_owner and alias_owner[key] != cid:
                errors.append(
                    f"{cid}: alias {alias!r} also resolves to {alias_owner[key]}; "
                    "add an ambiguity rule or rename"
                )
            alias_owner[key] = cid
        for ref in list(concept.get("parent_ids", [])) + list(concept.get("related_ids", [])):
            if ref not in ids:
                errors.append(f"{cid}: references unknown concept {ref!r}")

    for rule in taxonomy.get("ambiguity_rules", []):
        for cid in rule.get("allowed_concept_ids", []):
            if cid not in ids:
                errors.append(f"ambiguity rule {rule.get('alias')!r}: unknown concept {cid!r}")
        if not rule.get("requires"):
            errors.append(f"ambiguity rule {rule.get('alias')!r}: must state what it requires")

    # Non-interchangeable sets: distinct ids, and no shared alias between them.
    for pair in taxonomy.get("non_interchangeable_pairs", []):
        if len(pair) != 2:
            errors.append(f"non_interchangeable_pairs: expected a pair, got {pair!r}")
            continue
        left, right = pair
        if left == right:
            errors.append(f"non_interchangeable_pairs: {left!r} paired with itself")
        for cid in pair:
            if cid not in ids:
                errors.append(f"non_interchangeable_pairs: unknown concept {cid!r}")
        by_id = {c["id"]: c for c in concepts if "id" in c}
        if left in by_id and right in by_id:
            la = {normalize_alias(a) for a in by_id[left].get("aliases", [])} - ambiguous
            ra = {normalize_alias(a) for a in by_id[right].get("aliases", [])} - ambiguous
            shared = la & ra
            if shared:
                errors.append(
                    f"non_interchangeable_pairs: {left} and {right} share alias(es) "
                    f"{sorted(shared)}; distinct concepts must not be reachable by one name"
                )
    return ids


def _validate_conventions(
    conventions: Mapping[str, Any], concept_ids: set[str], errors: List[str]
) -> set[str]:
    ids: set[str] = set()
    for conv in conventions.get("conventions", []):
        cid = conv.get("id", "<no id>")
        ids.add(cid)
        for field in ("unit", "quantity"):
            if not conv.get(field):
                errors.append(f"{cid}: convention must declare {field}")
        if not conv.get("viewpoint_ids"):
            errors.append(f"{cid}: convention must declare at least one viewpoint")
        for vid in conv.get("viewpoint_ids", []):
            if vid not in concept_ids:
                errors.append(f"{cid}: unknown viewpoint {vid!r}")
        ddid = conv.get("default_definition_id")
        if ddid is not None and ddid not in concept_ids:
            errors.append(f"{cid}: unknown default_definition_id {ddid!r}")

        # A measure that can produce a loss number must say which way it points.
        if conv.get("quantity") in {"expected_loss", "expected_credit_loss",
                                    "loss_given_default"}:
            if conv.get("loss_sign") in (None, "", "not_applicable"):
                errors.append(f"{cid}: loss-bearing quantity must declare a loss_sign")

        # 0072 AC-013: no institution- or policy-specific value may be a
        # hard-coded constant. A required parameter with a default is exactly
        # that, wearing a parameter's clothes.
        for param in conv.get("parameters", []):
            if not param.get("id"):
                errors.append(f"{cid}: parameter without an id")
            if param.get("required") and param.get("default") is not None:
                errors.append(
                    f"{cid}: parameter {param.get('id')!r} is required but carries a "
                    "default; an institution-specific value must not be supplied by "
                    "this pack"
                )
            if not param.get("rationale"):
                errors.append(f"{cid}: parameter {param.get('id')!r} must state a rationale")
    return ids


def _validate_lifecycles(lifecycles: Mapping[str, Any], errors: List[str]) -> set[str]:
    ids: set[str] = set()
    for graph in lifecycles.get("lifecycles", []):
        gid = graph.get("id", "<no id>")
        ids.add(gid)
        state_ids = {s["id"] for s in graph.get("states", []) if "id" in s}
        initial = list(graph.get("initial_state_ids", []))
        terminal = list(graph.get("terminal_state_ids", []))

        if not initial:
            errors.append(f"{gid}: no initial state")
        for sid in initial + terminal:
            if sid not in state_ids:
                errors.append(f"{gid}: unknown state {sid!r} in initial/terminal list")
        if not terminal:
            errors.append(f"{gid}: terminal states must be explicit")

        for trans in graph.get("transitions", []):
            tid = trans.get("id", "<no id>")
            for end in ("from", "to"):
                if trans.get(end) not in state_ids:
                    errors.append(f"{gid}/{tid}: unknown {end} state {trans.get(end)!r}")
            if not trans.get("initiating_role_id"):
                errors.append(f"{gid}/{tid}: transition must name its initiating role")
            if not trans.get("produces_artifact"):
                errors.append(f"{gid}/{tid}: transition must name the artifact it produces")

        reachable = set(initial)
        stack = list(initial)
        while stack:
            current = stack.pop()
            for trans in graph.get("transitions", []):
                if trans.get("from") == current and trans.get("to") not in reachable:
                    reachable.add(trans["to"])
                    stack.append(trans["to"])
        unreachable = state_ids - reachable
        if unreachable:
            errors.append(f"{gid}: unreachable states {sorted(unreachable)}")

        for sid in terminal:
            outgoing = [
                t for t in graph.get("transitions", [])
                if t.get("from") == sid and t.get("to") != sid
            ]
            if outgoing:
                errors.append(f"{gid}: terminal state {sid!r} has outgoing transitions")
    return ids


def transition_allowed(graph: Mapping[str, Any], from_state: str, to_state: str) -> bool:
    """Return whether a transition is declared. Undeclared means rejected."""

    return any(
        t.get("from") == from_state and t.get("to") == to_state
        for t in graph.get("transitions", [])
    )


def _validate_decision_paths(
    decision_paths: Mapping[str, Any], errors: List[str]
) -> set[str]:
    """Enforce 0072 REQ-014: the unsafe consumer configuration is unrepresentable."""

    ids: set[str] = set()
    protected = set(
        decision_paths.get("protected_attribute_registry", {}).get("attribute_ids", [])
    )
    for path in decision_paths.get("decision_paths", []):
        pid = path.get("id", "<no id>")
        ids.add(pid)
        if not path.get("rationale"):
            errors.append(f"{pid}: decision path must state a rationale")

        leaked = set(path.get("protected_attributes_in_features", []))
        if leaked:
            errors.append(
                f"{pid}: protected attribute(s) {sorted(leaked)} present in the feature "
                "set; protected attributes are for segregated fairness testing only"
            )
        unknown = leaked - protected
        if unknown:
            errors.append(f"{pid}: unregistered protected attribute(s) {sorted(unknown)}")

        if not path.get("consumer_decision"):
            continue

        unmet = [
            field for field in CONSUMER_DECISION_OBLIGATIONS if not path.get(field)
        ]
        reasons = path.get("reason_codes")
        if isinstance(reasons, Mapping):
            if not reasons.get("derivable"):
                unmet.append("reason_codes.derivable")
            if not reasons.get("excludes_protected_attributes"):
                unmet.append("reason_codes.excludes_protected_attributes")

        fairness = path.get("fairness_testing")
        if not isinstance(fairness, Mapping):
            unmet.append("fairness_testing")
        else:
            for field in FAIRNESS_TESTING_OBLIGATIONS:
                if not fairness.get(field):
                    unmet.append(f"fairness_testing.{field}")
            if not fairness.get("measured_at_applied_cutoff"):
                unmet.append("fairness_testing.measured_at_applied_cutoff")
            if fairness.get("protected_class_basis") == "estimated":
                if not fairness.get("estimation_method_param"):
                    unmet.append("fairness_testing.estimation_method_param")
                if not fairness.get("estimation_limitations_recorded"):
                    unmet.append("fairness_testing.estimation_limitations_recorded")
                # An estimate of a protected attribute is a protected attribute
                # for feature purposes: admissible for testing, never as input.
                if fairness.get("estimation_use") != "testing_only":
                    errors.append(
                        f"{pid}: a protected-class estimate may be used for testing only, "
                        f"never as a model feature"
                    )
            lda = fairness.get("less_discriminatory_alternative")
            if isinstance(lda, Mapping):
                if not lda.get("required_when"):
                    unmet.append("fairness_testing.less_discriminatory_alternative.required_when")
                if not lda.get("outcome_required"):
                    unmet.append("fairness_testing.less_discriminatory_alternative.outcome_required")

        if unmet and path.get("sole_basis_adverse_action_permitted"):
            errors.append(
                f"{pid}: consumer decision path is missing {sorted(set(unmet))} yet permits "
                "sole-basis adverse action; it must be restated as decision_support_only "
                "with sole_basis_adverse_action_permitted false"
            )
    return ids


def _validate_governance(governance: Mapping[str, Any], errors: List[str]) -> None:
    present = {a.get("id") for a in governance.get("required_artifacts", [])}
    missing = REQUIRED_GOVERNANCE_ARTIFACTS - present
    if missing:
        errors.append(f"governance: missing required artifact(s) {sorted(missing)}")
    for artifact in governance.get("required_artifacts", []):
        if not artifact.get("why"):
            errors.append(f"{artifact.get('id')}: governance artifact must state why")

    predicate = governance.get("deployability_predicate", {})
    if not predicate.get("computed_not_asserted"):
        errors.append(
            "governance: deployability must be computed from resolving artifacts, "
            "never asserted by a field"
        )
    admission = governance.get("evidence_admission", {})
    if admission.get("automated_promotion_permitted"):
        errors.append(
            "governance: automated promotion of derived evidence to a decision input "
            "is prohibited by 0072 REQ-016"
        )
    if admission.get("initial_evidence_class") != "derived_evidence":
        errors.append("governance: LLM-derived values must start as derived_evidence")


def is_deployable(
    entry: Mapping[str, Any],
    governance: Mapping[str, Any],
    decision_paths: Mapping[str, Any],
    open_high_gap_ids: Sequence[str] = (),
) -> bool:
    """Compute deployability. There is deliberately no ``deployable`` field."""

    resolved = {a.get("artifact_id") for a in entry.get("governance_evidence", [])}
    if not REQUIRED_GOVERNANCE_ARTIFACTS.issubset(resolved):
        return False
    if set(entry.get("open_high_gap_ids", [])) & set(open_high_gap_ids):
        return False

    path_id = entry.get("decision_path_id")
    if path_id:
        paths = {p["id"]: p for p in decision_paths.get("decision_paths", [])}
        path = paths.get(path_id)
        if path is None:
            return False
        if path.get("consumer_decision"):
            if any(not path.get(field) for field in CONSUMER_DECISION_OBLIGATIONS):
                return False
            if path.get("protected_attributes_in_features"):
                return False
            fairness = path.get("fairness_testing")
            if not isinstance(fairness, Mapping):
                return False
            if any(not fairness.get(f) for f in FAIRNESS_TESTING_OBLIGATIONS):
                return False
    return True


def admit_derived_evidence(
    value: Mapping[str, Any], governance: Mapping[str, Any]
) -> Dict[str, Any]:
    """Admit an LLM-derived value, or say exactly why it cannot be admitted."""

    rule = governance.get("evidence_admission", {})
    required = rule.get("requires", {})
    missing = [field for field in required if not value.get(field)]
    if missing:
        return {"admitted": False, "evidence_class": None, "missing": sorted(missing)}

    review = value.get("review")
    promoted = bool(
        isinstance(review, Mapping)
        and review.get("reviewer")
        and review.get("review_date")
        and review.get("scope")
    )
    return {
        "admitted": True,
        "evidence_class": "decision_input" if promoted else "derived_evidence",
        "missing": [],
    }


def _validate_workflows(
    workflows: Mapping[str, Any],
    decision_path_ids: set[str],
    errors: List[str],
) -> None:
    levels = set(workflows.get("runtime_boundary_levels", {}))
    for flow in workflows.get("workflows", []):
        wid = flow.get("id", "<no id>")
        for field in ("stages", "required_inputs", "produced_artifacts", "gates",
                      "human_decision_points", "participating_agents"):
            if not flow.get(field):
                errors.append(f"{wid}: workflow must enumerate {field}")
        if flow.get("decision_path_id") not in decision_path_ids:
            errors.append(f"{wid}: unknown decision_path_id {flow.get('decision_path_id')!r}")
        if flow.get("runtime_boundary") not in levels:
            errors.append(f"{wid}: unknown runtime_boundary {flow.get('runtime_boundary')!r}")
        for agent in flow.get("participating_agents", []):
            status = agent.get("status")
            if status not in {"existing", "future"}:
                errors.append(f"{wid}: agent {agent.get('agent_id')!r} has unknown status")
            if status == "future" and not agent.get("owning_spec"):
                errors.append(
                    f"{wid}: future agent {agent.get('agent_id')!r} must name its owning spec"
                )


def _validate_coverage(coverage: Mapping[str, Any], root: Path, errors: List[str]) -> None:
    domains: set[str] = set()
    for cap in coverage.get("capabilities", []):
        cid = cap.get("id", "<no id>")
        domains.add(cap.get("domain"))
        level = cap.get("coverage_level")
        if level not in ALLOWED_COVERAGE_LEVELS:
            errors.append(f"{cid}: unknown coverage_level {level!r}")
        for field in ("scope", "limitation", "owning_spec"):
            if not cap.get(field):
                errors.append(f"{cid}: capability must declare {field}")
        if not cap.get("current_artifacts"):
            errors.append(f"{cid}: capability must name its current artifacts")
        for artifact in cap.get("current_artifacts", []):
            if not (root / artifact).exists():
                errors.append(f"{cid}: artifact {artifact!r} does not exist")
        # A runtime claim needs a runtime. Saying so is the point of the level.
        if level in {"reference_runtime", "validated_runtime"}:
            if not any(a.endswith(".py") for a in cap.get("current_artifacts", [])):
                errors.append(
                    f"{cid}: coverage_level {level!r} claimed without a named runtime module"
                )
    missing = REQUIRED_CAPABILITY_DOMAINS - domains
    if missing:
        errors.append(f"coverage: required domain(s) not covered: {sorted(missing)}")


def parse_gap_register(root: Path | None = None) -> List[Dict[str, str]]:
    """Parse gap_register.md into structured rows.

    A gap is considered OPEN unless its disposition explicitly states
    resolution — starting with "Resolved" or "**Corrected" (bold, matching
    this pack's own convention for a closed gap). Anything else, including
    "Assigned" or "Open", is open. This is deliberately conservative: an
    ambiguous disposition is treated as still blocking, never as silently
    resolved.
    """

    root = root or repository_root()
    path = root / PACK_DIR / "gap_register.md"
    text = path.read_text(encoding="utf-8")
    rows = re.findall(r"^\| (G-0072-\d{3}) \|(.+)$", text, re.M)
    parsed: List[Dict[str, str]] = []
    for gap_id, rest in rows:
        cells = [c.strip() for c in rest.split("|")]
        if len(cells) < 6:
            continue
        gap, evidence, severity, affected, disposition, owner = cells[:6]
        disposition_stripped = disposition.lstrip("*").strip()
        closed = disposition_stripped.lower().startswith(("resolved", "corrected"))
        parsed.append(
            {
                "id": gap_id, "gap": gap, "evidence": evidence,
                "severity": severity.lower(), "affected": affected,
                "disposition": disposition, "owner": owner,
                "status": "closed" if closed else "open",
            }
        )
    return parsed


def high_severity_open_gap_ids(root: Path | None = None) -> set[str]:
    """Return the IDs of gaps that are both high-severity and still open."""

    return {
        row["id"] for row in parse_gap_register(root)
        if row["severity"] == "high" and row["status"] == "open"
    }


def _validate_gap_register(root: Path, errors: List[str]) -> None:
    path = root / PACK_DIR / "gap_register.md"
    if not path.exists():
        errors.append("gap_register.md is missing")
        return
    text = path.read_text(encoding="utf-8")
    rows = re.findall(r"^\| (G-0072-\d{3}) \|(.+)$", text, re.M)
    if not rows:
        errors.append("gap_register.md: no gap rows found")
    for gap_id, rest in rows:
        # Columns after the id: gap, evidence, severity, affected, disposition, owner.
        cells = [c.strip() for c in rest.split("|")]
        if len(cells) < 6:
            errors.append(f"{gap_id}: gap row must carry evidence, severity, disposition, owner")
            continue
        gap, evidence, severity, _affected, disposition, owner = cells[:6]
        if severity.lower() not in {"high", "medium", "low"}:
            errors.append(f"{gap_id}: unknown severity {severity!r}")
        if not gap or not evidence:
            errors.append(f"{gap_id}: gap row must describe the gap and cite evidence")
        if not disposition or not owner:
            errors.append(f"{gap_id}: gap row must state a disposition and an owner")


def _validate_golden_cases(
    golden: Mapping[str, Any], convention_ids: set[str], errors: List[str]
) -> None:
    rule_ids = {r["id"] for r in golden.get("point_in_time_rules", [])}
    if not rule_ids:
        errors.append("golden_cases.json: point_in_time_rules must be declared")
    for case in golden.get("golden_cases", []):
        cid = case.get("case_id", "<no id>")
        if case.get("operation") not in ALLOWED_GOLDEN_OPERATIONS:
            errors.append(f"{cid}: unknown operation {case.get('operation')!r}")
        if not case.get("invariants"):
            errors.append(f"{cid}: golden case must state its invariants")
        for conv_id in case.get("convention_ids", []):
            if conv_id not in convention_ids:
                errors.append(f"{cid}: unknown convention {conv_id!r}")
        for name, spec in case.get("inputs", {}).items():
            if "unit" not in spec:
                errors.append(f"{cid}: input {name!r} must declare a unit")
        for name, spec in case.get("expected_outputs", {}).items():
            if "unit" not in spec:
                errors.append(f"{cid}: output {name!r} must declare a unit")
        expected = case.get("expected_outputs", {}).get("violated_rules")
        if expected:
            for rule in expected.get("value", []):
                if rule not in rule_ids and not rule.startswith("rule.basis."):
                    errors.append(f"{cid}: references unknown rule {rule!r}")


def validate_domain_pack(root: Path | None = None) -> ValidationReport:
    """Validate structure, references, temporal fields, contracts, and cases."""

    root = root or repository_root()
    pack = load_domain_pack(root)
    sources = registered_source_ids(root)
    records = all_records(pack)
    errors: List[str] = []
    blocking_gap_ids = high_severity_open_gap_ids(root)

    _validate_common_records(records, sources, errors, blocking_gap_ids=blocking_gap_ids)
    concept_ids = _validate_taxonomy(pack["taxonomy"], errors)
    convention_ids = _validate_conventions(pack["conventions"], concept_ids, errors)
    _validate_lifecycles(pack["lifecycles"], errors)
    path_ids = _validate_decision_paths(pack["decision_paths"], errors)
    _validate_governance(pack["governance"], errors)
    _validate_workflows(pack["workflows"], path_ids, errors)
    _validate_coverage(pack["coverage"], root, errors)
    _validate_gap_register(root, errors)
    _validate_golden_cases(pack["golden_cases"], convention_ids, errors)

    # Every golden case must actually run and reproduce its expected outputs.
    for case in pack["golden_cases"].get("golden_cases", []):
        try:
            run_golden_case(case)
        except CreditRiskValidationError as exc:
            errors.append(str(exc))

    counts = {
        "records": len(records),
        "concepts": len(pack["taxonomy"].get("concepts", [])),
        "conventions": len(pack["conventions"].get("conventions", [])),
        "lifecycles": len(pack["lifecycles"].get("lifecycles", [])),
        "decision_paths": len(pack["decision_paths"].get("decision_paths", [])),
        "workflows": len(pack["workflows"].get("workflows", [])),
        "capabilities": len(pack["coverage"].get("capabilities", [])),
        "golden_cases": len(pack["golden_cases"].get("golden_cases", [])),
        "reviewed": sum(1 for r in records if r.get("review_status") == "reviewed"),
        "draft": sum(1 for r in records if r.get("review_status") == "draft"),
        "blocked_pending_gap": sum(1 for r in records if r.get("blocked_by_gap_ids")),
    }
    return ValidationReport(errors=tuple(errors), counts=counts)


def validate_or_raise(root: Path | None = None) -> ValidationReport:
    """Validate the pack and raise a compact error if anything fails."""

    report = validate_domain_pack(root)
    report.raise_if_errors()
    return report


def records_available_as_of(
    records: Sequence[Mapping[str, Any]], *, as_of: str, effective_date: str
) -> List[Mapping[str, Any]]:
    """Return records knowable as of one date and effective on another.

    Knowledge time is checked before effective time: a standard issued after the
    as-of date is excluded even when its effective interval covers the period
    being measured.
    """

    as_of_date = _date(as_of, "as_of")
    effective = _date(effective_date, "effective_date")
    admitted: List[Mapping[str, Any]] = []
    for record in records:
        if _date(str(record["knowledge_as_of"]), "knowledge_as_of") > as_of_date:
            continue
        eff_from = record.get("effective_from")
        eff_to = record.get("effective_to")
        if eff_from is not None and _date(str(eff_from), "effective_from") > effective:
            continue
        if eff_to is not None and _date(str(eff_to), "effective_to") <= effective:
            continue
        admitted.append(record)
    return admitted


# --------------------------------------------------------------------------
# Golden-case operations
#
# These exist to pin conventions, not to price or decide anything. Each is
# deterministic, takes its parameters as inputs, and supplies no institution-
# specific default.
# --------------------------------------------------------------------------


def _value(case: Mapping[str, Any], name: str) -> Any:
    inputs = case.get("inputs", {})
    if name not in inputs:
        raise CreditRiskValidationError(f"{case.get('case_id')}: missing input {name!r}")
    return inputs[name]["value"]


def expected_loss(pd: float, lgd: float, ead: float) -> float:
    """Expected loss. Operand basis compatibility is the caller's to establish."""

    return pd * lgd * ead


def ead_from_ccf(drawn_balance: float, limit: float, ccf: float) -> float:
    """Exposure at default from a drawn balance and a credit conversion factor."""

    if limit < drawn_balance:
        raise CreditRiskValidationError("limit must not be below the drawn balance")
    return drawn_balance + ccf * (limit - drawn_balance)


def lifetime_ecl(
    marginal_pd: Sequence[float],
    lgd: float,
    ead: Sequence[float],
    eir: float,
) -> Dict[str, float]:
    """Lifetime and twelve-month ECL discounted at the effective interest rate.

    Twelve-month ECL is the first discounted period of the same lifetime sum,
    not a separate twelve-month-horizon expected loss.
    """

    if len(marginal_pd) != len(ead):
        raise CreditRiskValidationError("marginal_pd and ead must be the same length")
    periods = [
        marginal_pd[i] * lgd * ead[i] / (1 + eir) ** (i + 1) for i in range(len(marginal_pd))
    ]
    return {
        "lifetime_ecl": sum(periods),
        "twelve_month_ecl": periods[0] if periods else 0.0,
        "period_contributions": periods,
    }


def rwa_from_risk_weight(risk_weight: float, ead: float) -> float:
    """Risk-weighted assets. The risk weight is supplied by the governing rule."""

    return risk_weight * ead


def score_points_to_odds(
    score: float, base_score: float, base_odds: float, pdo: float
) -> Dict[str, float]:
    """Convert a score to odds using institution-supplied scaling parameters."""

    if pdo == 0:
        raise CreditRiskValidationError("pdo must be non-zero")
    odds = base_odds * 2 ** ((score - base_score) / pdo)
    return {"odds": odds, "implied_probability_of_good": odds / (1.0 + odds)}


def adverse_action_reasons(
    feature_points: Mapping[str, float],
    max_attainable_points: Mapping[str, float],
    stable_feature_order: Sequence[str],
    max_reasons: int,
    protected_attributes: Sequence[str] = (),
) -> Dict[str, Any]:
    """Rank principal reasons deterministically, ties broken by declared order.

    Determinism is the requirement, not a nicety: two runs on the same
    application must disclose the same principal reasons, so ordering never
    depends on dictionary insertion or raw float comparison.
    """

    order = {name: i for i, name in enumerate(stable_feature_order)}
    unordered = set(feature_points) - set(order)
    if unordered:
        raise CreditRiskValidationError(
            f"features {sorted(unordered)} are absent from stable_feature_order; "
            "ordering would be non-deterministic"
        )
    leaked = set(feature_points) & set(protected_attributes)
    if leaked:
        raise CreditRiskValidationError(
            f"protected attribute(s) {sorted(leaked)} present among scored features"
        )

    points_lost = {
        name: max_attainable_points[name] - feature_points[name] for name in feature_points
    }
    ranked = sorted(points_lost, key=lambda name: (-points_lost[name], order[name]))
    return {
        "ordered_reason_codes": [f"reason.{name}" for name in ranked[:max_reasons]],
        "points_lost": points_lost,
    }


def migration_matrix_rows(
    grades: Sequence[str], matrix: Sequence[Sequence[float]], absorbing_state: str
) -> Dict[str, Any]:
    """Check the row-stochastic identity and that default absorbs."""

    if len(matrix) != len(grades):
        raise CreditRiskValidationError("matrix must have one row per grade")
    row_sums = [sum(row) for row in matrix]
    stochastic = all(abs(total - 1.0) <= 1e-12 for total in row_sums)
    index = grades.index(absorbing_state) if absorbing_state in grades else -1
    absorbs = index >= 0 and abs(matrix[index][index] - 1.0) <= 1e-12
    return {"row_sums": row_sums, "rows_stochastic": stochastic, "absorbing": absorbs}


def adverse_impact_ratio(
    approved_protected: float,
    total_protected: float,
    approved_reference: float,
    total_reference: float,
    disparity_threshold: float,
) -> Dict[str, Any]:
    """Disparity screen at the applied cutoff, against a supplied threshold.

    The threshold is an argument, never a constant here: the four-fifths ratio
    is a widely used screening convention, not a legal threshold and not a safe
    harbour. A breach says where to look; it is not a determination of
    lawfulness.
    """

    if total_protected <= 0 or total_reference <= 0:
        raise CreditRiskValidationError("group totals must be positive")
    rate_protected = approved_protected / total_protected
    rate_reference = approved_reference / total_reference
    if rate_reference == 0:
        raise CreditRiskValidationError("reference selection rate is zero; ratio undefined")
    ratio = rate_protected / rate_reference
    breached = ratio < disparity_threshold
    return {
        "adverse_impact_ratio": ratio,
        "selection_rate_protected": rate_protected,
        "selection_rate_reference": rate_reference,
        "threshold_breached": breached,
        # A breach obliges a recorded search outcome, not merely a warning.
        "less_discriminatory_alternative_required": breached,
    }


def point_in_time_admission(
    decision_date: str,
    feature_as_of: str,
    label_outcome_window_end: str,
    used_as: str,
) -> Dict[str, Any]:
    """Admit or reject a value, naming every rule it violates.

    Every violated rule is reported, not just the first: a rejection is meant to
    be diagnostic.
    """

    decision = _date(decision_date, "decision_date")
    as_of = _date(feature_as_of, "feature_as_of")
    window_end = _date(label_outcome_window_end, "label_outcome_window_end")
    violated: List[str] = []

    if used_as == "feature":
        if as_of > decision:
            violated.append("rule.pit.attribute_as_of")
        if window_end > decision:
            violated.append("rule.pit.outcome_window_alignment")
    elif used_as != "label":
        raise CreditRiskValidationError(f"unknown used_as {used_as!r}")

    return {"admitted": not violated, "violated_rules": violated}


def basis_compatible(pd_spec: Mapping[str, Any], lgd_spec: Mapping[str, Any]) -> List[str]:
    """Return the basis rules an expected-loss operand pair violates."""

    violated: List[str] = []
    same_horizon = pd_spec.get("horizon") == lgd_spec.get("horizon")
    same_defn = pd_spec.get("default_definition_id") == lgd_spec.get("default_definition_id")
    # A one-year PD with a workout-period LGD is the normal, correct pairing;
    # what must match is the default definition, and the horizon only where both
    # are stated on the same axis.
    if not same_defn:
        violated.append("rule.basis.el_operands")
    elif not same_horizon and lgd_spec.get("horizon") not in {"workout_period", None}:
        violated.append("rule.basis.el_operands")
    return violated


def run_golden_case(case: Mapping[str, Any]) -> Dict[str, Any]:
    """Run one golden case and verify it reproduces its expected outputs."""

    op = case.get("operation")
    cid = case.get("case_id", "<no id>")
    expected = case.get("expected_outputs", {})

    if op == "el_pd_lgd_ead":
        pd_spec = case["inputs"]["pd"]
        lgd_spec = case["inputs"]["lgd"]
        violated = basis_compatible(pd_spec, lgd_spec)
        if "admitted" in expected:
            actual = {"admitted": not violated, "violated_rules": violated}
        else:
            if violated:
                raise CreditRiskValidationError(
                    f"{cid}: operands violate {violated} but the case expects a value"
                )
            actual = {
                "expected_loss": expected_loss(
                    pd_spec["value"], lgd_spec["value"], _value(case, "ead")
                )
            }
    elif op == "ead_from_ccf":
        actual = {
            "ead": ead_from_ccf(
                _value(case, "drawn_balance"), _value(case, "limit"), _value(case, "ccf")
            )
        }
    elif op == "ecl_lifetime_eir":
        result = lifetime_ecl(
            _value(case, "marginal_pd"), _value(case, "lgd"),
            _value(case, "ead"), _value(case, "eir"),
        )
        actual = {
            "lifetime_ecl": result["lifetime_ecl"],
            "twelve_month_ecl": result["twelve_month_ecl"],
        }
    elif op == "rwa_from_risk_weight":
        actual = {"rwa": rwa_from_risk_weight(_value(case, "risk_weight"), _value(case, "ead"))}
    elif op == "score_points_to_odds":
        actual = score_points_to_odds(
            _value(case, "score"), _value(case, "base_score"),
            _value(case, "base_odds"), _value(case, "pdo"),
        )
    elif op == "adverse_action_ranking":
        actual = adverse_action_reasons(
            _value(case, "feature_points"), _value(case, "max_attainable_points"),
            _value(case, "stable_feature_order"), _value(case, "max_reasons"),
        )
    elif op == "migration_matrix_rows":
        result = migration_matrix_rows(
            _value(case, "grades"), _value(case, "matrix"), _value(case, "absorbing_state")
        )
        actual = {"row_sums": result["row_sums"], "rows_stochastic": result["rows_stochastic"]}
    elif op == "adverse_impact_ratio":
        actual = adverse_impact_ratio(
            _value(case, "approved_protected"), _value(case, "total_protected"),
            _value(case, "approved_reference"), _value(case, "total_reference"),
            _value(case, "disparity_threshold"),
        )
    elif op == "point_in_time_admission":
        actual = point_in_time_admission(
            _value(case, "decision_date"), _value(case, "feature_as_of"),
            _value(case, "label_outcome_window_end"), _value(case, "used_as"),
        )
    else:
        raise CreditRiskValidationError(f"{cid}: unknown operation {op!r}")

    _compare_expected(cid, expected, actual)
    return actual


def _compare_expected(
    cid: str, expected: Mapping[str, Any], actual: Mapping[str, Any]
) -> None:
    for name, spec in expected.items():
        if name not in actual:
            raise CreditRiskValidationError(f"{cid}: case produced no output named {name!r}")
        want, got = spec["value"], actual[name]
        tolerance = spec.get("tolerance")
        if isinstance(want, (int, float)) and not isinstance(want, bool):
            if abs(float(got) - float(want)) > (tolerance or 0.0):
                raise CreditRiskValidationError(
                    f"{cid}: {name} expected {want!r}, got {got!r}"
                )
        elif isinstance(want, Mapping):
            for key, sub in want.items():
                if abs(float(got[key]) - float(sub)) > (tolerance or 0.0):
                    raise CreditRiskValidationError(
                        f"{cid}: {name}[{key!r}] expected {sub!r}, got {got[key]!r}"
                    )
        elif isinstance(want, list) and want and isinstance(want[0], (int, float)):
            if len(want) != len(got):
                raise CreditRiskValidationError(f"{cid}: {name} length mismatch")
            for i, sub in enumerate(want):
                if abs(float(got[i]) - float(sub)) > (tolerance or 0.0):
                    raise CreditRiskValidationError(
                        f"{cid}: {name}[{i}] expected {sub!r}, got {got[i]!r}"
                    )
        elif want != got:
            raise CreditRiskValidationError(f"{cid}: {name} expected {want!r}, got {got!r}")


def run_golden_cases(root: Path | None = None) -> Dict[str, Any]:
    """Run every golden case and return deterministic outputs."""

    pack = load_domain_pack(root or repository_root())
    return {
        case["case_id"]: run_golden_case(case)
        for case in pack["golden_cases"].get("golden_cases", [])
    }


def main() -> int:
    """CLI entry point: validate the pack and print a one-line summary."""

    report = validate_domain_pack()
    if not report.ok:
        for error in report.errors:
            print(f"- {error}")
        print(f"credit-risk validation FAILED ({len(report.errors)} error(s))")
        return 1
    summary = ", ".join(f"{k}={v}" for k, v in sorted(report.counts.items()))
    print(f"credit-risk validation OK ({summary})")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI passthrough
    raise SystemExit(main())
