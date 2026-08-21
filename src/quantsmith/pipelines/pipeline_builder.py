"""Reference pipeline for spec 0042 -- pipeline builder.

The design-time layer that runs *before* a pipeline's step implementations
exist. ``0011`` (``data_pipeline.py``) already owns execution -- ``Pipeline``,
``Step``, ``DataContract``, ``run``, ``backfill`` -- so this module does not
run anything. It compiles a declared intent into a validated DAG, reviews it
against ``instructions/pipeline_engineering.md``'s checklist, renders a
reviewable ``templates/data/pipeline_manifest.md``-shaped document, and hands
a bound ``Pipeline`` back to ``0011`` once implementations are ready.

Two properties are deliberate and worth stating plainly:

* **DAG validity is decided by ``0011``, not here.** ``compile_intent``
  constructs a real ``Pipeline`` with placeholder step functions purely to
  borrow its topological sort, which already rejects cycles, unknown
  dependencies, and duplicate step names. A second implementation could drift
  from ``0011``'s and disagree about what a valid pipeline is -- the one thing
  a build-time checker must never do. That placeholder ``Pipeline`` is local
  to validation and is never returned; ``to_pipeline`` is the only function
  that yields a runnable object, and it requires real implementations.

* **This module reviews declarations, not implementations.** It cannot verify
  that a step is genuinely idempotent, or genuinely tested -- those are claims
  made by whoever wrote the intent. The rendered manifest says so, and lists
  what is still outstanding, rather than presenting an unreviewed pipeline as
  ready.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .data_pipeline import DataContract, Pipeline, Step, StepFn

BLOCKING = "blocking"
ADVISORY = "advisory"

VALID_KINDS = ("source", "transform", "sink")
VALID_CLASSIFICATIONS = ("public", "internal", "confidential", "restricted")

# Template section headers (templates/data/pipeline_manifest.md), plus the
# disclosed seventh section that carries real review findings.
MANIFEST_SECTIONS = (
    "## Ownership",
    "## Schedule",
    "## Inputs & Outputs",
    "## Reliability",
    "## Observability & Runbook",
    "## DAG",
    "## Readiness",
)

_DECLARED_NOT_VERIFIED = (
    "Every property below is **declared** by the pipeline's intent and "
    "reviewed for completeness -- it is **not verified** against a running "
    "pipeline. Idempotency, retry behaviour, and test coverage are claims "
    "until `data_pipeline.run` (spec `0011`) exercises them."
)


# ---------------------------------------------------------------------------
# Intent
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StepIntent:
    """One declared step: what it is, what it depends on, what it emits."""

    name: str
    kind: str  # "source" | "transform" | "sink"
    deps: Tuple[str, ...] = ()
    contract: Optional[DataContract] = None
    dataset: str = ""
    connection: str = ""
    max_attempts: int = 1
    tested: bool = False  # declared, not verified


@dataclass(frozen=True)
class PipelineIntent:
    """A declared pipeline, ahead of any implementation existing."""

    name: str
    owner: str
    steps: Tuple[StepIntent, ...]
    classification: str = ""
    schedule: str = ""
    partitioning: str = ""
    retry_policy: str = ""
    backfill_policy: str = ""
    idempotency_key: str = ""
    freshness_sla: str = ""
    runbook: str = ""
    escalation: str = ""
    deployment_note: str = ""


# ---------------------------------------------------------------------------
# Findings -- REQ-002
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReadinessFinding:
    code: str
    severity: str  # BLOCKING | ADVISORY
    subject: str  # step name, or the pipeline name
    message: str


@dataclass(frozen=True)
class CompiledPipeline:
    intent: PipelineIntent
    dag_order: Tuple[str, ...]
    findings: Tuple[ReadinessFinding, ...]

    @property
    def blocking_findings(self) -> Tuple[ReadinessFinding, ...]:
        return tuple(f for f in self.findings if f.severity == BLOCKING)

    @property
    def advisory_findings(self) -> Tuple[ReadinessFinding, ...]:
        return tuple(f for f in self.findings if f.severity == ADVISORY)

    @property
    def is_shippable(self) -> bool:
        """A valid graph and nothing blocking outstanding."""
        return bool(self.dag_order) and not self.blocking_findings


def review_readiness(intent: PipelineIntent) -> List[ReadinessFinding]:
    """Check an intent against ``instructions/pipeline_engineering.md``.

    Every check runs and every violation is reported -- a design review wants
    all of its problems at once, not the first one. Findings accumulate in a
    stable order (pipeline-level first, then steps in declaration order), so
    the result is deterministic.
    """
    findings: List[ReadinessFinding] = []
    subject = intent.name or "<unnamed pipeline>"

    def block(code: str, subj: str, message: str) -> None:
        findings.append(ReadinessFinding(code, BLOCKING, subj, message))

    def advise(code: str, subj: str, message: str) -> None:
        findings.append(ReadinessFinding(code, ADVISORY, subj, message))

    # -- pipeline level ----------------------------------------------------
    if not intent.steps:
        block("no-steps", subject, "the pipeline declares no steps")
    for field_name, code, label in (
        ("owner", "no-owner", "an owner or steward"),
        ("schedule", "no-schedule", "a schedule or cadence"),
        ("retry_policy", "no-retry-policy", "a retry policy"),
        ("backfill_policy", "no-backfill-policy", "a backfill policy"),
        ("idempotency_key", "no-idempotency-key", "an idempotency key"),
        ("runbook", "no-runbook", "a runbook"),
    ):
        if not str(getattr(intent, field_name)).strip():
            block(code, subject, f"the pipeline declares no {label}")

    if not intent.classification.strip():
        advise("no-classification", subject, "the pipeline declares no data classification")
    elif intent.classification not in VALID_CLASSIFICATIONS:
        advise(
            "unknown-classification",
            subject,
            f"classification {intent.classification!r} is not one of "
            f"{', '.join(VALID_CLASSIFICATIONS)}",
        )
    for field_name, code, label in (
        ("partitioning", "no-partitioning", "a partitioning scheme"),
        ("freshness_sla", "no-freshness-sla", "a freshness SLA"),
        ("escalation", "no-escalation", "an escalation path"),
        ("deployment_note", "no-deployment-note", "a deployment note"),
    ):
        if not str(getattr(intent, field_name)).strip():
            advise(code, subject, f"the pipeline declares no {label}")

    # -- step level --------------------------------------------------------
    for step in intent.steps:
        if step.contract is None:
            block(
                "no-contract",
                step.name,
                "the step declares no output data contract; a violation could "
                "reach a downstream step unchecked",
            )
        if step.kind not in VALID_KINDS:
            block(
                "unknown-kind",
                step.name,
                f"kind {step.kind!r} is not one of {', '.join(VALID_KINDS)}",
            )
        if step.kind == "source" and step.deps:
            block(
                "source-with-deps",
                step.name,
                "a source step must not declare upstream dependencies",
            )
        if step.max_attempts < 1:
            block(
                "unbounded-attempts",
                step.name,
                f"max_attempts is {step.max_attempts}; retries must be at least 1",
            )
        if not step.tested:
            advise("not-tested", step.name, "the step is not declared as tested")
        if step.kind in ("source", "sink") and not step.connection.strip():
            advise(
                "no-connection",
                step.name,
                f"the {step.kind} step declares no connection or system",
            )
        if not step.dataset.strip():
            advise("no-dataset", step.name, "the step declares no dataset name")
        if step.kind in ("transform", "sink") and not step.deps:
            advise(
                "no-upstream",
                step.name,
                f"the {step.kind} step declares no upstream dependency",
            )

    return findings


# ---------------------------------------------------------------------------
# Compilation -- REQ-001
# ---------------------------------------------------------------------------


def _placeholder(_inputs: Dict[str, List[dict]], _partition: int) -> List[dict]:
    """Stand-in step body used only to borrow 0011's graph validation."""
    return []


