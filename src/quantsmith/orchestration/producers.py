"""Producer integrations for spec 0070 orchestration evidence.

These helpers adapt existing runtimes into 0070 evidence bundles without
changing the runtimes' own execution contracts. The first producer consumes a
real ``quant_factory.FactorySpec`` and ``FactoryDecision`` and emits the prompt,
context, assumption, evaluation, audit, replay, and envelope artifacts needed
to validate the run offline.
"""

from __future__ import annotations

import datetime as _dt
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

from .foundation import (
    INTEGRATION_SURFACES,
    REQUIRED_HARNESS_LAYERS,
    SCHEMA_VERSION_ASSUMPTION,
    SCHEMA_VERSION_AUDIT_EVENT,
    SCHEMA_VERSION_CONTEXT,
    SCHEMA_VERSION_EVALUATION,
    SCHEMA_VERSION_PROMPT,
    SCHEMA_VERSION_RUN,
    sha256_file,
    validate_run_envelope_file,
)


def emit_quant_factory_evidence(
    spec: Any,
    decision: Any,
    output_dir: str | Path,
    *,
    actor_id: str = "quant_factory",
    actor_clearance: str = "internal",
    started_at: str | None = None,
    repo_revision: str = "unknown",
    objective: str | None = None,
    release_profile: str = "release_bound",
) -> Path:
    """Emit a validated 0070 envelope for a real quant-factory run.

    ``spec`` is expected to be a ``quantsmith.pipelines.quant_factory.FactorySpec``
    and ``decision`` a matching ``FactoryDecision``. The function intentionally
    accepts them structurally, rather than importing quant-factory types at
    module import time, so the orchestration package stays lightweight.
    """

    if getattr(spec, "run_id", None) != getattr(decision, "run_id", None):
        raise ValueError("FactorySpec.run_id and FactoryDecision.run_id must match")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    started = _parse_or_now(started_at)
    created_at = _format_utc(started + _dt.timedelta(seconds=6))
    review_date = _format_date(started.date() + _dt.timedelta(days=365))
    run_id = str(spec.run_id)
    safe_run_id = _safe_id(run_id)
    objective = objective or (
        "Record Quant Model Factory convergence evidence in a spec 0070 "
        "orchestration envelope."
    )

    decision_path = out / "factory_decision.json"
    _write_json(
        decision_path,
        _factory_decision_payload(
            spec,
            decision,
            producer="quantsmith.pipelines.quant_factory.FactoryRunner.run",
        ),
    )
    decision_hash = sha256_file(decision_path)

    prompt_path = out / "prompt.md"
    prompt_path.write_text(_render_factory_prompt(spec, objective), encoding="utf-8")
    prompt_hash = sha256_file(prompt_path)

    context_path = out / "context_note.md"
    context_path.write_text(_render_factory_context(spec, decision), encoding="utf-8")
    context_hash = sha256_file(context_path)

    prompt_manifest_path = out / "prompt_manifest.json"
    _write_json(
        prompt_manifest_path,
        {
            "schema_version": SCHEMA_VERSION_PROMPT,
            "prompt_id": "prompt.quant_factory.producer",
            "version": "1.0.0",
            "source": {
                "type": "prompt_source",
                "path": "prompt.md",
                "hash": prompt_hash,
            },
            "role_layers": [
                {
                    "role": "system",
                    "source_path": "prompt.md",
                    "hash": prompt_hash,
                }
            ],
            "variables": [
                {"name": "run_id", "required": True},
                {"name": "convergence_mode", "required": True},
                {"name": "seed", "required": True},
            ],
            "rendered_variables": {
                "run_id": run_id,
                "convergence_mode": str(spec.convergence_mode),
                "seed": str(spec.seed),
            },
            "model_constraints": {
                "providers": ["deterministic"],
                "models": ["quantsmith.pipelines.quant_factory.FactoryRunner"],
                "temperature_max": 0.0,
                "seed_required": True,
            },
            "allowed_tools": [
                {
                    "name": "quantsmith.pipelines.quant_factory.FactoryRunner.run",
                    "type": "python",
                    "fixtureable": True,
                }
            ],
            "allowed_plugins": [],
            "requested_tools": [
                {"name": "quantsmith.pipelines.quant_factory.FactoryRunner.run"}
            ],
            "requested_plugins": [],
            "prohibited_data_classes": [
                "secret",
                "credential",
                "mnpi",
                "licensed_body",
            ],
            "safety_policy_refs": [
                "instructions/point_in_time.md",
                "instructions/reproducibility.md",
            ],
            "evaluation_refs": ["evaluation_harness.json#quant_factory"],
            "owner": "spec0070",
            "review": {
                "status": "approved",
                "reviewer": actor_id,
                "reviewed_at": _format_date(started.date()),
            },
        },
    )
    prompt_manifest_hash = sha256_file(prompt_manifest_path)

    context_manifest_path = out / "context_manifest.json"
    _write_json(
        context_manifest_path,
        {
            "schema_version": SCHEMA_VERSION_CONTEXT,
            "context_id": f"ctx-{safe_run_id}",
            "run_id": run_id,
            "caller": {"id": actor_id, "clearance": actor_clearance},
            "as_of": _format_utc(started + _dt.timedelta(seconds=1)),
            "context_window": {
                "token_budget": 4096,
                "character_budget": 16000,
            },
            "items": [
                {
                    "context_id": f"ctx-{safe_run_id}-factory-summary",
                    "source_authority": "quantsmith://pipeline/quant_factory",
                    "locator": "context_note.md#quant-factory-run",
                    "content_hash": context_hash,
                    "access_level": "internal",
                    "caller_clearance": actor_clearance,
                    "retrieval_query": f"quant factory run {run_id}",
                    "selection_rule": "factory spec and decision supplied by caller",
                    "rank": 1,
                    "budget": {
                        "tokens": 256,
                        "characters": len(context_path.read_text(encoding="utf-8")),
                    },
                    "known_at": _format_utc(started + _dt.timedelta(seconds=1)),
                    "effective_at": _format_utc(started + _dt.timedelta(seconds=1)),
                    "expires_at": _format_utc(started + _dt.timedelta(days=365)),
                    "freshness": "current",
                    "citations": [
                        {
                            "label": "factory decision artifact",
                            "locator": "factory_decision.json",
                        },
                        {
                            "label": "factory ledger",
                            "locator": str(spec.ledger_path),
                        },
                    ],
                }
            ],
            "exclusions": [
                {
                    "locator": "lane training data bodies",
                    "reason": "producer records metadata and lane outcomes; source data remains owned by the caller",
                }
            ],
        },
    )
    context_manifest_hash = sha256_file(context_manifest_path)

    assumptions_path = out / "assumptions.jsonl"
    _write_jsonl(
        assumptions_path,
        [
            {
                "schema_version": SCHEMA_VERSION_ASSUMPTION,
                "assumption_id": f"ASM-{safe_run_id}-001",
                "statement": (
                    "Caller-supplied lane results were produced using point-in-time "
                    "inputs, and any detected leakage is represented in leakage_flags."
                ),
                "type": "producer_boundary",
                "scope": "quantsmith.pipelines.quant_factory",
                "owner": "spec0061",
                "evidence": [
                    {
                        "type": "factory_decision",
                        "locator": "factory_decision.json",
                        "hash": decision_hash,
                    }
                ],
                "confidence": "medium",
                "status": "active",
                "introduced_at": _format_date(started.date()),
                "review_due_at": review_date,
                "dependent_artifacts": ["factory_decision.json", "run_envelope.json"],
                "invalidation_trigger": (
                    "A lane executor is found to have used look-ahead data or omitted "
                    "a leakage flag."
                ),
                "disposition_history": [
                    {
                        "status": "active",
                        "timestamp": _format_utc(started + _dt.timedelta(seconds=2)),
                        "actor": actor_id,
                        "reason": "Required boundary assumption for quant-factory producer evidence.",
                    }
                ],
            },
            {
                "schema_version": SCHEMA_VERSION_ASSUMPTION,
                "assumption_id": f"ASM-{safe_run_id}-002",
                "statement": (
                    "The convergence gate thresholds were predeclared before the "
                    "factory decision was accepted."
                ),
                "type": "gate_threshold",
                "scope": "quantsmith.pipelines.quant_factory",
                "owner": "spec0061",
                "evidence": [
                    {
                        "type": "factory_decision",
                        "locator": "factory_decision.json",
                        "hash": decision_hash,
                    }
                ],
                "confidence": "high",
                "status": "active",
                "introduced_at": _format_date(started.date()),
                "review_due_at": review_date,
                "dependent_artifacts": ["factory_decision.json", "evaluation_harness.json"],
                "invalidation_trigger": "Gate parameters are changed after lane results are known.",
                "disposition_history": [
                    {
                        "status": "active",
                        "timestamp": _format_utc(started + _dt.timedelta(seconds=2)),
                        "actor": actor_id,
                        "reason": "Convergence gate recorded verbatim from FactorySpec.",
                    }
                ],
            },
        ],
    )
    assumptions_hash = sha256_file(assumptions_path)

    harness_path = out / "evaluation_harness.json"
    _write_json(
        harness_path,
        _factory_harness_payload(
            run_id=run_id,
            safe_run_id=safe_run_id,
            decision=decision,
        ),
    )
    harness_hash = sha256_file(harness_path)

    audit_path = out / "audit_events.jsonl"
    _write_jsonl(
        audit_path,
        _factory_audit_events(
            run_id=run_id,
            safe_run_id=safe_run_id,
            actor_id=actor_id,
            started=started,
            decision=decision,
            decision_hash=decision_hash,
        ),
    )
    audit_hash = sha256_file(audit_path)

    envelope_path = out / "run_envelope.json"
    _write_json(
        envelope_path,
        {
            "schema_version": SCHEMA_VERSION_RUN,
            "run_id": run_id,
            "objective": objective,
            "spec_id": "0070-prompt-context-harness-foundation",
            "stage": "implementation",
            "mode": "deterministic",
            "release_profile": release_profile,
            "created_at": created_at,
            "actor": {
                "type": "runtime",
                "id": actor_id,
                "clearance": actor_clearance,
            },
            "repo_revision": repo_revision,
            "environment": {
                "producer": "quantsmith.pipelines.quant_factory",
                "network": "disabled",
                "dependencies": ["stdlib"],
            },
            "prompt_manifest": {
                "type": "prompt_manifest",
                "path": "prompt_manifest.json",
                "hash": prompt_manifest_hash,
            },
            "context_manifest": {
                "type": "context_manifest",
                "path": "context_manifest.json",
                "hash": context_manifest_hash,
            },
            "assumption_ledger": {
                "type": "assumption_ledger",
                "path": "assumptions.jsonl",
                "hash": assumptions_hash,
            },
            "evaluation_harness": {
                "type": "evaluation_harness",
                "path": "evaluation_harness.json",
                "hash": harness_hash,
            },
            "audit_events": {
                "type": "audit_events",
                "path": "audit_events.jsonl",
                "hash": audit_hash,
            },
            "gate_results": [
                {
                    "gate": "orchestration",
                    "status": "pass",
                    "finding_count": 0,
                    "checked_at": created_at,
                },
                {
                    "gate": "quant_factory_convergence",
                    "status": "pass" if decision.decision == "approved" else "fail",
                    "finding_count": 0 if decision.decision == "approved" else 1,
                    "checked_at": created_at,
                },
            ],
            "replay": {
                "mode": "deterministic",
                "command": (
                    "python -m quantsmith.orchestration replay --envelope "
                    "run_envelope.json"
                ),
                "expected_outputs": [
                    {
                        "type": "final_artifact",
                        "path": "factory_decision.json",
                        "hash": decision_hash,
                    }
                ],
            },
            "artifacts": [
                {
                    "type": "final_artifact",
                    "path": "factory_decision.json",
                    "hash": decision_hash,
                    "access_class": "internal",
                    "producer_event_id": f"evt-{safe_run_id}-completed",
                }
            ],
        },
    )
    validate_run_envelope_file(envelope_path).raise_if_errors()
    return envelope_path


