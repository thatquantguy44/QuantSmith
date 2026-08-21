"""Reference pipeline for spec 0035 — funding ladder min-cost flow.

Composes an already-shipped, dependency-free solver instead of inventing a new
one: ``min_cost_flow`` (``optimization_solvers.py``, spec 0013) solves a bipartite
``SOURCE -> tenor -> obligation -> SINK`` network that matches a set of future cash
obligations to a set of available funding tenors (overnight, 1-week, 1-month, …) at
minimum total cost. ``optimization_solvers.py`` is not modified.

This is a **general treasury/cash-funding** tool, not a securities-financing one.
It does not model repo, securities-lending, or collateral/haircut mechanics --
that domain stays agent-contract-only and routes to an adopter's own models via
``agents/optimization/model_plugin_registration/`` (spec 0026), per this SDK's
standing direction. It is also a single, static snapshot decision, not a rolling
simulation that re-solves as time or rates change (see spec 0035's Non-Goals).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

from .optimization_solvers import min_cost_flow


@dataclass(frozen=True)
class FundingTenor:
    """A funding instrument: how long it lasts, how much can be drawn, its cost."""

    name: str
    tenor_days: float
    capacity: float
    rate: float


@dataclass(frozen=True)
class FundingObligation:
    """A future cash need: when it's due, and how much must be funded by then."""

    name: str
    horizon_days: float
    notional: float


@dataclass(frozen=True)
class FundingLadderResult:
    status: str  # "optimal" | "infeasible"
    total_cost: float
    allocations: Dict[Tuple[str, str], float] = field(default_factory=dict)
    tenor_utilization: Dict[str, float] = field(default_factory=dict)


def solve_funding_ladder(
    tenors: Sequence[FundingTenor],
    obligations: Sequence[FundingObligation],
) -> FundingLadderResult:
    """Fund every obligation from the eligible, cheapest available tenor capacity.

    A tenor may only fund an obligation it can actually cover: ``tenor.tenor_days
    >= obligation.horizon_days`` (the funding must still be outstanding when the
    obligation is due) -- enforced by edge existence, not a post-hoc filter. Every
    obligation is fully funded (its own ``obligation -> SINK`` edge capacity equals
    its notional) or the result reports ``status="infeasible"`` -- never a partial
    allocation presented as a full solution. Deterministic.
    """
    n_tenors = len(tenors)
    n_obligations = len(obligations)
    source = 0
    tenor_base = 1
    obligation_base = tenor_base + n_tenors
    sink = obligation_base + n_obligations

    edges: List[Tuple[int, int, float, float]] = []
    source_edge_tenor: List[int] = []  # index into tenors, parallel to its edge
    match_edge_pairs: List[Tuple[int, int]] = []  # (tenor_idx, obligation_idx)

    for ti, tenor in enumerate(tenors):
        edges.append((source, tenor_base + ti, tenor.capacity, 0.0))
        source_edge_tenor.append(ti)

    for ti, tenor in enumerate(tenors):
        for oi, obligation in enumerate(obligations):
            if tenor.tenor_days >= obligation.horizon_days:
                cost = tenor.rate * obligation.horizon_days
                edges.append((tenor_base + ti, obligation_base + oi, obligation.notional, cost))
                match_edge_pairs.append((ti, oi))

    n_source_edges = n_tenors
    n_match_edges = len(match_edge_pairs)

    for oi, obligation in enumerate(obligations):
        edges.append((obligation_base + oi, sink, obligation.notional, 0.0))

    required_flow = sum(o.notional for o in obligations)
    n_nodes = sink + 1

    result = min_cost_flow(n_nodes, edges, source=source, sink=sink, required_flow=required_flow)

    if result.status != "optimal":
        return FundingLadderResult(status="infeasible", total_cost=0.0)

    match_flows = result.edge_flows[n_source_edges:n_source_edges + n_match_edges]
    allocations: Dict[Tuple[str, str], float] = {}
    tenor_utilization: Dict[str, float] = {t.name: 0.0 for t in tenors}
    for (ti, oi), flow in zip(match_edge_pairs, match_flows):
        if flow > 1e-9:
            allocations[(tenors[ti].name, obligations[oi].name)] = flow
            tenor_utilization[tenors[ti].name] += flow

    return FundingLadderResult(
        status="optimal",
        total_cost=result.cost,
        allocations=allocations,
        tenor_utilization=tenor_utilization,
    )
