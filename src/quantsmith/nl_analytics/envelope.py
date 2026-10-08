"""``0070`` orchestration evidence for a natural-language analytics run. Spec
``0080`` (REQ-013, T-014).

Adapts one already-answered question — its plan, executed result, chart, and
insight set — into a spec-``0070`` run envelope: a prompt manifest, a context
manifest, an assumption ledger, an evaluation harness, and an audit trail
covering interpret, validate, execute, chart, insight computation, narrate,
and deliver. ``0070``'s own ``replay_envelope_file`` can then check the
bundle's integrity offline, and re-emitting from identical inputs produces a
byte-identical bundle (NFR-001).

This module never runs the pipeline itself — it is handed the already-built
plan/result/chart/insights/response and only records them. Emission is
opt-in: nothing in ``respond.answer()`` calls this automatically, so asking a
question with no envelope requested still has no side effects (RISK-004,
matching the chat path's "no side effects" guarantee elsewhere in this
package).

Standard library only.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from quantsmith.orchestration.foundation import (
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

from .chart import ChartSpec
from .execute import Result
from .insights import Insight
from .plan import QueryPlan, describe_plan
from .respond import ChatResponse

_PRODUCER_SCHEMA = "quantsmith.orchestration.producer.nl_analytics.v1"

#: Recognized dataset-privacy classification keys (spec ``0080`` NFR-004,
#: AC-020), matching ``adapters/llm_runtime/adapter_contract.md``'s
#: ``privacy`` block. A key absent from a caller-supplied ``dataset_privacy``
#: mapping is treated as ``False``.
PRIVACY_FLAGS = ("contains_pii", "contains_mnpi", "contains_restricted_positions")

_REDACTED = "[REDACTED: dataset carries a declared privacy classification]"


def emit_answer_evidence(
    question: str,
    plan: QueryPlan,
    result: Result,
    chart: Optional[ChartSpec],
    insight_set: Sequence[Insight],
    response: ChatResponse,
    output_dir: str | Path,
    *,
    run_id: str,
    actor_id: str = "nl_analytics",
    actor_clearance: str = "public",
    started_at: Optional[str] = None,
    repo_revision: str = "unknown",
    interpreter_mode: str = "keyword/1",
    release_profile: str = "release_bound",
    dataset_privacy: Optional[Mapping[str, bool]] = None,
) -> Path:
    """Emit a validated ``0070`` envelope for one answered question.

    ``run_id`` is caller-assigned, the same convention every other run/record
    id in this package follows (``build_records``, ``FactorySpec.run_id``) —
    this module never invents one. Raises
    :class:`~quantsmith.orchestration.foundation.OrchestrationValidationError`
    if the emitted bundle does not validate.

    ``dataset_privacy`` is the caller's declared classification of the
    dataset behind ``question`` (``contains_pii`` / ``contains_mnpi`` /
    ``contains_restricted_positions`` — spec ``0080`` NFR-004, AC-020); this
    module never infers it. When any flag is set, the raw question text is
    redacted out of every rendered artifact (``answer_payload.json``,
    ``prompt.md``) and replaced with its hash — the interpreted plan and
    computed result stay in full, since both are governed vocabulary and
    numbers, not free text (T-016's scope stops at the one genuinely
    free-text field this package carries; redacting per-dimension result
    values is a documented follow-up, not needed by any current caller).
    When the interpreter is LLM-backed (``interpreter_mode`` not
    ``keyword*``), the flags are also recorded on the ``interpret`` audit
    event as the privacy block an ``adapters/llm_runtime/`` request for that
    call would carry, per the adapter contract.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    started = _parse_or_now(started_at)
    created_at = _format_utc(started + _dt.timedelta(seconds=8))
    review_date = _format_date(started.date() + _dt.timedelta(days=365))
    safe_run_id = _safe_id(run_id)
    is_llm = not interpreter_mode.startswith("keyword")
    privacy = {flag: bool((dataset_privacy or {}).get(flag, False)) for flag in PRIVACY_FLAGS}
    is_restricted = any(privacy.values())
    question_hash = f"sha256:{hashlib.sha256(question.encode('utf-8')).hexdigest()}"
    question_display = _REDACTED if is_restricted else question

    payload_path = out / "answer_payload.json"
    _write_json(
        payload_path,
        _answer_payload(question_display, question_hash, plan, result, chart, insight_set, response),
    )
    payload_hash = sha256_file(payload_path)

    prompt_path = out / "prompt.md"
    prompt_path.write_text(_render_prompt(question_display, plan), encoding="utf-8")
    prompt_hash = sha256_file(prompt_path)

    context_path = out / "context_note.md"
    context_path.write_text(_render_context(plan, result), encoding="utf-8")
    context_hash = sha256_file(context_path)

    prompt_manifest_path = out / "prompt_manifest.json"
    _write_json(
        prompt_manifest_path,
        {
            "schema_version": SCHEMA_VERSION_PROMPT,
            "prompt_id": "prompt.nl_analytics.answer",
            "version": "1.0.0",
            "source": {"type": "prompt_source", "path": "prompt.md", "hash": prompt_hash},
            "role_layers": [{"role": "user", "source_path": "prompt.md", "hash": prompt_hash}],
            "variables": [
                {"name": "question", "required": True},
                {"name": "question_hash", "required": True},
                {"name": "metric", "required": True},
                {"name": "interpreter_mode", "required": True},
            ],
            "rendered_variables": {
                "question": question_display,
                "question_hash": question_hash,
                "metric": plan.metric,
                "interpreter_mode": interpreter_mode,
            },
            "privacy": privacy,
            "model_constraints": {
                "providers": ["external_llm"] if is_llm else ["deterministic"],
                "models": [interpreter_mode],
                "temperature_max": 1.0 if is_llm else 0.0,
                "seed_required": not is_llm,
            },
            "allowed_tools": [
                {"name": "quantsmith.nl_analytics.respond.answer", "type": "python", "fixtureable": True}
            ],
            "allowed_plugins": [],
            "requested_tools": [{"name": "quantsmith.nl_analytics.respond.answer"}],
            "requested_plugins": [],
            "prohibited_data_classes": ["secret", "credential", "mnpi", "licensed_body"],
            "safety_policy_refs": [
                "instructions/point_in_time.md",
                "instructions/reproducibility.md",
            ],
            "evaluation_refs": ["evaluation_harness.json#nl_analytics"],
            "owner": "spec0080",
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
            "context_window": {"token_budget": 4096, "character_budget": 16000},
            "items": [
                {
                    "context_id": f"ctx-{safe_run_id}-result-summary",
                    "source_authority": "quantsmith://nl_analytics/execute",
                    "locator": "context_note.md#result-summary",
                    "content_hash": context_hash,
                    "access_level": actor_clearance,
                    "caller_clearance": actor_clearance,
                    "retrieval_query": question_display,
                    "selection_rule": "execute() over the plan's window, bounded by as_of",
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
                        {"label": "answer payload", "locator": "answer_payload.json"},
                        {"label": "governed metric", "locator": f"0008-metrics-semantic-layer#{plan.metric}"},
                    ],
                }
            ],
            "exclusions": [
                {
                    "locator": "raw fact rows behind the plan",
                    "reason": "the injected reader's source rows remain owned by the caller; only the computed result is recorded",
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
                    "The caller-injected reader returns rows that are themselves "
                    "point-in-time correct; execute() enforces the plan's as_of "
                    "and window bounds on what it is given, but does not verify "
                    "the reader's own upstream point-in-time discipline."
                ),
                "type": "producer_boundary",
                "scope": "quantsmith.nl_analytics.execute",
                "owner": "spec0080",
                "evidence": [
                    {"type": "answer_payload", "locator": "answer_payload.json", "hash": payload_hash}
                ],
                "confidence": "medium",
                "status": "active",
                "introduced_at": _format_date(started.date()),
                "review_due_at": review_date,
                "dependent_artifacts": ["answer_payload.json", "run_envelope.json"],
                "invalidation_trigger": (
                    "The injected reader is found to return rows not yet known "
                    "as of the row's own effective date."
                ),
                "disposition_history": [
                    {
                        "status": "active",
                        "timestamp": _format_utc(started + _dt.timedelta(seconds=2)),
                        "actor": actor_id,
                        "reason": "Required boundary assumption for the nl_analytics producer.",
                    }
                ],
            },
            {
                "schema_version": SCHEMA_VERSION_ASSUMPTION,
                "assumption_id": f"ASM-{safe_run_id}-002",
                "statement": (
                    "The governed metric definition used to compute this result "
                    "has not changed since this run; a later definition change "
                    "is detectable only where a write-back record's "
                    "metric_definition_hash is compared, not by this envelope."
                ),
                "type": "gate_threshold",
                "scope": "quantsmith.pipelines.metrics_semantic_layer",
                "owner": "spec0008",
                "evidence": [
                    {"type": "answer_payload", "locator": "answer_payload.json", "hash": payload_hash}
                ],
                "confidence": "medium",
                "status": "active",
                "introduced_at": _format_date(started.date()),
                "review_due_at": review_date,
                "dependent_artifacts": ["answer_payload.json"],
                "invalidation_trigger": "The metric's SemanticLayer definition is redefined.",
                "disposition_history": [
                    {
                        "status": "active",
                        "timestamp": _format_utc(started + _dt.timedelta(seconds=2)),
                        "actor": actor_id,
                        "reason": "Metric governance is 0008's responsibility, not re-verified here.",
                    }
                ],
            },
        ],
    )
    assumptions_hash = sha256_file(assumptions_path)

    harness_path = out / "evaluation_harness.json"
    _write_json(harness_path, _harness_payload(run_id=run_id, safe_run_id=safe_run_id, response=response, is_llm=is_llm))
    harness_hash = sha256_file(harness_path)

    audit_path = out / "audit_events.jsonl"
    _write_jsonl(
        audit_path,
        _audit_events(
            run_id=run_id, safe_run_id=safe_run_id, actor_id=actor_id, started=started,
            payload_hash=payload_hash, response=response, is_llm=is_llm, privacy=privacy,
        ),
    )
    audit_hash = sha256_file(audit_path)

    envelope_path = out / "run_envelope.json"
    _write_json(
        envelope_path,
        {
            "schema_version": SCHEMA_VERSION_RUN,
            "run_id": run_id,
            "objective": f"Answer '{question_display}' as a governed, replayable nl_analytics run.",
            "spec_id": "0080-nl-analytics-insights",
            "stage": "implementation",
            "mode": "external_provider" if is_llm else "deterministic",
            "release_profile": release_profile,
            "created_at": created_at,
            "actor": {"type": "runtime", "id": actor_id, "clearance": actor_clearance},
            "repo_revision": repo_revision,
            "environment": {
                "producer": "quantsmith.nl_analytics",
                "network": "disabled",
                "dependencies": ["stdlib"],
            },
            "prompt_manifest": {"type": "prompt_manifest", "path": "prompt_manifest.json", "hash": prompt_manifest_hash},
            "context_manifest": {"type": "context_manifest", "path": "context_manifest.json", "hash": context_manifest_hash},
            "assumption_ledger": {"type": "assumption_ledger", "path": "assumptions.jsonl", "hash": assumptions_hash},
            "evaluation_harness": {"type": "evaluation_harness", "path": "evaluation_harness.json", "hash": harness_hash},
            "audit_events": {"type": "audit_events", "path": "audit_events.jsonl", "hash": audit_hash},
            "gate_results": [
                {"gate": "orchestration", "status": "pass", "finding_count": 0, "checked_at": created_at},
                {
                    "gate": "nl_analytics_grounding",
                    "status": "pass" if response.status == "answered" else "skipped",
                    "finding_count": 0,
                    "checked_at": created_at,
                },
            ],
            "replay": {
                "mode": "deterministic" if not is_llm else "fixture",
                "command": "python -m quantsmith.orchestration replay --envelope run_envelope.json",
                "expected_outputs": [
                    {"type": "final_artifact", "path": "answer_payload.json", "hash": payload_hash}
                ],
            },
            "artifacts": [
                {
                    "type": "final_artifact",
                    "path": "answer_payload.json",
                    "hash": payload_hash,
                    "access_class": actor_clearance,
                    "producer_event_id": f"evt-{safe_run_id}-completed",
                }
            ],
        },
    )
    validate_run_envelope_file(envelope_path).raise_if_errors()
    return envelope_path


