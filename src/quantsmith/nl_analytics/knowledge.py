"""Opt-in knowledge candidates from published insights. Spec ``0080`` (REQ-022, AC-031).

A published answer can be proposed as a ``0048``/``0049`` knowledge candidate
— a reviewable observation, never a live record. This module only *builds*
the candidate with ``workflow_memory.propose_records``, which is pure; staging
it into ``memory/inbox/`` is the caller's explicit step
(``workflow_memory.stage_candidates``), and only a human's ``promote`` ever
turns it into a record. So asking a question never writes to memory.

Standard library and in-repo modules only.
"""

from __future__ import annotations

import datetime
from collections.abc import Mapping, Sequence

from quantsmith.pipelines import workflow_memory as wm

from .insights import Insight
from .plan import QueryPlan

WORKFLOW = "nl_analytics"
DEFAULT_TARGET_CATALOG = "nl_analytics/insights.yaml"


def knowledge_candidate(
    plan: QueryPlan,
    insights: Sequence[Insight],
    records: Sequence[Mapping[str, object]],
    *,
    run_id: str,
    metric_definition_hash: str,
    as_of: int,
    proposed_at: datetime.date,
    target_catalog: str = DEFAULT_TARGET_CATALOG,
    access_level: str = "internal",
) -> wm.Candidate:
    """One low-confidence ``metric`` candidate for the answer's headline insight.

    Its evidence cites everything needed to trace it back: the run id, plan
    hash, written record keys, metric-definition hash, and as-of period
    (REQ-022). ``proposed_at`` is caller-supplied, since this package reads
    no clock (NFR-002).
    """
    if not insights:
        raise ValueError("an answer with no insights has nothing to propose")
    evidence = {
        "source_run": run_id,
        "plan_hash": plan.content_hash(),
        "record_keys": ",".join(str(r["record_key"]) for r in records),
        "metric_definition_hash": metric_definition_hash,
        "as_of_period": str(as_of),
        "interpreter": plan.interpreter,
    }
    spec = wm.CandidateSpec(
        scope=f"metric:{plan.metric}", type="metric", statement=insights[0].statement,
        confidence="low", pit_scope="<= run date", evidence=(evidence,),
        target_catalog=target_catalog, access_level=access_level,
    )
    return wm.propose_records([spec], workflow=WORKFLOW, source_run=run_id, proposed_at=proposed_at)[0]