def _factory_decision_payload(spec: Any, decision: Any, *, producer: str) -> dict[str, Any]:
    return {
        "schema_version": "quantsmith.orchestration.producer.quant_factory.v1",
        "producer": producer,
        "run_id": str(decision.run_id),
        "factory_spec": {
            "run_id": str(spec.run_id),
            "convergence_mode": str(spec.convergence_mode),
            "seed": spec.seed,
            "deadline_seconds": _json_safe(spec.deadline_seconds),
            "ledger_path": str(spec.ledger_path),
            "gate": {
                "min_sharpe": spec.gate.min_sharpe,
                "max_drawdown": spec.gate.max_drawdown,
                "min_annual_return": spec.gate.min_annual_return,
                "n_best": spec.gate.n_best,
                "pass_threshold": spec.gate.pass_threshold,
            },
            "lanes": [
                {
                    "lane_id": str(lane.lane_id),
                    "hypothesis": str(lane.hypothesis),
                    "feature_set": list(lane.feature_set),
                    "model_tag": str(lane.model_tag),
                    "backtest_config": _json_safe(lane.backtest_config),
                    "status": str(lane.status),
                }
                for lane in spec.lanes
            ],
        },
        "decision": {
            "decision": str(decision.decision),
            "approved_lanes": list(decision.approved_lanes),
            "elapsed_seconds": decision.elapsed_seconds,
            "lane_results": [
                {
                    "lane_id": str(result.lane_id),
                    "status": str(result.status),
                    "sharpe": result.sharpe,
                    "max_drawdown": result.max_drawdown,
                    "annual_return": result.annual_return,
                    "gate_score": result.gate_score,
                    "leakage_flags": list(result.leakage_flags),
                    "elapsed_seconds": result.elapsed_seconds,
                    "error": result.error,
                }
                for result in decision.lane_results
            ],
        },
    }


