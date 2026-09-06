"""Typed orchestration evidence contracts for spec 0070.

The module is deliberately standard-library only. It records an agentic quant
run as JSON/JSONL artifacts and validates the fields that make prompt,
context, assumption, harness, audit, and replay evidence reviewable offline.

It does not call model providers, plugins, MCP servers, vector stores, or data
feeds. Those systems are represented through locators, hashes, metadata, and
fixtures so a reviewer can see what was available and what can be replayed.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION_RUN = "quantsmith.orchestration.run.v1"
SCHEMA_VERSION_PROMPT = "quantsmith.orchestration.prompt.v1"
SCHEMA_VERSION_CONTEXT = "quantsmith.orchestration.context.v1"
SCHEMA_VERSION_ASSUMPTION = "quantsmith.orchestration.assumption.v1"
SCHEMA_VERSION_EVALUATION = "quantsmith.orchestration.evaluation_harness.v1"
SCHEMA_VERSION_AUDIT_EVENT = "quantsmith.orchestration.audit_event.v1"

ACCESS_LEVELS = ("public", "internal", "restricted")
_ACCESS_RANK = {level: rank for rank, level in enumerate(ACCESS_LEVELS)}

ALLOWED_RUN_MODES = (
    "exploratory",
    "deterministic",
    "fixture_backed_llm",
    "external_provider",
)
ALLOWED_RELEASE_PROFILES = ("exploratory", "release_bound")
ALLOWED_REPLAY_MODES = ("deterministic", "fixture", "metadata_only")
ALLOWED_STATUSES = ("pass", "fail", "warn", "skipped")
ALLOWED_FRESHNESS = ("current", "stale", "expired", "excluded")
ALLOWED_CONFIDENCE = ("low", "medium", "high")
ALLOWED_ASSUMPTION_STATUSES = (
    "active",
    "accepted",
    "rejected",
    "superseded",
    "expired",
)
ALLOWED_ROLES = ("system", "developer", "user", "assistant", "tool", "safety")
ALLOWED_AUDIT_EVENT_TYPES = (
    "run_started",
    "prompt_render",
    "context_retrieval",
    "tool_plugin_call",
    "model_invocation",
    "data_source_read",
    "gate_result",
    "human_approval",
    "override",
    "rejected_alternative",
    "assumption_change",
    "replay_attempt",
    "release_decision",
    "run_completed",
)
REQUIRED_HARNESS_LAYERS = (
    "envelope",
    "prompt",
    "context",
    "assumptions",
    "tool_plugin_calls",
    "model_outputs",
    "quant_leakage",
    "final_artifact",
    "replay",
)
INTEGRATION_SURFACES = (
    "instructions/spec_driven_development.md",
    "instructions/reproducibility.md",
    "instructions/point_in_time.md",
    "instructions/data_provenance.md",
    "instructions/knowledge_base.md",
    "instructions/model_plugin_integration.md",
    "adapters/llm_runtime/",
    "adapters/model_plugin/",
    "src/quantsmith/adapters/mcp_servers/",
    "src/quantsmith/pipelines/workflow_memory.py",
    "src/quantsmith/pipelines/market_research.py",
    "sources/",
    "hooks/stages/leakage-check.sh",
    "hooks/stages/backtest-check.sh",
    "hooks/stages/repro-check.sh",
    "hooks/stages/data-contract-check.sh",
    "hooks/stages/source-catalog-check.sh",
    "hooks/stages/secret-scan-check.sh",
)

_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class OrchestrationValidationError(ValueError):
    """Raised when callers request exception-style validation."""


@dataclass(frozen=True)
class Finding:
    """One field-level orchestration validation finding."""

    source: str
    field: str
    code: str
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "source": self.source,
            "field": self.field,
            "code": self.code,
            "message": self.message,
        }


@dataclass(frozen=True)
class ValidationReport:
    """Validation outcome for one or more orchestration artifacts."""

    findings: tuple[Finding, ...] = ()
    counts: Mapping[str, int] = field(default_factory=dict)

    @property
    def errors(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity == "error")

    @property
    def ok(self) -> bool:
        return not self.errors

    def extend(self, *reports: "ValidationReport") -> "ValidationReport":
        findings = list(self.findings)
        counts = dict(self.counts)
        for report in reports:
            findings.extend(report.findings)
            for key, value in report.counts.items():
                counts[key] = counts.get(key, 0) + value
        return ValidationReport(tuple(findings), counts)

    def raise_if_errors(self) -> None:
        if self.errors:
            text = "\n".join(
                f"- {f.source}:{f.field}: {f.message}" for f in self.errors
            )
            raise OrchestrationValidationError(text)


@dataclass(frozen=True)
class ReplayReport:
    """Replay outcome emitted by the spec 0070 replay command."""

    run_id: str
    status: str
    replay_mode: str
    input_hashes: Mapping[str, str]
    fixture_substitutions: tuple[Mapping[str, str], ...] = ()
    non_reproducible_dependencies: tuple[Mapping[str, str], ...] = ()
    output_diffs: tuple[Mapping[str, str], ...] = ()
    gate_status: str = "unknown"
    findings: tuple[Mapping[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "replay_mode": self.replay_mode,
            "gate_status": self.gate_status,
            "input_hashes": dict(self.input_hashes),
            "fixture_substitutions": list(self.fixture_substitutions),
            "non_reproducible_dependencies": list(
                self.non_reproducible_dependencies
            ),
            "output_diffs": list(self.output_diffs),
            "findings": list(self.findings),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def sha256_file(path: str | Path) -> str:
    """Return a ``sha256:<hex>`` digest for ``path``."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def load_json(path: str | Path) -> Any:
    """Load a JSON artifact with path-rich errors."""

    path = Path(path)
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise OrchestrationValidationError(f"{path}: invalid JSON: {exc}") from exc