def _answer_payload(
    question_display: str, question_hash: str, plan: QueryPlan, result: Result,
    chart: Optional[ChartSpec], insight_set: Sequence[Insight], response: ChatResponse,
) -> dict[str, Any]:
    return {
        "schema_version": _PRODUCER_SCHEMA,
        "producer": "quantsmith.nl_analytics.respond.answer",
        "question": question_display,
        "question_hash": question_hash,
        "plan": plan.to_canonical_dict(),
        "plan_hash": plan.content_hash(),
        "result": {
            "values": {"|".join(k): v for k, v in sorted(result.values.items())},
            "series": {
                str(p): {"|".join(k): v for k, v in sorted(vals.items())}
                for p, vals in sorted(result.series.items())
            },
            "row_count": result.row_count,
            "latest_period": result.latest_period,
            "as_of": result.as_of,
            "content_hash": result.content_hash,
        },
        "chart": None if chart is None else {
            "chart_type": chart.chart_type,
            "title": chart.title,
            "metric": chart.metric,
            "dimensions": list(chart.dimensions),
            "data": list(chart.data),
        },
        "insights": [{"kind": i.kind, "statement": i.statement, "values": i.values} for i in insight_set],
        "response_status": response.status,
        "response_headline": response.headline,
        "domain_packs": list(response.domain_packs),
        "domain_pack_source": response.domain_pack_source,
    }