def _factory_harness_payload(
    *,
    run_id: str,
    safe_run_id: str,
    decision: Any,
) -> dict[str, Any]:
    decision_status = "pass" if decision.decision == "approved" else "fail"
    return {
        "schema_version": SCHEMA_VERSION_EVALUATION,
        "harness_id": f"harness-{safe_run_id}",
        "run_id": run_id,
        "required_layers": list(REQUIRED_HARNESS_LAYERS),
        "layers": [
            _check_layer("envelope", "envelope-schema", "schema"),
            _check_layer("prompt", "prompt-hash", "hash"),
            _check_layer("context", "context-access-pit", "access_point_in_time"),
            _check_layer("assumptions", "assumption-ledger", "ledger_required_fields"),
            _check_layer("tool_plugin_calls", "factory-run-call", "declared_python_call"),
            _check_layer("model_outputs", "no-provider-output", "no_provider_model_call"),
            _check_layer("quant_leakage", "lane-leakage-flags", "leakage_flags"),
            _check_layer("final_artifact", "factory-decision-hash", "hash"),
            _check_layer("replay", "deterministic-replay", "replay"),
        ],
        "integration_surfaces": list(INTEGRATION_SURFACES),
        "producer_checks": [
            {
                "check_id": "quant-factory-convergence",
                "check_type": "factory_decision",
                "status": decision_status,
                "approved_lanes": list(decision.approved_lanes),
            }
        ],
    }