def load_jsonl(path: str | Path) -> list[Mapping[str, Any]]:
    """Load JSONL audit or assumption artifacts."""

    path = Path(path)
    records: list[Mapping[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, 1):
            line = raw.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise OrchestrationValidationError(
                    f"{path}:{line_no}: invalid JSONL: {exc}"
                ) from exc
            if not isinstance(value, Mapping):
                raise OrchestrationValidationError(
                    f"{path}:{line_no}: JSONL record must be an object"
                )
            records.append(value)
    return records


def discover_envelopes(root: str | Path) -> tuple[Path, ...]:
    """Return orchestration run envelope files below ``root``."""

    root = Path(root)
    if root.is_file():
        return (root,)
    if not root.exists():
        return ()
    return tuple(sorted(root.rglob("run_envelope*.json")))


def validate_discovered_envelopes(root: str | Path) -> ValidationReport:
    """Validate every discovered orchestration envelope below ``root``."""

    reports: list[ValidationReport] = []
    for path in discover_envelopes(root):
        reports.append(validate_run_envelope_file(path))
    counts: dict[str, int] = {}
    findings = tuple(f for report in reports for f in report.findings)
    for report in reports:
        for key, value in report.counts.items():
            if key == "envelopes":
                continue
            counts[key] = counts.get(key, 0) + value
    counts["envelopes"] = len(reports)
    return ValidationReport(findings=findings, counts=counts)


def validate_run_envelope_file(path: str | Path) -> ValidationReport:
    """Load and validate one run envelope from disk."""

    path = Path(path)
    return validate_run_envelope(
        load_json(path),
        base_dir=path.parent,
        source=str(path),
        load_references=True,
    )


def validate_run_envelope(
    envelope: Mapping[str, Any],
    *,
    base_dir: str | Path = ".",
    source: str = "<run_envelope>",
    load_references: bool = True,
) -> ValidationReport:
    """Validate a spec 0070 orchestration run envelope."""

    findings: list[Finding] = []
    base = Path(base_dir)
    required = (
        "schema_version",
        "run_id",
        "objective",
        "spec_id",
        "stage",
        "mode",
        "release_profile",
        "created_at",
        "actor",
        "repo_revision",
        "environment",
        "prompt_manifest",
        "context_manifest",
        "assumption_ledger",
        "evaluation_harness",
        "audit_events",
        "gate_results",
        "replay",
        "artifacts",
    )
    _require_fields(envelope, required, source, findings)
    _expect_schema(envelope, SCHEMA_VERSION_RUN, source, "schema_version", findings)

    run_id = _string(envelope.get("run_id"))
    if not run_id:
        _add(findings, source, "run_id", "required", "run_id must be a non-empty string")
    _require_non_empty_string(envelope, "objective", source, "objective", findings)
    _require_non_empty_string(envelope, "spec_id", source, "spec_id", findings)
    _require_non_empty_string(envelope, "stage", source, "stage", findings)
    _require_non_empty_string(envelope, "repo_revision", source, "repo_revision", findings)
    _expect_member(envelope.get("mode"), ALLOWED_RUN_MODES, source, "mode", findings)
    _expect_member(
        envelope.get("release_profile"),
        ALLOWED_RELEASE_PROFILES,
        source,
        "release_profile",
        findings,
    )
    created_at = _expect_timestamp(
        envelope.get("created_at"), source, "created_at", findings
    )

    actor = envelope.get("actor")
    if isinstance(actor, Mapping):
        _require_non_empty_string(actor, "id", source, "actor.id", findings)
        _require_non_empty_string(actor, "type", source, "actor.type", findings)
        _expect_member(
            actor.get("clearance"),
            ACCESS_LEVELS,
            source,
            "actor.clearance",
            findings,
        )
    else:
        _add(findings, source, "actor", "type", "actor must be an object")

    if not isinstance(envelope.get("environment"), Mapping):
        _add(findings, source, "environment", "type", "environment must be an object")

    manifests: dict[str, Any] = {}
    reference_fields = (
        "prompt_manifest",
        "context_manifest",
        "assumption_ledger",
        "evaluation_harness",
        "audit_events",
    )
    for field_name in reference_fields:
        ref = envelope.get(field_name)
        ref_path = _validate_artifact_ref(
            ref,
            base,
            source,
            field_name,
            findings,
            required_type=field_name,
        )
        if load_references and ref_path is not None and ref_path.exists():
            try:
                if field_name in ("assumption_ledger", "audit_events"):
                    manifests[field_name] = load_jsonl(ref_path)
                else:
                    manifests[field_name] = load_json(ref_path)
            except (OSError, OrchestrationValidationError) as exc:
                _add(findings, source, field_name, "load", str(exc))

    if load_references:
        _validate_loaded_references(
            manifests=manifests,
            base=base,
            source=source,
            run_id=run_id,
            envelope_created_at=created_at,
            findings=findings,
        )

    gate_results = envelope.get("gate_results")
    if isinstance(gate_results, Sequence) and not isinstance(gate_results, (str, bytes)):
        for index, gate in enumerate(gate_results):
            path = f"gate_results[{index}]"
            if not isinstance(gate, Mapping):
                _add(findings, source, path, "type", "gate result must be an object")
                continue
            _require_non_empty_string(gate, "gate", source, f"{path}.gate", findings)
            _expect_member(gate.get("status"), ALLOWED_STATUSES, source, f"{path}.status", findings)
            if not isinstance(gate.get("finding_count"), int):
                _add(
                    findings,
                    source,
                    f"{path}.finding_count",
                    "type",
                    "finding_count must be an integer",
                )
    else:
        _add(findings, source, "gate_results", "type", "gate_results must be a list")

    replay = envelope.get("replay")
    if isinstance(replay, Mapping):
        _require_non_empty_string(replay, "command", source, "replay.command", findings)
        _expect_member(
            replay.get("mode"),
            ALLOWED_REPLAY_MODES,
            source,
            "replay.mode",
            findings,
        )
        for output_index, output_ref in enumerate(replay.get("expected_outputs", []) or []):
            _validate_artifact_ref(
                output_ref,
                base,
                source,
                f"replay.expected_outputs[{output_index}]",
                findings,
            )
    else:
        _add(findings, source, "replay", "type", "replay must be an object")

    artifacts = envelope.get("artifacts")
    if isinstance(artifacts, Sequence) and not isinstance(artifacts, (str, bytes)):
        for index, artifact in enumerate(artifacts):
            field_name = f"artifacts[{index}]"
            _validate_artifact_ref(artifact, base, source, field_name, findings)
            if isinstance(artifact, Mapping):
                _require_non_empty_string(
                    artifact, "producer_event_id", source, f"{field_name}.producer_event_id", findings
                )
                _expect_member(
                    artifact.get("access_class"),
                    ACCESS_LEVELS,
                    source,
                    f"{field_name}.access_class",
                    findings,
                )
    else:
        _add(findings, source, "artifacts", "type", "artifacts must be a list")

    counts = {
        "envelopes": 1,
        "gate_results": len(gate_results) if isinstance(gate_results, Sequence) else 0,
        "artifacts": len(artifacts) if isinstance(artifacts, Sequence) else 0,
    }
    return ValidationReport(tuple(findings), counts)


def validate_prompt_manifest(
    manifest: Mapping[str, Any],
    *,
    base_dir: str | Path = ".",
    source: str = "<prompt_manifest>",
) -> ValidationReport:
    """Validate prompt metadata, permissions, variables, and source hashes."""

    findings: list[Finding] = []
    base = Path(base_dir)
    required = (
        "schema_version",
        "prompt_id",
        "version",
        "source",
        "role_layers",
        "variables",
        "model_constraints",
        "allowed_tools",
        "allowed_plugins",
        "prohibited_data_classes",
        "safety_policy_refs",
        "evaluation_refs",
        "owner",
        "review",
    )
    _require_fields(manifest, required, source, findings)
    _expect_schema(manifest, SCHEMA_VERSION_PROMPT, source, "schema_version", findings)
    for field_name in ("prompt_id", "version", "owner"):
        _require_non_empty_string(manifest, field_name, source, field_name, findings)

    prompt_ref = manifest.get("source")
    _validate_artifact_ref(prompt_ref, base, source, "source", findings)

    role_layers = manifest.get("role_layers")
    if isinstance(role_layers, Sequence) and not isinstance(role_layers, (str, bytes)):
        if not role_layers:
            _add(findings, source, "role_layers", "required", "role_layers cannot be empty")
        for index, layer in enumerate(role_layers):
            field_name = f"role_layers[{index}]"
            if not isinstance(layer, Mapping):
                _add(findings, source, field_name, "type", "role layer must be an object")
                continue
            _expect_member(layer.get("role"), ALLOWED_ROLES, source, f"{field_name}.role", findings)
            _validate_artifact_ref(layer, base, source, field_name, findings, allow_missing_path=False)
    else:
        _add(findings, source, "role_layers", "type", "role_layers must be a list")

    declared_variables = _named_entries(manifest.get("variables"), source, "variables", findings)
    rendered_variables = manifest.get("rendered_variables", {})
    if not isinstance(rendered_variables, Mapping):
        _add(findings, source, "rendered_variables", "type", "rendered_variables must be an object")
        rendered_variables = {}
    for name in rendered_variables:
        if name not in declared_variables:
            _add(
                findings,
                source,
                f"rendered_variables.{name}",
                "undeclared-variable",
                f"rendered variable {name!r} is not declared",
            )
    for variable in manifest.get("variables", []) if isinstance(manifest.get("variables"), Sequence) else []:
        if not isinstance(variable, Mapping):
            continue
        name = _string(variable.get("name"))
        if not name:
            continue
        if variable.get("required") is True and "default" not in variable and name not in rendered_variables:
            _add(
                findings,
                source,
                f"variables.{name}",
                "missing-render",
                f"required variable {name!r} has no default or rendered value",
            )

    for block_name in ("model_constraints", "review"):
        if not isinstance(manifest.get(block_name), Mapping):
            _add(findings, source, block_name, "type", f"{block_name} must be an object")
    for list_name in (
        "allowed_tools",
        "allowed_plugins",
        "prohibited_data_classes",
        "safety_policy_refs",
        "evaluation_refs",
    ):
        _expect_list(manifest.get(list_name), source, list_name, findings)

    allowed_tools = _named_entries(manifest.get("allowed_tools"), source, "allowed_tools", findings)
    allowed_plugins = _named_entries(manifest.get("allowed_plugins"), source, "allowed_plugins", findings)
    for requested in _named_entries(
        manifest.get("requested_tools", []), source, "requested_tools", findings
    ):
        if requested not in allowed_tools:
            _add(
                findings,
                source,
                f"requested_tools.{requested}",
                "unauthorized-tool",
                f"requested tool {requested!r} is not allowed by the prompt manifest",
            )
    for requested in _named_entries(
        manifest.get("requested_plugins", []), source, "requested_plugins", findings
    ):
        if requested not in allowed_plugins:
            _add(
                findings,
                source,
                f"requested_plugins.{requested}",
                "unauthorized-plugin",
                f"requested plugin {requested!r} is not allowed by the prompt manifest",
            )

    return ValidationReport(tuple(findings), {"prompt_manifests": 1})


def validate_context_manifest(
    manifest: Mapping[str, Any],
    *,
    base_dir: str | Path = ".",
    source: str = "<context_manifest>",
    envelope_created_at: _dt.datetime | None = None,
) -> ValidationReport:
    """Validate context access, point-in-time, freshness, and locator metadata."""

    findings: list[Finding] = []
    base = Path(base_dir)
    required = (
        "schema_version",
        "context_id",
        "run_id",
        "caller",
        "as_of",
        "context_window",
        "items",
        "exclusions",
    )
    _require_fields(manifest, required, source, findings)
    _expect_schema(manifest, SCHEMA_VERSION_CONTEXT, source, "schema_version", findings)
    for field_name in ("context_id", "run_id"):
        _require_non_empty_string(manifest, field_name, source, field_name, findings)

    context_as_of = _expect_timestamp(manifest.get("as_of"), source, "as_of", findings)
    if context_as_of and envelope_created_at and context_as_of > envelope_created_at:
        _add(
            findings,
            source,
            "as_of",
            "future-context",
            "context as_of cannot be after the envelope created_at timestamp",
        )

    caller = manifest.get("caller")
    caller_clearance = None
    if isinstance(caller, Mapping):
        _require_non_empty_string(caller, "id", source, "caller.id", findings)
        caller_clearance = _string(caller.get("clearance"))
        _expect_member(caller_clearance, ACCESS_LEVELS, source, "caller.clearance", findings)
    else:
        _add(findings, source, "caller", "type", "caller must be an object")

    window = manifest.get("context_window")
    token_budget = None
    character_budget = None
    if isinstance(window, Mapping):
        token_budget = window.get("token_budget")
        character_budget = window.get("character_budget")
        if not isinstance(token_budget, int) or token_budget < 0:
            _add(findings, source, "context_window.token_budget", "type", "token_budget must be a non-negative integer")
        if character_budget is not None and (not isinstance(character_budget, int) or character_budget < 0):
            _add(
                findings,
                source,
                "context_window.character_budget",
                "type",
                "character_budget must be a non-negative integer when supplied",
            )
    else:
        _add(findings, source, "context_window", "type", "context_window must be an object")

    items = manifest.get("items")
    tokens_used = 0
    characters_used = 0
    if isinstance(items, Sequence) and not isinstance(items, (str, bytes)):
        if not items:
            _add(findings, source, "items", "required", "items cannot be empty")
        seen_ranks: set[int] = set()
        for index, item in enumerate(items):
            field_name = f"items[{index}]"
            if not isinstance(item, Mapping):
                _add(findings, source, field_name, "type", "context item must be an object")
                continue
            _validate_context_item(
                item,
                base=base,
                source=source,
                field_name=field_name,
                caller_clearance=caller_clearance,
                manifest_as_of=context_as_of,
                findings=findings,
            )
            rank = item.get("rank")
            if isinstance(rank, int):
                if rank in seen_ranks:
                    _add(findings, source, f"{field_name}.rank", "duplicate", f"duplicate context rank {rank}")
                seen_ranks.add(rank)
            budget = item.get("budget", {})
            if isinstance(budget, Mapping):
                tokens = budget.get("tokens", 0)
                characters = budget.get("characters", 0)
                if isinstance(tokens, int):
                    tokens_used += tokens
                if isinstance(characters, int):
                    characters_used += characters
    else:
        _add(findings, source, "items", "type", "items must be a list")

    if isinstance(token_budget, int) and tokens_used > token_budget:
        _add(
            findings,
            source,
            "context_window.token_budget",
            "budget-exceeded",
            f"context uses {tokens_used} tokens but budget is {token_budget}",
        )
    if isinstance(character_budget, int) and characters_used > character_budget:
        _add(
            findings,
            source,
            "context_window.character_budget",
            "budget-exceeded",
            f"context uses {characters_used} characters but budget is {character_budget}",
        )

    exclusions = manifest.get("exclusions")
    if isinstance(exclusions, Sequence) and not isinstance(exclusions, (str, bytes)):
        for index, exclusion in enumerate(exclusions):
            field_name = f"exclusions[{index}]"
            if not isinstance(exclusion, Mapping):
                _add(findings, source, field_name, "type", "exclusion must be an object")
                continue
            _require_non_empty_string(exclusion, "locator", source, f"{field_name}.locator", findings)
            _require_non_empty_string(exclusion, "reason", source, f"{field_name}.reason", findings)
    else:
        _add(findings, source, "exclusions", "type", "exclusions must be a list")

    return ValidationReport(tuple(findings), {"context_manifests": 1, "context_items": len(items) if isinstance(items, Sequence) else 0})


def validate_assumption_ledger(
    assumptions: Sequence[Mapping[str, Any]],
    *,
    base_dir: str | Path = ".",
    source: str = "<assumption_ledger>",
) -> ValidationReport:
    """Validate material assumption records and their disposition history."""

    findings: list[Finding] = []
    seen: set[str] = set()
    required = (
        "schema_version",
        "assumption_id",
        "statement",
        "type",
        "scope",
        "owner",
        "evidence",
        "confidence",
        "status",
        "introduced_at",
        "dependent_artifacts",
        "invalidation_trigger",
        "disposition_history",
    )
    for index, assumption in enumerate(assumptions):
        field_name = f"assumptions[{index}]"
        if not isinstance(assumption, Mapping):
            _add(findings, source, field_name, "type", "assumption must be an object")
            continue
        _require_fields(assumption, required, source, findings, prefix=field_name)
        _expect_schema(assumption, SCHEMA_VERSION_ASSUMPTION, source, f"{field_name}.schema_version", findings)
        assumption_id = _string(assumption.get("assumption_id"))
        if not assumption_id:
            _add(findings, source, f"{field_name}.assumption_id", "required", "assumption_id is required")
        elif assumption_id in seen:
            _add(findings, source, f"{field_name}.assumption_id", "duplicate", f"duplicate assumption_id {assumption_id}")
        seen.add(assumption_id)
        for key in ("statement", "type", "scope", "owner", "invalidation_trigger"):
            _require_non_empty_string(assumption, key, source, f"{field_name}.{key}", findings)
        _expect_member(assumption.get("confidence"), ALLOWED_CONFIDENCE, source, f"{field_name}.confidence", findings)
        _expect_member(
            assumption.get("status"),
            ALLOWED_ASSUMPTION_STATUSES,
            source,
            f"{field_name}.status",
            findings,
        )
        _expect_date(assumption.get("introduced_at"), source, f"{field_name}.introduced_at", findings)
        if not assumption.get("review_due_at") and not assumption.get("expires_at"):
            _add(
                findings,
                source,
                f"{field_name}.review_due_at",
                "required",
                "assumption requires review_due_at or expires_at",
            )
        if assumption.get("review_due_at"):
            _expect_date(assumption.get("review_due_at"), source, f"{field_name}.review_due_at", findings)
        if assumption.get("expires_at"):
            _expect_date(assumption.get("expires_at"), source, f"{field_name}.expires_at", findings)
        _expect_non_empty_list(assumption.get("evidence"), source, f"{field_name}.evidence", findings)
        _expect_non_empty_list(
            assumption.get("dependent_artifacts"),
            source,
            f"{field_name}.dependent_artifacts",
            findings,
        )
        history = assumption.get("disposition_history")
        if _expect_non_empty_list(history, source, f"{field_name}.disposition_history", findings):
            for event_index, event in enumerate(history):
                event_field = f"{field_name}.disposition_history[{event_index}]"
                if not isinstance(event, Mapping):
                    _add(findings, source, event_field, "type", "disposition history entry must be an object")
                    continue
                for key in ("status", "timestamp", "actor", "reason"):
                    _require_non_empty_string(event, key, source, f"{event_field}.{key}", findings)
                _expect_timestamp(event.get("timestamp"), source, f"{event_field}.timestamp", findings)
    return ValidationReport(tuple(findings), {"assumptions": len(assumptions)})


def validate_evaluation_harness(
    harness: Mapping[str, Any],
    *,
    base_dir: str | Path = ".",
    source: str = "<evaluation_harness>",
) -> ValidationReport:
    """Validate layer-specific deterministic checks or explicit exceptions."""

    findings: list[Finding] = []
    required = (
        "schema_version",
        "harness_id",
        "run_id",
        "required_layers",
        "layers",
        "integration_surfaces",
    )
    _require_fields(harness, required, source, findings)
    _expect_schema(harness, SCHEMA_VERSION_EVALUATION, source, "schema_version", findings)
    for key in ("harness_id", "run_id"):
        _require_non_empty_string(harness, key, source, key, findings)

    declared_required = harness.get("required_layers")
    if not isinstance(declared_required, Sequence) or isinstance(declared_required, (str, bytes)):
        _add(findings, source, "required_layers", "type", "required_layers must be a list")
        declared_required = ()
    missing_required = sorted(set(REQUIRED_HARNESS_LAYERS) - set(declared_required))
    for layer in missing_required:
        _add(
            findings,
            source,
            "required_layers",
            "missing-layer",
            f"required harness layer {layer!r} is missing",
        )

    layer_entries = harness.get("layers")
    covered: set[str] = set()
    if isinstance(layer_entries, Sequence) and not isinstance(layer_entries, (str, bytes)):
        for index, entry in enumerate(layer_entries):
            field_name = f"layers[{index}]"
            if not isinstance(entry, Mapping):
                _add(findings, source, field_name, "type", "layer entry must be an object")
                continue
            layer = _string(entry.get("layer"))
            if not layer:
                _add(findings, source, f"{field_name}.layer", "required", "layer is required")
                continue
            checks = entry.get("checks", [])
            exception = entry.get("exception")
            if _has_deterministic_check(checks, source, field_name, findings):
                covered.add(layer)
            elif isinstance(exception, Mapping) and _string(exception.get("reason")):
                covered.add(layer)
            else:
                _add(
                    findings,
                    source,
                    field_name,
                    "coverage",
                    "layer needs a deterministic check or an explicit exception with a reason",
                )
    else:
        _add(findings, source, "layers", "type", "layers must be a list")

    for layer in REQUIRED_HARNESS_LAYERS:
        if layer not in covered:
            _add(
                findings,
                source,
                f"layers.{layer}",
                "missing-layer-coverage",
                f"harness layer {layer!r} lacks check or exception coverage",
            )

    surfaces = harness.get("integration_surfaces")
    if isinstance(surfaces, Sequence) and not isinstance(surfaces, (str, bytes)):
        for surface in INTEGRATION_SURFACES:
            if surface not in surfaces:
                _add(
                    findings,
                    source,
                    "integration_surfaces",
                    "missing-surface",
                    f"existing surface {surface!r} must be referenced, not re-owned",
                )
    else:
        _add(findings, source, "integration_surfaces", "type", "integration_surfaces must be a list")

    return ValidationReport(tuple(findings), {"evaluation_harnesses": 1})


def validate_audit_events(
    events: Sequence[Mapping[str, Any]],
    *,
    run_id: str | None = None,
    base_dir: str | Path = ".",
    source: str = "<audit_events>",
) -> ValidationReport:
    """Validate append-only audit event shape and event relationships."""

    findings: list[Finding] = []
    base = Path(base_dir)
    seen: set[str] = set()
    previous_timestamp: _dt.datetime | None = None
    for index, event in enumerate(events):
        field_name = f"events[{index}]"
        if not isinstance(event, Mapping):
            _add(findings, source, field_name, "type", "audit event must be an object")
            continue
        required = (
            "schema_version",
            "event_id",
            "run_id",
            "event_type",
            "timestamp",
            "actor",
            "parent_event_ids",
            "payload_ref",
            "artifact_refs",
            "finding_refs",
        )
        _require_fields(event, required, source, findings, prefix=field_name)
        _expect_schema(event, SCHEMA_VERSION_AUDIT_EVENT, source, f"{field_name}.schema_version", findings)
        event_id = _string(event.get("event_id"))
        if not event_id:
            _add(findings, source, f"{field_name}.event_id", "required", "event_id is required")
        elif event_id in seen:
            _add(findings, source, f"{field_name}.event_id", "duplicate", f"duplicate event_id {event_id}")
        event_run_id = _string(event.get("run_id"))
        if run_id and event_run_id and event_run_id != run_id:
            _add(
                findings,
                source,
                f"{field_name}.run_id",
                "run-mismatch",
                f"event run_id {event_run_id!r} does not match envelope run_id {run_id!r}",
            )
        _expect_member(
            event.get("event_type"),
            ALLOWED_AUDIT_EVENT_TYPES,
            source,
            f"{field_name}.event_type",
            findings,
        )
        timestamp = _expect_timestamp(event.get("timestamp"), source, f"{field_name}.timestamp", findings)
        if timestamp and previous_timestamp and timestamp < previous_timestamp:
            _add(
                findings,
                source,
                f"{field_name}.timestamp",
                "non-monotonic",
                "audit event timestamps must be monotonic",
            )
        if timestamp:
            previous_timestamp = timestamp
        _require_non_empty_string(event, "actor", source, f"{field_name}.actor", findings)
        parent_ids = event.get("parent_event_ids")
        if isinstance(parent_ids, Sequence) and not isinstance(parent_ids, (str, bytes)):
            for parent_id in parent_ids:
                if parent_id not in seen:
                    _add(
                        findings,
                        source,
                        f"{field_name}.parent_event_ids",
                        "broken-parent",
                        f"parent event {parent_id!r} is missing or appears after child",
                    )
        else:
            _add(findings, source, f"{field_name}.parent_event_ids", "type", "parent_event_ids must be a list")
        if event.get("event_type") in ("override", "human_approval", "release_decision"):
            _require_non_empty_string(event, "reason", source, f"{field_name}.reason", findings)
        payload_ref = event.get("payload_ref")
        if not isinstance(payload_ref, Mapping):
            _add(findings, source, f"{field_name}.payload_ref", "type", "payload_ref must be an object")
        else:
            _validate_optional_fixture_ref(payload_ref, base, source, f"{field_name}.payload_ref", findings)
        if "payload" in event:
            _add(
                findings,
                source,
                f"{field_name}.payload",
                "raw-payload",
                "audit events must store payload_ref or redacted metadata, not raw payload bodies",
            )
        for list_name in ("artifact_refs", "finding_refs"):
            _expect_list(event.get(list_name), source, f"{field_name}.{list_name}", findings)
        if event_id:
            seen.add(event_id)
    return ValidationReport(tuple(findings), {"audit_events": len(events)})


def append_audit_event(path: str | Path, event: Mapping[str, Any]) -> None:
    """Append a validated audit event to a JSONL ledger."""

    path = Path(path)
    existing: list[Mapping[str, Any]] = []
    if path.exists():
        existing = load_jsonl(path)
    report = validate_audit_events(
        existing + [event],
        base_dir=path.parent,
        source=str(path),
    )
    report.raise_if_errors()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(event), sort_keys=True, separators=(",", ":")))
        handle.write("\n")


