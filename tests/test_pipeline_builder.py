"""Acceptance tests for spec 0042 -- pipeline builder.

Each test is named for the acceptance criterion it covers (see
``specs/0042-pipeline-builder/tasks.md``).
"""

from __future__ import annotations

import re

import pytest

from quantsmith.pipelines.data_pipeline import DataContract, Pipeline, run
from quantsmith.pipelines.pipeline_builder import (
    BLOCKING,
    MANIFEST_SECTIONS,
    PipelineIntent,
    StepIntent,
    compile_intent,
    render_pipeline_manifest,
    review_readiness,
    to_pipeline,
)

PRICE_COLUMNS = {"date": str, "security_id": str, "close": float}


def contract(name):
    return DataContract(name=name, columns=PRICE_COLUMNS, required=frozenset({"date"}))


def complete_intent(steps=None):
    """An intent with every declaration present, so findings isolate to the steps."""
    return PipelineIntent(
        name="daily_prices",
        owner="Data Engineering",
        classification="internal",
        schedule="daily 06:00 UTC — cron `0 6 * * *`",
        partitioning="by trading day",
        retry_policy="3 attempts, transient failures only",
        backfill_policy="re-run only missing partitions, 30-day window",
        idempotency_key="(date, security_id)",
        freshness_sla="each step fresh by 07:00 UTC",
        runbook="runbooks/daily_prices.md",
        escalation="page the data-eng on-call rota",
        deployment_note="promoted by pipeline_deployment",
        steps=steps
        if steps is not None
        else (
            StepIntent("pull_prices", "source", (), contract("raw_prices"), "raw_prices", "vendor API", 3, True),
            StepIntent("clean_prices", "transform", ("pull_prices",), contract("clean_prices"), "clean_prices", "", 3, True),
            StepIntent("write_warehouse", "sink", ("clean_prices",), contract("wh_prices"), "wh_prices", "Snowflake", 3, True),
        ),
    )


# --- AC-001: dag order respects dependencies ---


def test_dag_order_respects_dependencies_AC_001():
    intent = complete_intent()
    compiled = compile_intent(intent)
    order = list(compiled.dag_order)
    assert sorted(order) == sorted(s.name for s in intent.steps)
    for step in intent.steps:
        for dep in step.deps:
            assert order.index(dep) < order.index(step.name)
    assert compiled.is_shippable is True


# --- AC-002: a cycle is a blocking finding, not an exception ---


def test_cycle_is_blocking_finding_not_exception_AC_002():
    intent = complete_intent(
        steps=(
            StepIntent("a", "transform", ("b",), contract("a"), "a", "", 1, True),
            StepIntent("b", "transform", ("a",), contract("b"), "b", "", 1, True),
        )
    )
    compiled = compile_intent(intent)  # must not raise
    assert compiled.dag_order == ()
    assert compiled.is_shippable is False
    assert any(f.code == "invalid-dag" and f.severity == BLOCKING for f in compiled.findings)


# --- AC-003: unknown dependency is blocking ---


def test_unknown_dependency_is_blocking_AC_003():
    intent = complete_intent(
        steps=(StepIntent("a", "transform", ("ghost",), contract("a"), "a", "", 1, True),)
    )
    compiled = compile_intent(intent)
    blocking = [f for f in compiled.findings if f.severity == BLOCKING]
    assert any(f.code == "invalid-dag" for f in blocking)
    assert any("ghost" in f.message for f in blocking)


# --- AC-004: a step with no output contract is flagged, named ---


def test_missing_contract_flagged_per_step_AC_004():
    intent = complete_intent(
        steps=(
            StepIntent("pull", "source", (), contract("raw"), "raw", "API", 1, True),
            StepIntent("clean", "transform", ("pull",), None, "clean", "", 1, True),
        )
    )
    findings = review_readiness(intent)
    missing = [f for f in findings if f.code == "no-contract"]
    assert len(missing) == 1
    assert missing[0].subject == "clean"
    assert missing[0].severity == BLOCKING


# --- AC-005: every finding is collected, not just the first ---


def test_all_findings_collected_AC_005():
    intent = PipelineIntent(
        name="bare",
        owner="",  # blocking
        schedule="daily",
        retry_policy="3 attempts",
        backfill_policy="missing only",
        idempotency_key="(date)",
        runbook="",  # blocking
        steps=(
            StepIntent("a", "source", (), None, "a", "API", 1, True),  # no contract
            StepIntent("b", "transform", ("a",), None, "b", "", 1, True),  # no contract
        ),
    )
    codes = [f.code for f in review_readiness(intent)]
    assert "no-owner" in codes
    assert "no-runbook" in codes
    assert codes.count("no-contract") == 2


# --- AC-006: manifest has the template sections and passes the gate's own regexes ---

_GATE_THEMES = [
    r"owner|owned by|steward",
    r"schedule|cron|cadence|frequency",
    r"input|source|output|sink",
    r"retry|backfill|reprocess",
    r"idempoten",
    r"runbook|on-?call|incident|escalation",
]


def test_manifest_satisfies_gate_keywords_AC_006():
    intent = complete_intent()
    doc = render_pipeline_manifest(intent, compile_intent(intent))
    for section in MANIFEST_SECTIONS:
        assert section in doc, f"missing section: {section}"
    for pattern in _GATE_THEMES:
        assert re.search(pattern, doc, re.IGNORECASE), f"gate theme not satisfied: {pattern}"


# --- AC-007: the manifest is explicit that declarations are not verified ---


def test_manifest_states_declared_not_verified_AC_007():
    intent = complete_intent(
        steps=(StepIntent("orphan", "transform", (), None, "", "", 1, False),)
    )
    compiled = compile_intent(intent)
    doc = render_pipeline_manifest(intent, compiled)
    assert "not verified" in doc
    assert "not ready" in doc
    # The specific outstanding finding is named, not summarised away.
    assert "no output data contract" in doc
    assert "orphan" in doc


# --- AC-008: to_pipeline hands off a pipeline that actually runs on 0011 ---


def test_to_pipeline_runs_on_0011_runner_AC_008():
    intent = complete_intent()

    def make_rows(_inputs, _partition):
        return [{"date": "2026-01-02", "security_id": "AAA", "close": 10.0}]

    pipeline = to_pipeline(intent, {s.name: make_rows for s in intent.steps})
    assert isinstance(pipeline, Pipeline)

    manifest = run(pipeline, [1, 2])
    assert manifest.ok()
    assert manifest.partitions_run() == [1, 2]
    assert manifest.status_of("write_warehouse", 1) == "ok"


# --- AC-009: to_pipeline refuses an unshippable intent or an unbound step ---


def test_to_pipeline_refuses_unshippable_or_unbound_AC_009():
    unshippable = complete_intent(
        steps=(StepIntent("a", "source", (), None, "a", "API", 1, True),)  # no contract
    )
    with pytest.raises(ValueError, match="not shippable"):
        to_pipeline(unshippable, {"a": lambda i, p: []})

    ok_intent = complete_intent()
    with pytest.raises(ValueError, match="no implementation supplied"):
        to_pipeline(ok_intent, {"pull_prices": lambda i, p: []})


# --- AC-010: deterministic ---


def test_deterministic_AC_010():
    intent = complete_intent()
    first, second = compile_intent(intent), compile_intent(intent)
    assert first.findings == second.findings
    assert first.dag_order == second.dag_order
    assert render_pipeline_manifest(intent, first) == render_pipeline_manifest(intent, second)