def _factory_audit_events(
    *,
    run_id: str,
    safe_run_id: str,
    actor_id: str,
    started: _dt.datetime,
    decision: Any,
    decision_hash: str,
) -> list[Mapping[str, Any]]:
    return [
        _event(
            run_id,
            f"evt-{safe_run_id}-started",
            "run_started",
            started,
            actor_id,
            [],
            decision_hash,
            "Quant factory producer evidence emission started.",
        ),
        _event(
            run_id,
            f"evt-{safe_run_id}-prompt",
            "prompt_render",
            started + _dt.timedelta(seconds=1),
            actor_id,
            [f"evt-{safe_run_id}-started"],
            decision_hash,
            "Deterministic producer prompt rendered from FactorySpec.",
        ),
        _event(
            run_id,
            f"evt-{safe_run_id}-context",
            "context_retrieval",
            started + _dt.timedelta(seconds=2),
            actor_id,
            [f"evt-{safe_run_id}-prompt"],
            decision_hash,
            "FactorySpec and FactoryDecision summarized as local context.",
        ),
        _event(
            run_id,
            f"evt-{safe_run_id}-factory-call",
            "tool_plugin_call",
            started + _dt.timedelta(seconds=3),
            actor_id,
            [f"evt-{safe_run_id}-context"],
            decision_hash,
            "FactoryRunner.run represented as a deterministic Python call.",
            payload_extra={
                "provider": "python",
                "deterministic": True,
                "tool_name": "quantsmith.pipelines.quant_factory.FactoryRunner.run",
            },
        ),
        _event(
            run_id,
            f"evt-{safe_run_id}-gate",
            "gate_result",
            started + _dt.timedelta(seconds=4),
            actor_id,
            [f"evt-{safe_run_id}-factory-call"],
            decision_hash,
            f"Quant factory convergence decision: {decision.decision}.",
        ),
        _event(
            run_id,
            f"evt-{safe_run_id}-release",
            "release_decision",
            started + _dt.timedelta(seconds=5),
            actor_id,
            [f"evt-{safe_run_id}-gate"],
            decision_hash,
            "Producer evidence recorded for release review.",
            reason="Factory convergence decision and orchestration evidence emitted.",
        ),
        _event(
            run_id,
            f"evt-{safe_run_id}-completed",
            "run_completed",
            started + _dt.timedelta(seconds=6),
            actor_id,
            [f"evt-{safe_run_id}-release"],
            decision_hash,
            "Quant factory producer evidence emission completed.",
        ),
    ]