def replay_envelope_file(
    path: str | Path,
    *,
    fixture_mode: bool = False,
    allow_non_reproducible: bool = False,
) -> ReplayReport:
    """Validate and replay the deterministic or fixture-backed layers of a run."""

    path = Path(path)
    base = path.parent
    envelope = load_json(path)
    validation = validate_run_envelope(envelope, base_dir=base, source=str(path), load_references=True)
    run_id = _string(envelope.get("run_id")) or "<unknown>"

    input_hashes: dict[str, str] = {}
    for field_name in (
        "prompt_manifest",
        "context_manifest",
        "assumption_ledger",
        "evaluation_harness",
        "audit_events",
    ):
        ref = envelope.get(field_name)
        if isinstance(ref, Mapping):
            ref_path = _ref_path(ref, base)
            if ref_path is not None and ref_path.exists():
                input_hashes[field_name] = sha256_file(ref_path)
    for artifact in envelope.get("artifacts", []) if isinstance(envelope.get("artifacts"), Sequence) else []:
        if isinstance(artifact, Mapping):
            ref_path = _ref_path(artifact, base)
            if ref_path is not None and ref_path.exists():
                input_hashes[_string(artifact.get("path")) or ref_path.name] = sha256_file(ref_path)

    audit_events = []
    audit_ref = envelope.get("audit_events")
    if isinstance(audit_ref, Mapping):
        audit_path = _ref_path(audit_ref, base)
        if audit_path is not None and audit_path.exists():
            audit_events = load_jsonl(audit_path)

    fixture_substitutions: list[Mapping[str, str]] = []
    non_reproducible: list[Mapping[str, str]] = []
    replay_mode = _string(envelope.get("replay", {}).get("mode") if isinstance(envelope.get("replay"), Mapping) else "")
    for event in audit_events:
        if event.get("event_type") not in ("model_invocation", "tool_plugin_call"):
            continue
        payload_ref = event.get("payload_ref", {})
        if not isinstance(payload_ref, Mapping):
            continue
        if payload_ref.get("deterministic") is True:
            continue
        fixture_path = _string(payload_ref.get("fixture_path"))
        if fixture_path:
            if fixture_mode or replay_mode == "fixture":
                fixture_substitutions.append(
                    {
                        "event_id": _string(event.get("event_id")) or "",
                        "event_type": _string(event.get("event_type")) or "",
                        "fixture_path": fixture_path,
                    }
                )
            continue
        non_reproducible.append(
            {
                "event_id": _string(event.get("event_id")) or "",
                "event_type": _string(event.get("event_type")) or "",
                "provider": _string(payload_ref.get("provider")) or "unknown",
                "reason": "no deterministic executor or fixture_path was declared",
            }
        )

    output_diffs: list[Mapping[str, str]] = []
    replay = envelope.get("replay")
    if isinstance(replay, Mapping):
        for output_ref in replay.get("expected_outputs", []) or []:
            if not isinstance(output_ref, Mapping):
                continue
            ref_path = _ref_path(output_ref, base)
            expected_hash = _string(output_ref.get("hash") or output_ref.get("content_hash"))
            if ref_path is None or not ref_path.exists() or not expected_hash:
                continue
            actual_hash = sha256_file(ref_path)
            if expected_hash != actual_hash:
                output_diffs.append(
                    {
                        "path": str(output_ref.get("path")),
                        "expected_hash": expected_hash,
                        "actual_hash": actual_hash,
                    }
                )

    gate_status = "pass"
    for gate in envelope.get("gate_results", []) if isinstance(envelope.get("gate_results"), Sequence) else []:
        if isinstance(gate, Mapping) and gate.get("status") not in ("pass", "skipped"):
            gate_status = "warn"
            break
    findings = tuple(f.to_dict() for f in validation.findings)
    if validation.errors or output_diffs:
        status = "invalid"
    elif non_reproducible and not allow_non_reproducible:
        status = "non_reproducible"
    else:
        status = "replayed"
    return ReplayReport(
        run_id=run_id,
        status=status,
        replay_mode=replay_mode or "metadata_only",
        input_hashes=input_hashes,
        fixture_substitutions=tuple(fixture_substitutions),
        non_reproducible_dependencies=tuple(non_reproducible),
        output_diffs=tuple(output_diffs),
        gate_status=gate_status,
        findings=findings,
    )