def _steps_for(intent: PipelineIntent, fns: Optional[Dict[str, StepFn]]) -> List[Step]:
    return [
        Step(
            name=s.name,
            fn=(fns[s.name] if fns is not None else _placeholder),
            deps=tuple(s.deps),
            contract=s.contract,
            max_attempts=max(s.max_attempts, 1),
        )
        for s in intent.steps
    ]


def compile_intent(intent: PipelineIntent) -> CompiledPipeline:
    """Validate the intent's graph and readiness, without running anything.

    The graph is validated by constructing a real ``0011`` ``Pipeline`` with
    placeholder step bodies, so cycles, unknown dependencies, and duplicate
    step names are rejected by ``0011``'s own topological sort. Those come
    back as blocking findings rather than exceptions, so a review sees every
    problem at once.
    """
    findings = review_readiness(intent)
    dag_order: Tuple[str, ...] = ()
    try:
        dag_order = tuple(Pipeline(_steps_for(intent, None)).order)
    except ValueError as exc:
        findings.append(
            ReadinessFinding(
                code="invalid-dag",
                severity=BLOCKING,
                subject=intent.name or "<unnamed pipeline>",
                message=str(exc),
            )
        )
    return CompiledPipeline(intent=intent, dag_order=dag_order, findings=tuple(findings))


# ---------------------------------------------------------------------------
# Handoff to 0011 -- REQ-005
# ---------------------------------------------------------------------------


def to_pipeline(intent: PipelineIntent, step_fns: Dict[str, StepFn]) -> Pipeline:
    """Bind implementations and return a runnable ``0011`` ``Pipeline``.

    Refuses an intent that is not shippable, or one whose steps are not all
    implemented -- this is the handoff edge, and it should not produce a
    half-bound pipeline.
    """
    compiled = compile_intent(intent)
    if not compiled.is_shippable:
        reasons = "; ".join(f"{f.code} ({f.subject})" for f in compiled.blocking_findings)
        raise ValueError(
            f"intent {intent.name!r} is not shippable: {reasons or 'no valid DAG order'}"
        )
    missing = sorted(s.name for s in intent.steps if s.name not in step_fns)
    if missing:
        raise ValueError(f"no implementation supplied for step(s): {', '.join(missing)}")
    return Pipeline(_steps_for(intent, step_fns))


