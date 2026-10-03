"""Organization link-prediction baseline for spec 0095.

Scores unobserved links between **organizations** (co-investment, co-filing, supplier) with classic
neighbourhood measures and evaluates them on a temporal holdout: the graph is rebuilt as of a split
date, and the links that appear afterwards are the answers. Individuals are out of scope: nodes must be
organizations, and a node typed as a person is rejected. Scores are indicators of structural proximity,
not evidence that a relationship exists or is warranted.
"""

from __future__ import annotations

import math
import random
from itertools import combinations
from typing import Any, Dict, FrozenSet, List, Mapping, Sequence, Set, Tuple

from .validation import day, require_min_n

Edge = Tuple[str, str, str]                    # (node_a, node_b, known_at)
PERSON_TYPES = {"person", "individual", "founder", "officer", "employee"}


def validate_nodes(node_types: Mapping[str, str]) -> None:
    """Reject any node typed as a person; this model is organization-level only."""
    bad = sorted(n for n, t in node_types.items() if str(t).lower() in PERSON_TYPES)
    if bad:
        raise ValueError(f"person nodes are out of scope for link prediction: {', '.join(bad)}")


def build_adjacency(edges: Sequence[Edge], as_of: str) -> Dict[str, Set[str]]:
    cutoff = day(as_of)
    adj: Dict[str, Set[str]] = {}
    for a, b, known in edges:
        if a == b or day(known) > cutoff:
            continue
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    return adj


def common_neighbors(adj: Mapping[str, Set[str]], a: str, b: str) -> float:
    return float(len(adj.get(a, set()) & adj.get(b, set())))


def jaccard(adj: Mapping[str, Set[str]], a: str, b: str) -> float:
    union = adj.get(a, set()) | adj.get(b, set())
    return len(adj.get(a, set()) & adj.get(b, set())) / len(union) if union else 0.0


def adamic_adar(adj: Mapping[str, Set[str]], a: str, b: str) -> float:
    return sum(1.0 / math.log(len(adj[z])) for z in adj.get(a, set()) & adj.get(b, set()) if len(adj[z]) > 1)


def preferential_attachment(adj: Mapping[str, Set[str]], a: str, b: str) -> float:
    return float(len(adj.get(a, set())) * len(adj.get(b, set())))


SCORERS = {"common_neighbors": common_neighbors, "jaccard": jaccard, "adamic_adar": adamic_adar,
           "preferential_attachment": preferential_attachment}


def auc(pos: Sequence[float], neg: Sequence[float]) -> float:
    """Probability a random positive outscores a random negative (ties count half)."""
    if not pos or not neg:
        raise ValueError("need positive and negative scores")
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def temporal_link_split(edges: Sequence[Edge], split: str, seed: int, neg_per_pos: int = 5) -> Dict[str, Any]:
    """Train graph as of ``split``; positives = new links between known nodes; negatives = sampled non-links."""
    adj = build_adjacency(edges, split)
    train_pairs: Set[FrozenSet[str]] = {frozenset((a, b)) for a, nbrs in adj.items() for b in nbrs}
    nodes = sorted(adj)
    pos: List[Tuple[str, str]] = []
    pos_set: Set[FrozenSet[str]] = set()
    for a, b, known in sorted(edges, key=lambda e: (e[2], e[0], e[1])):
        pair = frozenset((a, b))
        if day(known) > day(split) and a in adj and b in adj and pair not in train_pairs and pair not in pos_set and a != b:
            pos.append((a, b))
            pos_set.add(pair)
    rng = random.Random(f"links-{seed}")
    forbidden = train_pairs | pos_set
    candidates = [(a, b) for a, b in combinations(nodes, 2) if frozenset((a, b)) not in forbidden]
    k = min(len(candidates), neg_per_pos * len(pos))
    neg = rng.sample(candidates, k) if k else []
    return {"adjacency": adj, "positives": pos, "negatives": neg, "split": day(split).isoformat()}


def evaluate_scorers(edges: Sequence[Edge], split: str, seed: int = 0, neg_per_pos: int = 5,
                     min_pos: int = 20) -> Dict[str, Any]:
    """AUC of each scorer on the temporal holdout, plus a random baseline. Refuses fewer than ``min_pos`` new links."""
    sp = temporal_link_split(edges, split, seed, neg_per_pos)
    require_min_n(len(sp["positives"]), min_pos, "link prediction positives")
    adj = sp["adjacency"]
    out: Dict[str, Any] = {"n_positives": len(sp["positives"]), "n_negatives": len(sp["negatives"]), "auc": {}}
    for name, fn in SCORERS.items():
        out["auc"][name] = auc([fn(adj, a, b) for a, b in sp["positives"]], [fn(adj, a, b) for a, b in sp["negatives"]])
    rng = random.Random(f"links-random-{seed}")
    out["auc"]["random"] = auc([rng.random() for _ in sp["positives"]], [rng.random() for _ in sp["negatives"]])
    out["beats_degree_baseline"] = {n: out["auc"][n] > out["auc"]["preferential_attachment"]
                                    for n in ("common_neighbors", "jaccard", "adamic_adar")}
    out["note"] = "structural proximity only; synthetic data cannot show real predictive value"
    return out