def _validate_loaded_references(
    *,
    manifests: Mapping[str, Any],
    base: Path,
    source: str,
    run_id: str | None,
    envelope_created_at: _dt.datetime | None,
    findings: list[Finding],
) -> None:
    validators = {
        "prompt_manifest": lambda data: validate_prompt_manifest(
            data, base_dir=base, source=f"{source}:prompt_manifest"
        ),
        "context_manifest": lambda data: validate_context_manifest(
            data,
            base_dir=base,
            source=f"{source}:context_manifest",
            envelope_created_at=envelope_created_at,
        ),
        "assumption_ledger": lambda data: validate_assumption_ledger(
            data, base_dir=base, source=f"{source}:assumption_ledger"
        ),
        "evaluation_harness": lambda data: validate_evaluation_harness(
            data, base_dir=base, source=f"{source}:evaluation_harness"
        ),
        "audit_events": lambda data: validate_audit_events(
            data, run_id=run_id, base_dir=base, source=f"{source}:audit_events"
        ),
    }
    for name, validator in validators.items():
        data = manifests.get(name)
        if data is None:
            continue
        findings.extend(validator(data).findings)


def _validate_context_item(
    item: Mapping[str, Any],
    *,
    base: Path,
    source: str,
    field_name: str,
    caller_clearance: str | None,
    manifest_as_of: _dt.datetime | None,
    findings: list[Finding],
) -> None:
    required = (
        "context_id",
        "source_authority",
        "locator",
        "access_level",
        "caller_clearance",
        "retrieval_query",
        "selection_rule",
        "rank",
        "budget",
        "known_at",
        "freshness",
        "citations",
    )
    _require_fields(item, required, source, findings, prefix=field_name)
    for key in (
        "context_id",
        "source_authority",
        "locator",
        "access_level",
        "caller_clearance",
        "retrieval_query",
        "selection_rule",
        "freshness",
    ):
        _require_non_empty_string(item, key, source, f"{field_name}.{key}", findings)
    access_level = _string(item.get("access_level"))
    item_clearance = _string(item.get("caller_clearance")) or caller_clearance
    _expect_member(access_level, ACCESS_LEVELS, source, f"{field_name}.access_level", findings)
    _expect_member(item_clearance, ACCESS_LEVELS, source, f"{field_name}.caller_clearance", findings)
    if access_level and item_clearance and not _access_allows(access_level, item_clearance):
        _add(
            findings,
            source,
            f"{field_name}.access_level",
            "access-denied",
            f"caller clearance {item_clearance!r} cannot access {access_level!r} context",
        )
    if caller_clearance and item_clearance and item_clearance != caller_clearance:
        _add(
            findings,
            source,
            f"{field_name}.caller_clearance",
            "caller-mismatch",
            "context item caller_clearance must match manifest caller clearance",
        )
    _expect_member(item.get("freshness"), ALLOWED_FRESHNESS, source, f"{field_name}.freshness", findings)
    known_at = _expect_timestamp(item.get("known_at"), source, f"{field_name}.known_at", findings)
    if known_at and manifest_as_of and known_at > manifest_as_of:
        _add(
            findings,
            source,
            f"{field_name}.known_at",
            "future-known",
            "context item was known after the run as_of time",
        )
    if item.get("effective_at"):
        _expect_timestamp(item.get("effective_at"), source, f"{field_name}.effective_at", findings)
    expires_at = None
    if item.get("expires_at"):
        expires_at = _expect_timestamp(item.get("expires_at"), source, f"{field_name}.expires_at", findings)
    if expires_at and manifest_as_of and expires_at < manifest_as_of and item.get("freshness") == "current":
        _add(
            findings,
            source,
            f"{field_name}.freshness",
            "stale-current",
            "expired context cannot be marked current",
        )
    if "content_hash" not in item and "chunk_id" not in item:
        _add(
            findings,
            source,
            f"{field_name}.content_hash",
            "required",
            "context item requires content_hash or chunk_id",
        )
    if item.get("content_hash"):
        _validate_hash_value(item.get("content_hash"), source, f"{field_name}.content_hash", findings)
        locator_path = _locator_path(_string(item.get("locator")), base)
        if locator_path is not None and locator_path.exists():
            _verify_hash(locator_path, _string(item.get("content_hash")), source, f"{field_name}.content_hash", findings)
    if not isinstance(item.get("rank"), int):
        _add(findings, source, f"{field_name}.rank", "type", "rank must be an integer")
    budget = item.get("budget")
    if isinstance(budget, Mapping):
        for key in ("tokens", "characters"):
            if not isinstance(budget.get(key), int) or budget.get(key) < 0:
                _add(findings, source, f"{field_name}.budget.{key}", "type", f"{key} must be a non-negative integer")
    else:
        _add(findings, source, f"{field_name}.budget", "type", "budget must be an object")
    _expect_non_empty_list(item.get("citations"), source, f"{field_name}.citations", findings)


