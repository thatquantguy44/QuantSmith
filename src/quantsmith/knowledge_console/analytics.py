"""Read-only natural-language analytics for the Knowledge Console (spec ``0080`` T-026, REQ-021).

``POST /api/analytics/ask`` answers a data question through ``nl_analytics.answer()``
under the console viewer's clearance (``0058``). Owner decision (2026-10-09): the console
stays read-only (spec ``0057`` NFR-003). This route never writes back, never emits an
envelope, and never stages a knowledge candidate; those stay with the ``nl_analytics``
CLI.

An :class:`AnalyticsService` is built once at server start and injected into the server,
so the handler reads no files and no clock per request. :func:`service_from_files`
builds one from the same registry and fact-row files the ``nl_analytics`` CLI reads,
optionally with a profile-backed LLM interpreter and narrator
(``quantsmith.adapters.llm_runtime``) that fall back to the keyword interpreter and
template narrative when no model is available.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from quantsmith.nl_analytics.authorize import AccessPolicy
from quantsmith.nl_analytics.cli import load_data, load_registry, response_to_dict
from quantsmith.nl_analytics.interpret import (
    InterpretContext,
    KeywordInterpreter,
    LLMInterpreter,
)
from quantsmith.nl_analytics.narrate import LLMNarrator
from quantsmith.nl_analytics.respond import AnswerContext, ChatResponse, answer
from quantsmith.pipelines import access_control
from quantsmith.pipelines.metrics_semantic_layer import SemanticLayer

# What a console caller sends to a model: the governed vocabulary and computed
# aggregates of public market data (the llm-profiles/1 data class).
DATA_CLASSES = ("public_market_data",)


@dataclass
class AnalyticsService:
    """Everything the analytics route needs, fixed at server start."""

    layer: SemanticLayer
    reader: Callable[[Any], Sequence[Any]]
    today_period: int
    default_window_periods: int | None = 7
    default_grain: str = "day"
    as_of: int | None = None
    # ``None`` means the roster is inactive (0058): no filtering, so the
    # viewer is treated as cleared for everything.
    viewer_clearance: str | None = None
    access_policy: AccessPolicy = field(default_factory=AccessPolicy)
    interpreter: Any = None
    narrator: Any = None
    synthetic: bool = False
    dataset_domains: tuple[str, ...] = ()
    domain_packs: tuple[Mapping, ...] = ()

    def ask(self, question: str) -> ChatResponse:
        context = AnswerContext(
            layer=self.layer, reader=self.reader,
            as_of=self.as_of if self.as_of is not None else self.today_period,
            interpret_context=InterpretContext(today_period=self.today_period,
                                               default_window_periods=self.default_window_periods,
                                               default_grain=self.default_grain),
            viewer_clearance=self.viewer_clearance or "restricted",
            access_policy=self.access_policy, interpreter=self.interpreter, narrator=self.narrator,
            synthetic=self.synthetic, dataset_domains=self.dataset_domains, domain_packs=self.domain_packs,
        )
        return answer(question, context)

    def ask_json(self, question: str) -> dict[str, Any]:
        response = self.ask(question)
        out = response_to_dict(response)
        # Read-only surface: no run, envelope, write-back, or knowledge candidate.
        for key in ("run_id", "envelope_uri", "writeback"):
            out.pop(key, None)
        out.update({"vega_lite": response.vega_lite, "narrative": response.narrative,
                    "narrative_mode": response.narrative_mode,
                    "viewer_clearance": self.viewer_clearance, "read_only": True})
        return out


def service_from_files(registry: str, data: str, *, today_period: int, as_of: int | None = None,
                       default_window_periods: int | None = 7, default_grain: str = "day",
                       llm_profiles: str | None = None, viewer_override: str | None = None,
                       access_root: str = ".", synthetic: bool = False) -> AnalyticsService:
    """Build a service from a registry and fact-row files, with optional LLM profiles."""
    layer = load_registry(registry)
    rows = load_data(data)
    interpreter = narrator = None
    if llm_profiles:
        from quantsmith.adapters import llm_runtime

        config = llm_runtime.load_profiles(llm_profiles)
        interpreter = LLMInterpreter(llm_runtime.as_callable(config=config, use="interpreter",
                                                             data_classes=DATA_CLASSES),
                                     fallback=KeywordInterpreter())
        narrator = LLMNarrator(llm_runtime.as_callable(config=config, use="narrator", data_classes=DATA_CLASSES))
    clearance = access_control.resolve_viewer_clearance(override=viewer_override, root=access_root)
    return AnalyticsService(
        layer=layer, reader=lambda plan: rows, today_period=today_period, as_of=as_of,
        default_window_periods=default_window_periods, default_grain=default_grain,
        viewer_clearance=clearance, interpreter=interpreter, narrator=narrator, synthetic=synthetic,
    )