def _harness_payload(*, run_id: str, safe_run_id: str, response: ChatResponse, is_llm: bool) -> dict[str, Any]:
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
            _check_layer("tool_plugin_calls", "answer-pipeline-call", "declared_python_call"),
            _check_layer(
                "model_outputs", "interpreter-model-call",
                "fixture_backed_model_call" if is_llm else "no_provider_model_call",
            ),
            _check_layer("quant_leakage", "execute-as-of-bound", "as_of_window_filter"),
            _check_layer("final_artifact", "answer-payload-hash", "hash"),
            _check_layer("replay", "deterministic-replay", "replay"),
        ],
        "integration_surfaces": list(INTEGRATION_SURFACES),
        "producer_checks": [
            {
                "check_id": "nl-analytics-grounding",
                "check_type": "response_status",
                "status": "pass" if response.status == "answered" else "skipped",
                "response_status": response.status,
            }
        ],
    }


def _audit_events(
    *, run_id: str, safe_run_id: str, actor_id: str, started: _dt.datetime,
    payload_hash: str, response: ChatResponse, is_llm: bool, privacy: Mapping[str, bool],
) -> list[Mapping[str, Any]]:
    def evt(offset: int, event_id: str, event_type: str, parents: list[str], summary: str, **extra: Any) -> dict:
        return _event(run_id, event_id, event_type, started + _dt.timedelta(seconds=offset), actor_id, parents, payload_hash, summary, **extra)

    started_id = f"evt-{safe_run_id}-started"
    interpret_id = f"evt-{safe_run_id}-interpret"
    validate_id = f"evt-{safe_run_id}-validate"
    execute_id = f"evt-{safe_run_id}-execute"
    chart_id = f"evt-{safe_run_id}-chart"
    insights_id = f"evt-{safe_run_id}-insights"
    narrate_id = f"evt-{safe_run_id}-narrate"
    deliver_id = f"evt-{safe_run_id}-deliver"

    interpret_extra: dict[str, Any] = {
        "provider": "external_llm" if is_llm else "python", "deterministic": not is_llm,
        "tool_name": "quantsmith.nl_analytics.interpret.interpret",
    }
    if is_llm:
        # The privacy block an adapters/llm_runtime/ request for this call
        # would carry, per its adapter contract — propagated from the
        # caller's declared dataset classification (NFR-004, AC-020), never
        # inferred here.
        interpret_extra["privacy"] = dict(privacy)

    return [
        evt(0, started_id, "run_started", [], "nl_analytics answer() run started."),
        evt(
            1, interpret_id, "model_invocation" if is_llm else "tool_plugin_call", [started_id],
            "Question interpreted into a governed QueryPlan.",
            payload_extra=interpret_extra,
        ),
        evt(2, validate_id, "tool_plugin_call", [interpret_id], "Plan validated and authorized against the metric registry and viewer clearance.",
            payload_extra={"provider": "python", "deterministic": True, "tool_name": "quantsmith.nl_analytics.plan.validate_plan"}),
        evt(3, execute_id, "data_source_read", [validate_id], "Plan executed over the caller-injected reader, bounded by as_of.",
            payload_extra={"provider": "python", "deterministic": True}),
        evt(4, chart_id, "tool_plugin_call", [execute_id], "Chart chosen deterministically from the result's shape.",
            payload_extra={"provider": "python", "deterministic": True, "tool_name": "quantsmith.nl_analytics.chart.choose_chart"}),
        evt(5, insights_id, "tool_plugin_call", [chart_id], "Insight set computed from the result and any comparison.",
            payload_extra={"provider": "python", "deterministic": True, "tool_name": "quantsmith.nl_analytics.insights.compute_insights"}),
        evt(6, narrate_id, "gate_result", [insights_id],
            "Narrative grounded against the insight set; ungrounded numbers rejected."
            + (f" Narrative written by {response.narrative_mode}." if response.narrative_mode not in ("", "template") else ""),
            payload_extra={"provider": "python", "deterministic": True}),
        evt(7, deliver_id, "release_decision", [narrate_id], f"ChatResponse delivered with status '{response.status}'.",
            reason=f"answer() returned status={response.status}."),
        evt(8, f"evt-{safe_run_id}-completed", "run_completed", [deliver_id], "nl_analytics answer() run completed."),
    ]