def _has_deterministic_check(
    checks: Any,
    source: str,
    field_name: str,
    findings: list[Finding],
) -> bool:
    if not isinstance(checks, Sequence) or isinstance(checks, (str, bytes)):
        _add(findings, source, f"{field_name}.checks", "type", "checks must be a list")
        return False
    has_check = False
    for index, check in enumerate(checks):
        check_field = f"{field_name}.checks[{index}]"
        if not isinstance(check, Mapping):
            _add(findings, source, check_field, "type", "check must be an object")
            continue
        for key in ("check_id", "check_type", "status"):
            _require_non_empty_string(check, key, source, f"{check_field}.{key}", findings)
        _expect_member(check.get("status"), ALLOWED_STATUSES, source, f"{check_field}.status", findings)
        deterministic = check.get("deterministic")
        fixture_ref = check.get("fixture_ref")
        if deterministic is True or fixture_ref:
            has_check = True
    return has_check


def _validate_optional_fixture_ref(
    payload_ref: Mapping[str, Any],
    base: Path,
    source: str,
    field_name: str,
    findings: list[Finding],
) -> None:
    fixture_path = _string(payload_ref.get("fixture_path"))
    fixture_hash = _string(payload_ref.get("fixture_hash"))
    if fixture_path:
        ref = {"path": fixture_path, "hash": fixture_hash or payload_ref.get("hash")}
        _validate_artifact_ref(ref, base, source, f"{field_name}.fixture", findings)
    elif payload_ref.get("hash"):
        _validate_hash_value(payload_ref.get("hash"), source, f"{field_name}.hash", findings)


