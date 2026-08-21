"""Reference runtime for spec 0055 -- workflow scheduling operations.

This is the local, dependency-free control plane above the scheduler adapters:
declare jobs, validate timing/ownership/idempotency metadata, dry-run a scheduler
deployment, dispatch work with a correlation/idempotency envelope, append a run
ledger, carry manual tasks forward, generate a daily status report, and hand
failures/overdues to alerting without sending anything.

The provider scheduler is still outside this module. Cron/Airflow/GitHub Actions
translate the approved registry entry into their own formats; this module owns the
portable status model.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib
import json
import re
import runpy
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from .alerting import Alert

VALID_ENVIRONMENTS = ("dev", "staging", "prod")
VALID_TARGET_TYPES = (
    "shell",
    "python_module",
    "python_function",
    "quantsmith_pipeline",
    "agentic_workflow",
)
VALID_CALENDARS = ("trading", "business", "daily", "custom")
VALID_TRIGGER_TYPES = ("cron", "interval", "event", "manual")
VALID_RUN_STATUSES = (
    "scheduled",
    "running",
    "completed",
    "failed",
    "skipped",
    "missed",
    "manual_pending",
)
VALID_TASK_STATUSES = ("open", "acknowledged", "completed")

_SECRET_RE = re.compile(
    r"(api[_-]?key|secret|token|password|passwd|authorization:\s*bearer)\s*[:=]\s*"
    r"['\"]?[^'\"\s]+",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str  # "error" | "warn"
    subject: str
    message: str


@dataclass(frozen=True)
class Target:
    type: str
    ref: str
    args: Tuple[str, ...] = ()
    kwargs: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Trigger:
    type: str
    expression: str


@dataclass(frozen=True)
class Schedule:
    timezone: str
    calendar: str
    trigger: Trigger


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    backoff_seconds: int = 0


@dataclass(frozen=True)
class BackfillPolicy:
    allowed: bool = False
    max_lookback_days: int = 0
    idempotency_key_template: str = "{job_id}:{partition}"


@dataclass(frozen=True)
class ManualFollowup:
    task_id: str
    owner: str
    due_offset_days: int = 0
    reminder_cadence: str = "daily"
    title: str = ""


@dataclass(frozen=True)
class ScheduleJob:
    job_id: str
    owner: str
    environment: str
    target: Target
    schedule: Schedule
    retry_policy: RetryPolicy
    backfill_policy: BackfillPolicy
    runbook_uri: str
    alert_route: str
    manual_followups: Tuple[ManualFollowup, ...] = ()
    parameters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RegistryValidation:
    jobs: Tuple[ScheduleJob, ...]
    findings: Tuple[Finding, ...]

    @property
    def is_valid(self) -> bool:
        return not any(f.severity == "error" for f in self.findings)


@dataclass(frozen=True)
class SchedulerDryRun:
    adapter_name: str
    provider: str
    status: str
    provider_schedule_id: Optional[str]
    next_run_utc: Optional[str]
    correlation_id: str
    timestamp_utc: str
    retryable: bool = False
    error_code: Optional[str] = None
    error_message_redacted: Optional[str] = None
    evidence_uri: Optional[str] = None


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    job_id: str
    correlation_id: str
    idempotency_key: str
    scheduled_for_utc: str
    started_at_utc: Optional[str]
    ended_at_utc: Optional[str]
    status: str
    attempt: int
    exit_code: Optional[int] = None
    exception_class: Optional[str] = None
    error_message_redacted: Optional[str] = None
    artifact_uris: Tuple[str, ...] = ()
    log_uri: Optional[str] = None
    manual_task_ids: Tuple[str, ...] = ()
    code_version: Optional[str] = None


@dataclass(frozen=True)
class ManualTask:
    task_id: str
    job_id: str
    owner: str
    title: str
    due_date: dt.date
    reminder_cadence: str
    status: str = "open"
    acknowledged_at_utc: Optional[str] = None
    completed_at_utc: Optional[str] = None
    evidence_uri: Optional[str] = None

    @property
    def is_open(self) -> bool:
        return self.status != "completed"

    def is_overdue(self, as_of: dt.date) -> bool:
        return self.is_open and self.due_date < as_of


@dataclass(frozen=True)
class MemoryCandidate:
    id: str
    scope: str
    type: str
    statement: str
    evidence: Mapping[str, str]
    confidence: str = "low"
    status: str = "candidate"


class ExecutionLedger:
    """Append-only JSONL run ledger.

    ``path=None`` keeps an in-memory ledger for tests and notebooks; a path gives
    the deployable local store the spec calls for. Existing records are read in
    append order, so reports are deterministic.
    """

    def __init__(self, path: Optional[str | Path] = None) -> None:
        self.path = Path(path) if path is not None else None
        self._records: List[RunRecord] = []
        if self.path and self.path.exists():
            for line in self.path.read_text().splitlines():
                if line.strip():
                    self._records.append(_record_from_json(json.loads(line)))

    def append(self, record: RunRecord) -> RunRecord:
        if record.status not in VALID_RUN_STATUSES:
            raise ValueError(f"unknown run status '{record.status}'")
        self._records.append(record)
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(_jsonable(asdict(record)), sort_keys=True) + "\n")
        return record

    def records(self) -> Tuple[RunRecord, ...]:
        return tuple(self._records)

    def completed_by_key(self, job_id: str, idempotency_key: str) -> Optional[RunRecord]:
        for record in reversed(self._records):
            if (
                record.job_id == job_id
                and record.idempotency_key == idempotency_key
                and record.status == "completed"
            ):
                return record
        return None


class ManualTaskQueue:
    """Small first-class queue for manual follow-ups."""

    def __init__(self, tasks: Sequence[ManualTask] = ()) -> None:
        self._tasks: Dict[str, ManualTask] = {t.task_id: t for t in tasks}

    def add(self, task: ManualTask) -> ManualTask:
        self._tasks[task.task_id] = task
        return task

    def add_for_job(self, job: ScheduleJob, base_date: dt.date) -> Tuple[ManualTask, ...]:
        created: List[ManualTask] = []
        for followup in job.manual_followups:
            title = followup.title or f"Manual follow-up for {job.job_id}"
            task = ManualTask(
                task_id=followup.task_id,
                job_id=job.job_id,
                owner=followup.owner,
                title=title,
                due_date=base_date + dt.timedelta(days=followup.due_offset_days),
                reminder_cadence=followup.reminder_cadence,
            )
            created.append(self.add(task))
        return tuple(created)

    def acknowledge(self, task_id: str, timestamp_utc: str) -> ManualTask:
        task = self._tasks[task_id]
        updated = ManualTask(**{**asdict(task), "status": "acknowledged", "acknowledged_at_utc": timestamp_utc})
        self._tasks[task_id] = updated
        return updated

    def complete(self, task_id: str, timestamp_utc: str, evidence_uri: str) -> ManualTask:
        task = self._tasks[task_id]
        updated = ManualTask(
            **{
                **asdict(task),
                "status": "completed",
                "completed_at_utc": timestamp_utc,
                "evidence_uri": evidence_uri,
            }
        )
        self._tasks[task_id] = updated
        return updated

    def open_tasks(self) -> Tuple[ManualTask, ...]:
        return tuple(t for t in self._tasks.values() if t.is_open)

    def overdue(self, as_of: dt.date) -> Tuple[ManualTask, ...]:
        return tuple(t for t in self._tasks.values() if t.is_overdue(as_of))

    def tasks(self) -> Tuple[ManualTask, ...]:
        return tuple(self._tasks.values())


def validate_registry(jobs: Sequence[ScheduleJob]) -> RegistryValidation:
    findings: List[Finding] = []
    seen: set[str] = set()
    for job in jobs:
        subject = job.job_id or "<missing job_id>"
        if not job.job_id.strip():
            findings.append(Finding("missing-job-id", "error", subject, "job_id is required"))
        elif job.job_id in seen:
            findings.append(Finding("duplicate-job-id", "error", subject, "job_id must be unique"))
        seen.add(job.job_id)
        if not job.owner.strip():
            findings.append(Finding("missing-owner", "error", subject, "owner is required"))
        if job.environment not in VALID_ENVIRONMENTS:
            findings.append(Finding("bad-environment", "error", subject, "environment must be dev, staging, or prod"))
        if job.target.type not in VALID_TARGET_TYPES:
            findings.append(Finding("bad-target-type", "error", subject, f"unsupported target type {job.target.type!r}"))
        if not job.target.ref.strip():
            findings.append(Finding("missing-target-ref", "error", subject, "target ref is required"))
        if job.schedule.calendar not in VALID_CALENDARS:
            findings.append(Finding("bad-calendar", "error", subject, "calendar must be trading, business, daily, or custom"))
        try:
            ZoneInfo(job.schedule.timezone)
        except Exception:
            findings.append(Finding("bad-timezone", "error", subject, f"unknown timezone {job.schedule.timezone!r}"))
        if job.schedule.trigger.type not in VALID_TRIGGER_TYPES:
            findings.append(Finding("bad-trigger-type", "error", subject, "trigger type is unsupported"))
        elif job.schedule.trigger.type == "cron":
            try:
                _parse_cron(job.schedule.trigger.expression)
            except ValueError as exc:
                findings.append(Finding("bad-cron", "error", subject, str(exc)))
        if job.retry_policy.max_attempts < 1:
            findings.append(Finding("bad-retry-policy", "error", subject, "max_attempts must be at least 1"))
        if job.retry_policy.backoff_seconds < 0:
            findings.append(Finding("bad-retry-policy", "error", subject, "backoff_seconds cannot be negative"))
        if job.backfill_policy.allowed:
            if job.backfill_policy.max_lookback_days < 1:
                findings.append(Finding("bad-backfill", "error", subject, "allowed backfills need max_lookback_days >= 1"))
            if not job.backfill_policy.idempotency_key_template.strip():
                findings.append(Finding("missing-idempotency", "error", subject, "backfills require idempotency metadata"))
        if not job.runbook_uri.strip():
            findings.append(Finding("missing-runbook", "error", subject, "runbook_uri is required"))
        if not job.alert_route.strip():
            findings.append(Finding("missing-alert-route", "error", subject, "alert_route is required"))
        for followup in job.manual_followups:
            if not followup.task_id.strip():
                findings.append(Finding("missing-manual-task-id", "error", subject, "manual follow-up task_id is required"))
            if not followup.owner.strip():
                findings.append(Finding("missing-manual-owner", "error", subject, "manual follow-up owner is required"))
    return RegistryValidation(tuple(jobs), tuple(findings))


def dry_run_schedule(job: ScheduleJob, now_utc: dt.datetime) -> SchedulerDryRun:
    """Validate provider-neutral schedule metadata and return next-run evidence."""
    validation = validate_registry([job])
    now_utc = _ensure_utc(now_utc)
    correlation_id = _correlation_id(job.job_id, now_utc.isoformat())
    if not validation.is_valid:
        return SchedulerDryRun(
            adapter_name="scheduler",
            provider=job.schedule.trigger.type,
            status="failed",
            provider_schedule_id=None,
            next_run_utc=None,
            correlation_id=correlation_id,
            timestamp_utc=now_utc.isoformat(),
            error_code=validation.findings[0].code,
            error_message_redacted=redact(validation.findings[0].message),
        )
    next_run = _next_run(job, now_utc)
    return SchedulerDryRun(
        adapter_name="scheduler",
        provider=job.schedule.trigger.type,
        status="scheduled",
        provider_schedule_id=f"dry-run:{job.schedule.trigger.type}:{job.job_id}",
        next_run_utc=next_run.isoformat() if next_run else None,
        correlation_id=correlation_id,
        timestamp_utc=now_utc.isoformat(),
        evidence_uri=f"schedule://dry-run/{job.job_id}",
    )


def dispatch_job(
    job: ScheduleJob,
    ledger: ExecutionLedger,
    scheduled_for_utc: dt.datetime,
    *,
    partition: str = "",
    force: bool = False,
    handlers: Optional[Mapping[str, Callable[..., Any]]] = None,
    code_version: Optional[str] = None,
    now_fn: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.timezone.utc),
) -> RunRecord:
    """Run one job target and append a ledger record.

    ``handlers`` is the safe extension point for tests, local pipelines, or future
    agentic runners. If no handler is supplied, shell commands run through
    ``subprocess`` and Python functions/modules resolve by import.
    """
    scheduled_for_utc = _ensure_utc(scheduled_for_utc)
    idempotency_key = _idempotency_key(job, partition, scheduled_for_utc)
    existing = ledger.completed_by_key(job.job_id, idempotency_key)
    run_id = _run_id(job.job_id, idempotency_key, len(ledger.records()) + 1)
    correlation_id = _correlation_id(job.job_id, idempotency_key)
    manual_ids = tuple(f.task_id for f in job.manual_followups)
    if existing and not force:
        return ledger.append(
            RunRecord(
                run_id=run_id,
                job_id=job.job_id,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
                scheduled_for_utc=scheduled_for_utc.isoformat(),
                started_at_utc=None,
                ended_at_utc=_ensure_utc(now_fn()).isoformat(),
                status="skipped",
                attempt=0,
                artifact_uris=(f"existing_run:{existing.run_id}",),
                manual_task_ids=manual_ids,
                code_version=code_version,
            )
        )

    attempts = max(1, job.retry_policy.max_attempts)
    last_error: Optional[BaseException] = None
    started = _ensure_utc(now_fn()).isoformat()
    for attempt in range(1, attempts + 1):
        try:
            artifacts = _invoke_target(job, handlers or {})
            return ledger.append(
                RunRecord(
                    run_id=run_id,
                    job_id=job.job_id,
                    correlation_id=correlation_id,
                    idempotency_key=idempotency_key,
                    scheduled_for_utc=scheduled_for_utc.isoformat(),
                    started_at_utc=started,
                    ended_at_utc=_ensure_utc(now_fn()).isoformat(),
                    status="completed",
                    attempt=attempt,
                    exit_code=0,
                    artifact_uris=tuple(str(a) for a in _as_sequence(artifacts)),
                    manual_task_ids=manual_ids,
                    code_version=code_version,
                )
            )
        except BaseException as exc:  # noqa: BLE001 - status ledger must catch all job failures
            last_error = exc
    assert last_error is not None
    return ledger.append(
        RunRecord(
            run_id=run_id,
            job_id=job.job_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            scheduled_for_utc=scheduled_for_utc.isoformat(),
            started_at_utc=started,
            ended_at_utc=_ensure_utc(now_fn()).isoformat(),
            status="failed",
            attempt=attempts,
            exit_code=1,
            exception_class=last_error.__class__.__name__,
            error_message_redacted=redact(str(last_error)),
            manual_task_ids=manual_ids,
            code_version=code_version,
        )
    )


def render_daily_operations_report(
    records: Sequence[RunRecord],
    tasks: Sequence[ManualTask],
    *,
    report_date: dt.date,
) -> str:
    """Render a deterministic Markdown daily operations report."""
    today_records = [
        r for r in records if dt.datetime.fromisoformat(r.scheduled_for_utc).date() == report_date
    ]
    by_status = {status: [r for r in today_records if r.status == status] for status in VALID_RUN_STATUSES}
    ownerish = _owner_rollup(today_records, tasks)
    lines = [
        f"# Daily Operations Report -- {report_date.isoformat()}",
        "",
        "## Completed Jobs",
        *_record_lines(by_status["completed"]),
        "",
        "## Failed Jobs",
        *_record_lines(by_status["failed"], include_error=True),
        "",
        "## Skipped Or Missed Jobs",
        *_record_lines(by_status["skipped"] + by_status["missed"]),
        "",
        "## Manual Tasks",
        *_task_lines([t for t in tasks if t.is_open], report_date),
        "",
        "## Overdue Reminders",
        *_task_lines([t for t in tasks if t.is_overdue(report_date)], report_date),
        "",
        "## Next Runs",
        *_record_lines([r for r in records if r.status == "scheduled"]),
        "",
        "## Owner / Workflow Rollup",
        *(f"- {k}: {v}" for k, v in ownerish),
    ]
    return "\n".join(lines).rstrip() + "\n"


def alert_handoffs(records: Sequence[RunRecord], tasks: Sequence[ManualTask], *, as_of: dt.date) -> Tuple[Alert, ...]:
    """Return alert payloads only; delivery remains the adapter layer's job."""
    alerts: List[Alert] = []
    for record in records:
        if record.status in ("failed", "missed"):
            alerts.append(
                Alert(
                    rule_id=f"workflow-{record.status}",
                    metric=record.job_id,
                    severity="critical" if record.status == "failed" else "warning",
                    dedup_key=f"{record.job_id}:{record.status}:{record.idempotency_key}",
                    message=redact(f"{record.job_id} {record.status}; see runbook/log evidence"),
                )
            )
    for task in tasks:
        if task.is_overdue(as_of):
            alerts.append(
                Alert(
                    rule_id="manual-task-overdue",
                    metric=task.job_id,
                    severity="warning",
                    dedup_key=f"{task.job_id}:manual:{task.task_id}",
                    message=redact(f"Manual task {task.task_id} overdue for {task.owner}: {task.title}"),
                )
            )
    return tuple(alerts)


