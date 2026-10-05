"""Flakiness and order-dependence checks (spec 0097).

Re-run a suite several times and classify each test by what the runs show:

* ``stable``            same outcome every run, in the default order
* ``flaky``             outcome changes between identical runs (timing, threads, I/O, randomness)
* ``order_dependent``   passes in the default order but fails when the same tests run in a shuffled order
                        (shared state leaking between tests)
* ``hash_seed_dependent`` outcome changes with ``PYTHONHASHSEED`` (set/dict iteration order assumptions)
* ``always_fails``      fails every time; a real failure, not flakiness

Shuffling uses explicit node ids in a seeded order, so no plugin is needed and the order is reproducible
from the reported seed. A test classed ``stable`` is only stable over the runs made; the report states
how many. Passing reruns do not prove a test is deterministic.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .report import TestResult
from .runners import run_gtest_binary, run_pytest


def to_node_id(cwd, junit_id: str) -> str:
    """Turn a JUnit id (``pkg.mod.Class::test``) into a pytest node id (``pkg/mod.py::Class::test``)."""
    classname, _, name = junit_id.partition("::")
    parts = classname.split(".")
    for i in range(len(parts), 0, -1):
        candidate = Path(cwd).joinpath(*parts[:i]).with_suffix(".py")
        if candidate.is_file():
            return "::".join(["/".join(parts[:i]) + ".py", *parts[i:], name])
    return junit_id


def _outcomes(results: Sequence[TestResult]) -> Dict[str, str]:
    return {r.id: r.status for r in results}


def collect_ids(cwd, args: Sequence[str] = (), python: Optional[str] = None, timeout_s: float = 600.0) -> List[str]:
    """Node ids from one default-order run (a collect-only pass would miss parametrised ids on some setups)."""
    rep = run_pytest(cwd, args, timeout_s, python)
    return [r.id for r in rep.results]


def check_pytest(cwd, args: Sequence[str] = (), runs: int = 5, shuffles: int = 2, hash_seeds: Sequence[str] = ("0", "1", "12345"),
                 seed: int = 20260101, python: Optional[str] = None, timeout_s: float = 600.0,
                 env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Classify tests via repeated, shuffled, and hash-seed-varied runs."""
    default_runs = [run_pytest(cwd, args, timeout_s, python, env_extra=env) for _ in range(max(2, runs))]
    base = default_runs[0]
    if base.verdict in ("no_tests", "error", "timeout") or not base.results:
        return {"verdict": base.verdict, "runs": len(default_runs), "tests": 0, "classification": {}, "flaky": [], "order_dependent": [],
                "hash_seed_dependent": [], "always_fails": [], "note": "nothing to classify; " + (base.notes[0] if base.notes else "no tests were collected")}
    per_run = [_outcomes(r.results) for r in default_runs]
    ids = sorted(set().union(*per_run))
    classification: Dict[str, str] = {}
    for tid in ids:
        seen = {o.get(tid, "missing") for o in per_run}
        classification[tid] = "always_fails" if seen <= {"failed", "error"} else ("flaky" if len(seen) > 1 else "stable")
    shuffle_detail: List[Dict[str, Any]] = []
    order_dep: Dict[str, List[int]] = {}
    runnable = [t for t in ids if classification[t] == "stable" and per_run[0].get(t) == "passed"]
    for k in range(shuffles):
        s = seed + k
        order = list(runnable)
        random.Random(s).shuffle(order)
        rep = run_pytest(cwd, args, timeout_s, python, env_extra=env, ids=[to_node_id(cwd, t) for t in order])
        out = _outcomes(rep.results)
        if not out:
            shuffle_detail.append({"seed": s, "ran": 0, "failed": 0, "error": "shuffled run produced no results; order check not performed"})
            continue
        newly = [t for t in order if out.get(t) in ("failed", "error")]
        shuffle_detail.append({"seed": s, "ran": len(out), "failed": len(newly)})
        for t in newly:
            order_dep.setdefault(t, []).append(s)
            classification[t] = "order_dependent"
    hash_dep: Dict[str, str] = {}
    for hs in hash_seeds:
        rep = run_pytest(cwd, args, timeout_s, python, env_extra={**(env or {}), "PYTHONHASHSEED": hs})
        out = _outcomes(rep.results)
        for t in ids:
            if classification[t] in ("stable",) and per_run[0].get(t) != out.get(t) and t in out:
                hash_dep[t] = hs
                classification[t] = "hash_seed_dependent"
    return {
        "verdict": "flakiness_found" if any(v in ("flaky", "order_dependent", "hash_seed_dependent") for v in classification.values()) else "no_flakiness_observed",
        "runs": len(default_runs), "shuffles": shuffle_detail, "hash_seeds": list(hash_seeds), "tests": len(ids),
        "classification": classification,
        "flaky": [t for t, v in classification.items() if v == "flaky"],
        "order_dependent": [{"test": t, "seed": seeds[0], "seeds": seeds, "failed_in_shuffles": len(seeds),
                            "reproduce": "run the explicit node ids in `random.Random(seed).shuffle` order"} for t, seeds in order_dep.items()],
        "hash_seed_dependent": [{"test": t, "failing_or_differing_seed": s} for t, s in hash_dep.items()],
        "always_fails": [t for t, v in classification.items() if v == "always_fails"],
        "note": f"observed over {len(default_runs)} identical runs, {shuffles} shuffles and {len(hash_seeds)} hash seeds; "
                "no flakiness observed is not proof of determinism",
    }


def check_gtest(binary, cwd, runs: int = 5, shuffles: int = 3, seed: int = 20260101, timeout_s: float = 300.0) -> Dict[str, Any]:
    """Repeat a GoogleTest binary, then run it shuffled with fixed seeds."""
    plain = [run_gtest_binary(binary, cwd, timeout_s=timeout_s) for _ in range(max(2, runs))]
    per_run = [_outcomes(r.results) for r in plain]
    ids = sorted(set().union(*per_run)) if per_run else []
    if not ids:
        return {"verdict": plain[0].verdict if plain else "error", "tests": 0, "flaky": [], "order_dependent": [],
                "note": "nothing to classify; no GoogleTest results were parsed"}
    flaky = [t for t in ids if len({o.get(t, "missing") for o in per_run}) > 1]
    order_dep: List[Dict[str, Any]] = []
    for k in range(shuffles):
        s = seed + k
        rep = run_gtest_binary(binary, cwd, shuffle_seed=s, timeout_s=timeout_s)
        for r in rep.results:
            if r.status in ("failed", "error") and per_run[0].get(r.id) == "passed" and r.id not in flaky:
                order_dep.append({"test": r.id, "seed": s, "reproduce": f"{binary} --gtest_shuffle --gtest_random_seed={s}"})
    return {"verdict": "flakiness_found" if flaky or order_dep else "no_flakiness_observed", "runs": len(plain), "shuffle_seeds": [seed + k for k in range(shuffles)],
            "tests": len(ids), "flaky": flaky, "order_dependent": order_dep,
            "note": "no flakiness observed is not proof of determinism"}