def _validate_artifact_ref(
    ref: Any,
    base: Path,
    source: str,
    field_name: str,
    findings: list[Finding],
    *,
    required_type: str | None = None,
    allow_missing_path: bool = True,
) -> Path | None:
    if not isinstance(ref, Mapping):
        _add(findings, source, field_name, "type", f"{field_name} must be an object")
        return None
    path_text = _string(ref.get("path") or ref.get("source_path"))
    if not path_text:
        if allow_missing_path:
            _add(findings, source, f"{field_name}.path", "required", "path is required")
        return None
    ref_path = _ref_path(ref, base)
    expected_hash = _string(ref.get("hash") or ref.get("content_hash"))
    if not expected_hash:
        _add(findings, source, f"{field_name}.hash", "required", "sha256 hash is required")
    else:
        _validate_hash_value(expected_hash, source, f"{field_name}.hash", findings)
    if ref.get("type") and required_type and ref.get("type") != required_type:
        _add(
            findings,
            source,
            f"{field_name}.type",
            "type-mismatch",
            f"expected artifact type {required_type!r}",
        )
    if ref_path is not None and not ref_path.exists():
        _add(findings, source, f"{field_name}.path", "missing", f"artifact path does not exist: {path_text}")
    elif ref_path is not None and expected_hash:
        _verify_hash(ref_path, expected_hash, source, f"{field_name}.hash", findings)
    return ref_path