def memory_candidates_from_failures(records: Sequence[RunRecord], *, minimum_failures: int = 2) -> Tuple[MemoryCandidate, ...]:
    """Propose durable memory candidates from repeated operational failures."""
    failures: Dict[str, List[RunRecord]] = {}
    for record in records:
        if record.status == "failed":
            failures.setdefault(record.job_id, []).append(record)
    candidates: List[MemoryCandidate] = []
    for job_id in sorted(failures):
        runs = failures[job_id]
        if len(runs) >= minimum_failures:
            digest = hashlib.sha1("|".join(r.run_id for r in runs).encode("utf-8")).hexdigest()[:8]
            candidates.append(
                MemoryCandidate(
                    id=f"MEM-CAND-{job_id}-{digest}",
                    scope=f"workflow:{job_id}",
                    type="pitfall",
                    statement=f"{job_id} has {len(runs)} recurring scheduled-run failures; review runbook and owner routing.",
                    evidence={"source_run": runs[-1].run_id, "corroboration_count": str(len(runs))},
                )
            )
    return tuple(candidates)


def _parse_cron(expr: str) -> Tuple[Tuple[int, ...], Tuple[int, ...], Tuple[int, ...], Tuple[int, ...], Tuple[int, ...]]:
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError("cron expression must have five fields")
    return (
        _parse_cron_field(fields[0], 0, 59),
        _parse_cron_field(fields[1], 0, 23),
        _parse_cron_field(fields[2], 1, 31),
        _parse_cron_field(fields[3], 1, 12),
        _parse_cron_field(fields[4], 0, 7),
    )


