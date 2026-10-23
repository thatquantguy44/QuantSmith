"""Typed governed-first routing and the shadow-mode SQL tail.

Spec ``0116`` REQ-009–REQ-010.  Every question is offered to ``0080`` first.
The interpreter result is recorded as a *typed* value during that call so an
unknown governed metric can be distinguished from ambiguity, access masking,
or another governed clarification without parsing exception text.  Only the
exact no-match clarification may enter the retrieval-first SQL tail.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from quantsmith.nl_analytics.interpret import (  # type: ignore[import-untyped]
    InterpretContext,
    Interpreter,
    KeywordInterpreter,
)
from quantsmith.nl_analytics.plan import (  # type: ignore[import-untyped]
    Clarification,
    QueryPlan,
)
from quantsmith.nl_analytics.respond import (  # type: ignore[import-untyped]
    AnswerContext,
    ChatResponse,
    answer,
)

from ..access import Caller, scrub
from ..access import caller as resolve_caller
from ..compose import CompositionError, CompositionRecord, CompositionRequest, compose
from ..config import Config
from ..execute import ExecutionError, ExecutionResult, QueryOnlyAdapter, execute
from ..index import Index
from ..verify import verify
from . import packs as packs_mod
from .reader import FactBatchEvidence, MetricSourceUnavailable, Reader

__all__ = ["AskOutcome", "AskRequest", "RouteEvent", "ask"]

_NO_MATCH = "no known metric matched the question"
_SHADOW_CAVEAT = "Shadow-mode SQL result; claim-level grounding and the release gate are deferred to spec 0117."


@dataclass(frozen=True)
class AskRequest:
    question: str
    as_of: str
    caller: str
    profile: str
    params: Mapping[str, Any] = field(default_factory=dict)
    pit_columns: tuple[str, ...] = ()
    default_window_periods: int = 1
    max_repairs: int = 1

    def __post_init__(self) -> None:
        if not self.question.strip():
            raise ValueError("ask question is empty")
        _as_of_period(self.as_of)
        if self.default_window_periods < 1:
            raise ValueError("default_window_periods must be positive")
        if self.max_repairs not in (0, 1, 2):
            raise ValueError("max_repairs must be between zero and two")


@dataclass(frozen=True)
class RouteEvent:
    event: str
    ok: bool
    code: str | None = None
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AskOutcome:
    route: str
    tier: str | None
    reason: str
    trace: tuple[RouteEvent, ...]
    answer: ChatResponse | None = None
    governed_evidence: FactBatchEvidence | None = None
    composition: CompositionRecord | None = None
    execution: ExecutionResult | None = None
    citations: tuple[str, ...] = ()
    caveats: tuple[str, ...] = ()
    error_code: str | None = None

    def as_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "route": self.route,
            "tier": self.tier,
            "reason": self.reason,
            "trace": [event.as_dict() for event in self.trace],
            "citations": list(self.citations),
            "caveats": list(self.caveats),
        }
        if self.answer is not None:
            value["answer"] = asdict(self.answer)
        if self.governed_evidence is not None:
            value["governed_evidence"] = self.governed_evidence.as_dict()
        if self.composition is not None:
            value["composition"] = self.composition.as_dict()
        if self.execution is not None:
            value["execution"] = self.execution.as_dict()
        if self.error_code is not None:
            value["error_code"] = self.error_code
        return value


class _TrackingInterpreter:
    """Delegate interpreter that retains its typed result for routing."""

    def __init__(self, delegate: Interpreter) -> None:
        self.delegate = delegate
        self.last: QueryPlan | Clarification | None = None

    @property
    def name(self) -> str:
        return f"tracked:{self.delegate.name}"

    def interpret(self, question: str, layer: Any, context: InterpretContext) -> QueryPlan | Clarification:
        result = self.delegate.interpret(question, layer, context)
        if not isinstance(result, (QueryPlan, Clarification)):
            raise TypeError("interpreter returned neither QueryPlan nor Clarification")
        self.last = result
        return result


def ask(
    request: AskRequest,
    *,
    config: Config,
    index: Index,
    mapping_report: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    join_graph: Sequence[Mapping[str, Any]],
    source: QueryOnlyAdapter,
    key_id: str,
    signing_key: bytes,
    keys: Mapping[str, bytes],
    now: int | Callable[[], int],
    completer: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    interpreter: Interpreter | None = None,
) -> AskOutcome:
    """Run one governed-first question with a bounded, verified SQL tail."""
    trace: list[RouteEvent] = [RouteEvent("governed_started", True)]
    who = resolve_caller(config, request.caller)
    current_now = now() if callable(now) else now
    profile = config.profile(request.profile)
    if request.profile != snapshot.get("profile"):
        return _failed("governed_unavailable", trace, "profile-mismatch", "E_METRIC_SOURCE_UNAVAILABLE")

    layer, compiled = packs_mod.compile_layer(mapping_report.get("bindings", ()))
    compiled_names = {item["metric"] for item in compiled if item.get("compiled")}
    if not compiled_names:
        return _failed("governed_unavailable", trace, "no governed metrics compiled",
                       "E_METRIC_SOURCE_UNAVAILABLE")
    pack_catalog, _pack_source = packs_mod.resolve(
        config.data.get("governed_tier", {}).get("packs_root"))
    reader = Reader(
        config=config,
        index=index,
        mapping_report=mapping_report,
        snapshot=snapshot,
        join_graph=join_graph,
        caller=who,
        source=source,
        key_id=key_id,
        signing_key=signing_key,
        keys=keys,
        now=current_now,
    )
    tracking = _TrackingInterpreter(interpreter or KeywordInterpreter())
    clearance = who.clearance if who.active else "restricted"
    context = AnswerContext(
        layer=layer,
        reader=reader,
        as_of=_as_of_period(request.as_of),
        interpret_context=InterpretContext(
            today_period=_as_of_period(request.as_of),
            default_grain="day",
            default_window_periods=request.default_window_periods,
        ),
        viewer_clearance=clearance,
        interpreter=tracking,
        synthetic=True,
        dataset_domains=tuple(config.data.get("governed_tier", {}).get("domain_tags") or ()),
        domain_packs=tuple(pack_catalog),
    )
    try:
        governed = answer(request.question, context)
    except MetricSourceUnavailable as exc:
        trace.append(RouteEvent("governed_unavailable", False, exc.code, exc.reason))
        return AskOutcome(
            route="governed_unavailable", tier="governed", reason=str(exc),
            trace=tuple(trace), error_code=exc.code,
        )

    interpreted = tracking.last
    if isinstance(interpreted, Clarification) and interpreted.reason == _NO_MATCH and not interpreted.candidates:
        trace.append(RouteEvent("no_governed_match", True, detail=_NO_MATCH))
        return _tail(
            request,
            config=config,
            index=index,
            snapshot=snapshot,
            join_graph=join_graph,
            source=source,
            who=who,
            key_id=key_id,
            signing_key=signing_key,
            keys=keys,
            now=current_now,
            completer=completer,
            trace=trace,
            profile=profile,
        )

    if governed.status == "clarification_needed":
        trace.append(RouteEvent("governed_clarification", True, detail=governed.reason))
        return AskOutcome(
            route="governed_clarification", tier="governed", reason=governed.reason,
            trace=tuple(trace), answer=governed, citations=governed.citations,
            caveats=governed.caveats,
        )

    plan = interpreted if isinstance(interpreted, QueryPlan) else None
    evidence = reader.evidence.for_plan(plan) if plan is not None else None
    citations = list(governed.citations)
    if evidence is not None:
        citations.extend((
            f"run:{evidence.provenance.run_id}",
            f"query:{evidence.source_query_id}",
            f"catalog:{evidence.provenance.snapshot_id}",
        ))
    trace.append(RouteEvent("governed_completed", True, detail=governed.status))
    return AskOutcome(
        route="governed_answer", tier="governed", reason=governed.reason,
        trace=tuple(trace), answer=governed, governed_evidence=evidence,
        citations=tuple(citations), caveats=governed.caveats,
    )


def _tail(
    request: AskRequest,
    *,
    config: Config,
    index: Index,
    snapshot: Mapping[str, Any],
    join_graph: Sequence[Mapping[str, Any]],
    source: QueryOnlyAdapter,
    who: Caller,
    key_id: str,
    signing_key: bytes,
    keys: Mapping[str, bytes],
    now: int,
    completer: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None,
    trace: list[RouteEvent],
    profile: Mapping[str, Any],
) -> AskOutcome:
    repair: dict[str, Any] | None = None

    def completing(context: Mapping[str, Any]) -> Mapping[str, Any]:
        if completer is None:
            raise LookupError("no completion backend")
        augmented = dict(context)
        augmented["attempt"] = 1 + sum(event.event == "repair_started" for event in trace)
        if repair is not None:
            augmented["repair"] = dict(repair)
        return completer(augmented)

    last_code = "E_VERIFY_UNKNOWN_IDENTIFIER"
    last_reason = "tail composition did not produce a verified query"
    for attempt in range(request.max_repairs + 1):
        try:
            record = compose(
                CompositionRequest(
                    question=request.question,
                    profile=request.profile,
                    params=request.params,
                    as_of=request.as_of,
                    route_outcome="no_governed_match",
                    pit_columns=request.pit_columns,
                ),
                index=index,
                profile=profile,
                snapshot=snapshot,
                completer=completing if completer is not None else None,
            )
        except CompositionError as exc:
            last_code, last_reason = exc.code, exc.message
            trace.append(RouteEvent("composition_rejected", False, exc.code, exc.message))
            if attempt >= request.max_repairs:
                break
            repair = {"stage": "compose", "code": exc.code}
            trace.append(RouteEvent("repair_started", True, exc.code, f"attempt {attempt + 1}"))
            continue

        trace.append(RouteEvent("composed", True, detail=record.path))
        verified = verify(
            record.verification_request(clearance=who.clearance),
            profile=profile,
            snapshot=snapshot,
            join_graph=join_graph,
            config_hash=config.hash,
            key_id=key_id,
            signing_key=signing_key,
            now=now,
            ttl_s=int(config.data["verification"]["token_ttl_s"]),
        )
        if not verified.ok or verified.verified is None:
            finding = verified.findings[0] if verified.findings else None
            last_code = finding.code if finding else "E_VERIFY_UNKNOWN_IDENTIFIER"
            last_reason = finding.message if finding else "verification failed"
            trace.append(RouteEvent("verification_rejected", False, last_code, last_reason))
            if attempt >= request.max_repairs or record.path == "reuse":
                break
            repair = {"stage": "verify", "code": last_code}
            trace.append(RouteEvent("repair_started", True, last_code, f"attempt {attempt + 1}"))
            continue

        trace.append(RouteEvent("verified", True, detail=record.content_hash))
        try:
            result = execute(
                verified.verified,
                token=verified.verified.token,
                params=record.params,
                keys=keys,
                now=now,
                config=config,
                snapshot_id=str(snapshot["snapshot_id"]),
                caller=who,
                source=source,
                source_exemplars=tuple(item["id"] for item in record.source_exemplars),
            )
        except ExecutionError as exc:
            trace.append(RouteEvent("execution_failed", False, exc.code, exc.message))
            return _failed("tail_failed", trace, exc.message, exc.code)
        trace.append(RouteEvent("executed", True, detail=result.provenance.run_id))
        citations = [
            f"run:{result.provenance.run_id}",
            f"query:{record.query_id or result.provenance.sql_hash}",
            f"catalog:{result.provenance.snapshot_id}",
        ]
        citations.extend(
            f"exemplar:{item['query_id'] or item['id']}@{item['repo']}:{item['ref']}"
            for item in record.source_exemplars
        )
        return AskOutcome(
            route="no_governed_match", tier=record.path,
            reason="governed vocabulary did not match; verified shadow-mode tail completed",
            trace=tuple(trace), composition=record, execution=result,
            citations=tuple(citations), caveats=tuple(record.limitations) + (_SHADOW_CAVEAT,),
        )

    return _failed("tail_failed", trace, last_reason, last_code)


def _failed(route: str, trace: Sequence[RouteEvent], reason: str, code: str) -> AskOutcome:
    return AskOutcome(
        route=route, tier=None, reason=scrub(reason), trace=tuple(trace), error_code=code,
    )


def _as_of_period(value: str) -> int:
    parts = value.split("-")
    if (len(parts) != 3 or tuple(map(len, parts)) != (4, 2, 2)
            or not all(part.isdigit() for part in parts)):
        raise ValueError("as_of must be an ISO date YYYY-MM-DD")
    return int("".join(parts))