def _verify_hash(
    path: Path,
    expected_hash: str | None,
    source: str,
    field_name: str,
    findings: list[Finding],
) -> None:
    if not expected_hash or not _HASH_RE.match(expected_hash):
        return
    try:
        actual_hash = sha256_file(path)
    except OSError as exc:
        _add(findings, source, field_name, "hash-read", f"cannot read {path}: {exc}")
        return
    if actual_hash != expected_hash:
        _add(
            findings,
            source,
            field_name,
            "hash-mismatch",
            f"hash mismatch for {path}: expected {expected_hash}, got {actual_hash}",
        )


def _ref_path(ref: Mapping[str, Any], base: Path) -> Path | None:
    path_text = _string(ref.get("path") or ref.get("source_path"))
    if not path_text:
        return None
    path = Path(path_text)
    return path if path.is_absolute() else base / path


def _locator_path(locator: str | None, base: Path) -> Path | None:
    if not locator or "://" in locator:
        return None
    local = locator.split("#", 1)[0]
    if not local:
        return None
    path = Path(local)
    return path if path.is_absolute() else base / path


def _require_fields(
    data: Mapping[str, Any],
    fields: Iterable[str],
    source: str,
    findings: list[Finding],
    *,
    prefix: str = "",
) -> None:
    for name in fields:
        if name not in data:
            field_name = f"{prefix}.{name}" if prefix else name
            _add(findings, source, field_name, "required", f"{name} is required")