def _parse_cron_field(field: str, low: int, high: int) -> Tuple[int, ...]:
    values: set[int] = set()
    for part in field.split(","):
        step = 1
        if "/" in part:
            part, step_s = part.split("/", 1)
            step = int(step_s)
            if step < 1:
                raise ValueError("cron step must be positive")
        if part == "*":
            start, end = low, high
        elif "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s), int(end_s)
        else:
            start = end = int(part)
        if start < low or end > high or start > end:
            raise ValueError(f"cron field {field!r} outside range {low}-{high}")
        values.update(range(start, end + 1, step))
    return tuple(sorted(values))


def _next_run(job: ScheduleJob, now_utc: dt.datetime) -> Optional[dt.datetime]:
    if job.schedule.trigger.type != "cron":
        return None
    minute, hour, dom, month, dow = _parse_cron(job.schedule.trigger.expression)
    tz = ZoneInfo(job.schedule.timezone)
    local = now_utc.astimezone(tz).replace(second=0, microsecond=0) + dt.timedelta(minutes=1)
    for _ in range(60 * 24 * 370):
        cron_dow = (local.weekday() + 1) % 7
        if (
            local.minute in minute
            and local.hour in hour
            and local.day in dom
            and local.month in month
            and (cron_dow in dow or (cron_dow == 0 and 7 in dow))
            and _calendar_allows(job.schedule.calendar, local.date())
        ):
            return local.astimezone(dt.timezone.utc)
        local += dt.timedelta(minutes=1)
    raise ValueError("no next cron run found within 370 days")