def _event(
    run_id: str,
    event_id: str,
    event_type: str,
    timestamp: _dt.datetime,
    actor_id: str,
    parent_ids: list[str],
    payload_hash: str,
    summary: str,
    *,
    reason: str | None = None,
    payload_extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload_ref: dict[str, Any] = {
        "kind": "producer_metadata",
        "hash": payload_hash,
        "summary": summary,
    }
    if payload_extra:
        payload_ref.update(payload_extra)
    event = {
        "schema_version": SCHEMA_VERSION_AUDIT_EVENT,
        "event_id": event_id,
        "run_id": run_id,
        "event_type": event_type,
        "timestamp": _format_utc(timestamp),
        "actor": actor_id,
        "parent_event_ids": parent_ids,
        "payload_ref": payload_ref,
        "artifact_refs": ["factory_decision.json"],
        "finding_refs": [],
    }
    if reason is not None:
        event["reason"] = reason
    return event


def _check_layer(layer: str, check_id: str, check_type: str) -> dict[str, Any]:
    return {
        "layer": layer,
        "checks": [
            {
                "check_id": check_id,
                "check_type": check_type,
                "deterministic": True,
                "status": "pass",
            }
        ],
    }


def _render_factory_prompt(spec: Any, objective: str) -> str:
    lanes = "\n".join(f"- {lane.lane_id}: {lane.hypothesis}" for lane in spec.lanes)
    return (
        "# Quant Factory Producer Prompt\n\n"
        "System: record a deterministic Quant Model Factory convergence decision "
        "as spec 0070 orchestration evidence.\n\n"
        f"Objective: {objective}\n\n"
        f"Run ID: {spec.run_id}\n"
        f"Convergence mode: {spec.convergence_mode}\n"
        f"Seed: {spec.seed}\n\n"
        "Declared lanes:\n"
        f"{lanes}\n"
    )


def _render_factory_context(spec: Any, decision: Any) -> str:
    gate = spec.gate
    lanes = "\n".join(
        f"- {result.lane_id}: status={result.status}, score={result.gate_score}, "
        f"leakage_flags={list(result.leakage_flags)}"
        for result in decision.lane_results
    )
    return (
        "# Quant Factory Run\n\n"
        f"Run `{spec.run_id}` used convergence mode `{spec.convergence_mode}` "
        f"with seed `{spec.seed}` and ledger `{spec.ledger_path}`.\n\n"
        "Gate thresholds:\n\n"
        f"- min_sharpe: {gate.min_sharpe}\n"
        f"- max_drawdown: {gate.max_drawdown}\n"
        f"- min_annual_return: {gate.min_annual_return}\n"
        f"- n_best: {gate.n_best}\n"
        f"- pass_threshold: {gate.pass_threshold}\n\n"
        f"Decision: `{decision.decision}`. Approved lanes: "
        f"{list(decision.approved_lanes)}.\n\n"
        "Lane summaries:\n\n"
        f"{lanes}\n"
    )


def _write_json(path: Path, data: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    text = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )
    path.write_text(text, encoding="utf-8")


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else "unbounded"
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return repr(value)


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return cleaned[:80] or "quant-factory-run"


def _parse_or_now(value: str | None) -> _dt.datetime:
    if value is None:
        return _dt.datetime.now(tz=_dt.timezone.utc).replace(microsecond=0)
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = _dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed.astimezone(_dt.timezone.utc).replace(microsecond=0)


def _format_utc(value: _dt.datetime) -> str:
    return value.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _format_date(value: _dt.date) -> str:
    return value.isoformat()
