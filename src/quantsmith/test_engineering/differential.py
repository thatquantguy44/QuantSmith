"""Differential testing: compare implementations of the same computation (spec 0098).

Run two or more callables on the same seeded inputs and compare their outputs within ``rtol``/``atol``:
a solver against an oracle, a new version against the old one, a vectorised rewrite against a loop. The
first implementation (or ``reference``) is the one the others are compared with.

Agreement is not correctness: implementations that share a bug, or the same wrong formula, agree.
Disagreement means at least one is wrong or the tolerance is too tight; the report names the case. ``worst_case`` is the mismatch with the
largest deviation; a difference that is not numeric (one implementation raised, a shape differs) counts as infinite, so it ranks first.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from ._compare import compare_values, to_jsonable
from ._guard import RAISED, RETURNED, TIMEOUT, call_guarded, describe_error
from .generators import InputSpec, generate_inputs

LIMITS = ("Agreement means the implementations gave the same answers on the sampled inputs; implementations that share a bug agree and are both wrong. "
          "Disagreement means at least one is wrong or the tolerance is too tight.")


def compare_implementations(impls: Mapping[str, Callable[[Any], Any]], *, inputs: Sequence[Any] | None = None,
                            spec: InputSpec | str | None = None, cases: int = 50, seed: int = 0, rtol: float = 1e-7,
                            atol: float = 1e-9, equal_nan: bool = False, timeout_s: float = 10.0, reference: str | None = None,
                            same_exception_agrees: bool = True, max_mismatches: int = 3) -> dict[str, Any]:
    names = list(impls)
    if len(names) < 2:
        raise ValueError("give at least two implementations to compare")
    ref = reference or names[0]
    if ref not in impls:
        raise ValueError(f"reference {ref!r} is not one of {names}")
    if inputs is None and spec is None:
        raise ValueError("give either inputs= or spec= (for example 'vector:5')")
    cases_in = list(inputs) if inputs is not None else generate_inputs(spec, cases, seed)
    others = [n for n in names if n != ref]
    summary = {n: {"agreements": 0, "disagreements": 0, "inconclusive": 0, "max_deviation": 0.0} for n in others}
    mismatches: list[dict[str, Any]] = []

    for i, x in enumerate(cases_in):
        outcome = {n: call_guarded(impls[n], (x,), timeout_s) for n in names}
        rk, rv = outcome[ref]
        for n in others:
            k, v = outcome[n]
            row = summary[n]
            if TIMEOUT in (rk, k):
                row["inconclusive"] += 1
                continue
            if rk == k == RAISED:
                same = type(rv) is type(v) and same_exception_agrees
                dev, note = (0.0, "") if same else (math.inf, f"{type(rv).__name__} vs {type(v).__name__}")
                ok = same
            elif rk != k:
                ok, dev = False, math.inf
                note = f"{ref} {rk}, {n} {k}: {describe_error(rk, rv) if rk == RAISED else describe_error(k, v)}"
            else:
                ok, dev, note = compare_values(v, rv, rtol, atol, equal_nan)
            if ok:
                row["agreements"] += 1
                if math.isfinite(dev):
                    row["max_deviation"] = max(row["max_deviation"], dev)
            else:
                row["disagreements"] += 1
                if math.isfinite(dev):
                    row["max_deviation"] = max(row["max_deviation"], dev)
                mismatches.append({"case": i, "implementation": n, "input": to_jsonable(x), "deviation": dev, "note": note,
                                   "reference_output": to_jsonable(rv) if rk == RETURNED else describe_error(rk, rv),
                                   "output": to_jsonable(v) if k == RETURNED else describe_error(k, v)})

    disagreements = sum(r["disagreements"] for r in summary.values())
    inconclusive = sum(r["inconclusive"] for r in summary.values())
    if not cases_in:
        status = "nothing_compared"
    elif disagreements:
        status = "disagree"
    elif inconclusive:
        status = "inconclusive"
    else:
        status = "agree"
    worst = max(mismatches, key=lambda m: m["deviation"], default=None)                  # a non-numeric mismatch (an exception, a shape) is infinite
    return {"check": "differential", "status": status, "reference": ref, "implementations": names, "seed": seed, "cases": len(cases_in),
            "per_implementation": summary, "disagreements": disagreements, "inconclusive": inconclusive,
            "tolerance": {"rtol": rtol, "atol": atol, "equal_nan": equal_nan}, "worst_case": worst,
            "mismatches": mismatches[:max_mismatches], "limits": LIMITS}