def _calendar_allows(calendar: str, date: dt.date) -> bool:
    if calendar in ("business", "trading"):
        return date.weekday() < 5
    return True


def _invoke_target(job: ScheduleJob, handlers: Mapping[str, Callable[..., Any]]) -> Any:
    if job.target.ref in handlers:
        return handlers[job.target.ref](*job.target.args, **dict(job.target.kwargs))
    if job.target.type == "shell":
        result = subprocess.run(
            [job.target.ref, *job.target.args],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"shell exited {result.returncode}")
        return ()
    if job.target.type == "python_function":
        module, _, func = job.target.ref.partition(":")
        if not module or not func:
            raise ValueError("python_function target ref must be 'module:function'")
        callable_ = getattr(importlib.import_module(module), func)
        return callable_(*job.target.args, **dict(job.target.kwargs))
    if job.target.type == "python_module":
        runpy.run_module(job.target.ref, run_name="__main__")
        return ()
    raise RuntimeError(f"target {job.target.type!r} requires a handler")


def _idempotency_key(job: ScheduleJob, partition: str, scheduled_for_utc: dt.datetime) -> str:
    return job.backfill_policy.idempotency_key_template.format(
        job_id=job.job_id,
        partition=partition or scheduled_for_utc.date().isoformat(),
        scheduled_for_utc=scheduled_for_utc.isoformat(),
        environment=job.environment,
    )