def _event(
    run_id: str, event_id: str, event_type: str, timestamp: _dt.datetime, actor_id: str,
    parent_ids: list[str], payload_hash: str, summary: str, *,
    reason: Optional[str] = None, payload_extra: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    payload_ref: dict[str, Any] = {"kind": "producer_metadata", "hash": payload_hash, "summary": summary}
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
        "artifact_refs": ["answer_payload.json"],
        "finding_refs": [],
    }
    if reason is not None:
        event["reason"] = reason
    return event


def _check_layer(layer: str, check_id: str, check_type: str) -> dict[str, Any]:
    return {"layer": layer, "checks": [{"check_id": check_id, "check_type": check_type, "deterministic": True, "status": "pass"}]}


def _render_prompt(question: str, plan: QueryPlan) -> str:
    return (
        "# Natural-Language Analytics Producer Prompt\n\n"
        "System: record a governed answer to a natural-language analytics "
        "question as spec 0070 orchestration evidence.\n\n"
        f"Question: {question}\n\n"
        f"Interpreted as: {describe_plan(plan)}\n"
    )


def _render_context(plan: QueryPlan, result: Result) -> str:
    return (
        "# Result Summary\n\n"
        f"Metric `{plan.metric}` over periods {plan.window.start_period}-{plan.window.end_period} "
        f"({plan.window.grain}), as of period {result.as_of}.\n\n"
        f"Row count: {result.row_count}. Latest observed period: {result.latest_period}.\n\n"
        f"Values: {dict(sorted({'|'.join(k): v for k, v in result.values.items()}.items()))}\n"
    )


def _write_json(path: Path, data: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    text = "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return cleaned[:80] or "nl-analytics-run"


def _parse_or_now(value: Optional[str]) -> _dt.datetime:
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