def _require_non_empty_string(
    data: Mapping[str, Any],
    key: str,
    source: str,
    field_name: str,
    findings: list[Finding],
) -> None:
    if not _string(data.get(key)):
        _add(findings, source, field_name, "required", f"{key} must be a non-empty string")


def _expect_schema(
    data: Mapping[str, Any],
    expected: str,
    source: str,
    field_name: str,
    findings: list[Finding],
) -> None:
    if data.get("schema_version") != expected:
        _add(
            findings,
            source,
            field_name,
            "schema-version",
            f"schema_version must be {expected!r}",
        )


def _expect_member(
    value: Any,
    allowed: Sequence[str],
    source: str,
    field_name: str,
    findings: list[Finding],
) -> None:
    if value not in allowed:
        _add(
            findings,
            source,
            field_name,
            "allowed-value",
            f"{field_name} must be one of {', '.join(allowed)}",
        )


def _expect_list(value: Any, source: str, field_name: str, findings: list[Finding]) -> bool:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        _add(findings, source, field_name, "type", f"{field_name} must be a list")
        return False
    return True


def _expect_non_empty_list(
    value: Any,
    source: str,
    field_name: str,
    findings: list[Finding],
) -> bool:
    if not _expect_list(value, source, field_name, findings):
        return False
    if not value:
        _add(findings, source, field_name, "required", f"{field_name} cannot be empty")
        return False
    return True


def _named_entries(
    entries: Any,
    source: str,
    field_name: str,
    findings: list[Finding],
) -> set[str]:
    names: set[str] = set()
    if entries is None:
        return names
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        _add(findings, source, field_name, "type", f"{field_name} must be a list")
        return names
    for index, entry in enumerate(entries):
        if isinstance(entry, str):
            name = entry
        elif isinstance(entry, Mapping):
            name = _string(entry.get("name"))
        else:
            _add(findings, source, f"{field_name}[{index}]", "type", "entry must be a string or object with name")
            continue
        if not name:
            _add(findings, source, f"{field_name}[{index}].name", "required", "name is required")
        elif name in names:
            _add(findings, source, f"{field_name}[{index}].name", "duplicate", f"duplicate name {name!r}")
        else:
            names.add(name)
    return names


def _expect_timestamp(
    value: Any,
    source: str,
    field_name: str,
    findings: list[Finding],
) -> _dt.datetime | None:
    if not isinstance(value, str) or not _TIMESTAMP_RE.match(value):
        _add(findings, source, field_name, "timestamp", "timestamp must be UTC ISO format YYYY-MM-DDTHH:MM:SSZ")
        return None
    try:
        return _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _add(findings, source, field_name, "timestamp", "timestamp is not a valid UTC instant")
        return None


def _expect_date(value: Any, source: str, field_name: str, findings: list[Finding]) -> None:
    if not isinstance(value, str) or not _DATE_RE.match(value):
        _add(findings, source, field_name, "date", "date must be ISO format YYYY-MM-DD")
        return
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        _add(findings, source, field_name, "date", "date is not valid")


def _validate_hash_value(
    value: Any,
    source: str,
    field_name: str,
    findings: list[Finding],
) -> None:
    if not isinstance(value, str) or not _HASH_RE.match(value):
        _add(
            findings,
            source,
            field_name,
            "hash-format",
            "hash must be sha256:<64 lowercase hex characters>",
        )


def _access_allows(item_level: str, caller_clearance: str) -> bool:
    item_rank = _ACCESS_RANK.get(item_level, len(ACCESS_LEVELS) - 1)
    caller_rank = _ACCESS_RANK.get(caller_clearance, 0)
    return item_rank <= caller_rank


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _add(
    findings: list[Finding],
    source: str,
    field_name: str,
    code: str,
    message: str,
    *,
    severity: str = "error",
) -> None:
    findings.append(Finding(source=source, field=field_name, code=code, message=message, severity=severity))