def _run_id(job_id: str, key: str, ordinal: int) -> str:
    digest = hashlib.sha1(f"{job_id}:{key}:{ordinal}".encode("utf-8")).hexdigest()[:12]
    return f"run-{digest}"


def _correlation_id(job_id: str, key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"quantsmith:{job_id}:{key}"))


def _ensure_utc(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc)


def _record_from_json(payload: Mapping[str, Any]) -> RunRecord:
    data = dict(payload)
    data["artifact_uris"] = tuple(data.get("artifact_uris") or ())
    data["manual_task_ids"] = tuple(data.get("manual_task_ids") or ())
    return RunRecord(**data)


def _jsonable(value: Any) -> Any:
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return value


def _as_sequence(value: Any) -> Tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(value)
    return (value,)


def redact(text: str) -> str:
    return _SECRET_RE.sub("[REDACTED]", text)


def _record_lines(records: Sequence[RunRecord], *, include_error: bool = False) -> List[str]:
    if not records:
        return ["- None"]
    lines = []
    for record in sorted(records, key=lambda r: (r.job_id, r.scheduled_for_utc, r.run_id)):
        detail = f"- {record.job_id} [{record.status}] run={record.run_id} attempts={record.attempt}"
        if include_error and record.error_message_redacted:
            detail += f" error={record.error_message_redacted}"
        lines.append(detail)
    return lines


def _task_lines(tasks: Sequence[ManualTask], as_of: dt.date) -> List[str]:
    if not tasks:
        return ["- None"]
    lines = []
    for task in sorted(tasks, key=lambda t: (t.owner, t.due_date, t.task_id)):
        overdue = " overdue" if task.is_overdue(as_of) else ""
        lines.append(f"- {task.task_id} [{task.status}{overdue}] owner={task.owner} due={task.due_date}: {task.title}")
    return lines


def _owner_rollup(records: Sequence[RunRecord], tasks: Sequence[ManualTask]) -> List[Tuple[str, str]]:
    counts: Dict[str, Dict[str, int]] = {}
    for record in records:
        counts.setdefault(record.job_id, {}).setdefault(record.status, 0)
        counts[record.job_id][record.status] += 1
    for task in tasks:
        key = f"manual:{task.owner}"
        counts.setdefault(key, {}).setdefault(task.status, 0)
        counts[key][task.status] += 1
    return [(k, ", ".join(f"{status}={counts[k][status]}" for status in sorted(counts[k]))) for k in sorted(counts)]