# ---------------------------------------------------------------------------
# Manifest rendering -- REQ-003 / REQ-004
# ---------------------------------------------------------------------------


def _cell(value: object) -> str:
    """Make a value safe inside a Markdown table cell."""
    text = str(value).replace("|", "\\|")
    return " ".join(text.split()) or "—"


def _direction(kind: str) -> str:
    return {"source": "input", "sink": "output"}.get(kind, "intermediate")


def render_pipeline_manifest(
    intent: PipelineIntent,
    compiled: CompiledPipeline,
    spec_id: str = "",
    last_updated: str = "",
) -> str:
    """Render a ``templates/data/pipeline_manifest.md``-shaped document.

    Populated from the real compiled DAG order, the real per-step
    dependencies, and the real findings. States explicitly that its contents
    are declared and reviewed, not verified against a running pipeline
    (REQ-004).
    """
    out: List[str] = []
    out.append(f"# Pipeline Manifest: {intent.name}")
    out.append("")
    out.append("> Generated by `render_pipeline_manifest` (spec `0042-pipeline-builder`).")
    out.append(f"> {_DECLARED_NOT_VERIFIED}")
    if spec_id:
        out.append(">")
        out.append(f"> **Spec:** {spec_id}")
    if last_updated:
        out.append(f"> **Last updated:** {last_updated}")
    out.append("")

    out.append("## Ownership")
    out.append("")
    out.append(f"- **Owner / steward:** {intent.owner or '— not declared'}")
    out.append(f"- **Classification:** {intent.classification or '— not declared'}")
    out.append("")

    out.append("## Schedule")
    out.append("")
    out.append(f"- **Cadence / schedule:** {intent.schedule or '— not declared'}")
    out.append(f"- **Partitioning:** {intent.partitioning or '— not declared'}")
    out.append("")

    out.append("## Inputs & Outputs")
    out.append("")
    out.append("| Direction | Dataset | Source / sink | Data contract |")
    out.append("| --- | --- | --- | --- |")
    for step in intent.steps:
        contract = f"`{step.contract.name}`" if step.contract is not None else "**none declared**"
        out.append(
            f"| {_direction(step.kind)} | {_cell(step.dataset)} | "
            f"{_cell(step.connection)} | {contract} |"
        )
    out.append("")

    out.append("## Reliability")
    out.append("")
    out.append(f"- **Retry policy:** {intent.retry_policy or '— not declared'}")
    out.append(f"- **Backfill:** {intent.backfill_policy or '— not declared'}")
    out.append(f"- **Idempotency:** {intent.idempotency_key or '— not declared'}")
    out.append("")

    out.append("## Observability & Runbook")
    out.append("")
    out.append(f"- **Freshness / SLA:** {intent.freshness_sla or '— not declared'}")
    out.append(f"- **Runbook / on-call:** {intent.runbook or '— not declared'}")
    out.append(f"- **Escalation:** {intent.escalation or '— not declared'}")
    out.append(f"- **Deployment:** {intent.deployment_note or '— not declared'}")
    out.append("")

    out.append("## DAG")
    out.append("")
    out.append("```text")
    if compiled.dag_order:
        width = max(len(s.name) for s in intent.steps)
        for name in compiled.dag_order:
            step = next(s for s in intent.steps if s.name == name)
            upstream = ", ".join(step.deps) if step.deps else "(no upstream)"
            out.append(f"{name.ljust(width)}  [{step.kind}]  <- {upstream}")
        out.append("")
        out.append(f"execution order: {', '.join(compiled.dag_order)}")
    else:
        out.append("no valid execution order — the declared graph is invalid")
    out.append("```")
    out.append("")
    out.append(
        "Steps are listed in execution order, each with its own declared upstream "
        "dependencies. Runtime: `src/quantsmith/pipelines/data_pipeline.py` (`0011`); "
        "observability: `src/quantsmith/pipelines/pipeline_observability.py` (`0019`)."
    )
    out.append("")

    out.append("## Readiness")
    out.append("")
    status = "ready to bind" if compiled.is_shippable else "not ready"
    out.append(
        f"- **Status:** {status} "
        f"({len(compiled.blocking_findings)} blocking, "
        f"{len(compiled.advisory_findings)} advisory)"
    )
    out.append("")
    if compiled.findings:
        out.append("| Severity | Subject | Finding |")
        out.append("| --- | --- | --- |")
        for f in compiled.findings:
            out.append(f"| {f.severity} | {_cell(f.subject)} | {_cell(f.message)} |")
    else:
        out.append("No findings: every checked declaration is present.")
    out.append("")

    return "\n".join(out)
