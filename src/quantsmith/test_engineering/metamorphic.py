"""Metamorphic relations for numeric callables (spec 0098).

A metamorphic relation says how the output must change when the input is transformed in a known way,
so it needs no expected value: ``f(c*x) == c*f(x)`` for a degree-1 homogeneous function, ``f(permute(x))
== f(x)`` for a symmetric one. ``check_relation`` evaluates a relation on seeded inputs and reports
``holds``, ``violated``, ``inconclusive`` (some case could not be evaluated, none violated) or
``nothing_checked``.

Choose relations you can justify for the model. A relation that does not apply (scaling on a ridge fit,
translation invariance of a function of levels) gives a false failure; each constructor states its
assumption, and the report repeats it. A relation holding on sampled inputs is not a proof for all inputs.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from ._compare import compare_values, to_jsonable
from ._guard import RETURNED, call_guarded, describe_error
from .generators import InputSpec, generate_inputs, rng_for

LIMITS = ("A relation that holds on the sampled inputs is evidence, not a proof for all inputs; it only tests the relation you chose, "
          "and it is a false alarm if that relation does not apply to the model.")


class CaseError(Exception):
    """A callable raised, hung or returned something unusable while a case was evaluated."""


@dataclass
class CaseResult:
    ok: bool
    deviation: float
    detail: dict[str, Any]


Evaluate = Callable[[Any], Any]


@dataclass(frozen=True)
class Relation:
    name: str
    params: Mapping[str, Any]
    assumption: str
    case: Callable[[Evaluate, Any, Any, np.random.Generator, float, float, bool], CaseResult]


def _scalar(value: Any) -> float:
    arr = np.asarray(value, dtype=float).reshape(-1)
    if arr.size != 1:
        raise CaseError(f"relation needs a scalar output, got {arr.size} values")
    return float(arr[0])


def _array(x: Any) -> np.ndarray:
    return np.asarray(x, dtype=float)


def scaling(degree: float = 1.0, factor: float | None = None) -> Relation:
    """``f(c*x) == c**degree * f(x)`` for ``c > 0`` (drawn from [0.5, 4] unless given). Assumes homogeneity of that degree."""
    if factor is not None and not factor > 0:
        raise ValueError("factor must be positive")

    def case(evaluate, x, y, rng, rtol, atol, eq_nan):
        c = float(factor if factor is not None else rng.uniform(0.5, 4.0))
        y2 = evaluate(c * _array(x))
        ok, dev, note = compare_values(y2, (c ** degree) * _array(y), rtol, atol, eq_nan)
        return CaseResult(ok, dev, {"factor": c, "degree": degree, "output": to_jsonable(y), "output_scaled_input": to_jsonable(y2), "note": note})

    return Relation("scaling", {"degree": degree, "factor": factor}, f"f is positively homogeneous of degree {degree}", case)


def translation(output: str = "equivariant", shift: float | None = None) -> Relation:
    """Add a constant ``s`` to every input element. ``equivariant``: ``f(x+s) == f(x)+s`` (a mean). ``invariant``: ``f(x+s) == f(x)`` (a spread)."""
    if output not in ("equivariant", "invariant"):
        raise ValueError("output must be 'equivariant' or 'invariant'")

    def case(evaluate, x, y, rng, rtol, atol, eq_nan):
        s = float(shift if shift is not None else rng.uniform(-2.0, 2.0))
        y2 = evaluate(_array(x) + s)
        expected = _array(y) + s if output == "equivariant" else _array(y)
        ok, dev, note = compare_values(y2, expected, rtol, atol, eq_nan)
        return CaseResult(ok, dev, {"shift": s, "output": to_jsonable(y), "output_shifted_input": to_jsonable(y2), "note": note})

    return Relation("translation", {"output": output, "shift": shift}, f"f is translation-{output}", case)


def permutation(kind: str = "invariant", axis: int = 0, symmetric_output: bool = False) -> Relation:
    """Permute the input along ``axis``. ``invariant``: ``f(Px) == f(x)``. ``equivariant``: ``f(Px) == P f(x)``
    (the output is permuted along its first axis; with ``symmetric_output`` a 2-D output is permuted on both axes)."""
    if kind not in ("invariant", "equivariant"):
        raise ValueError("kind must be 'invariant' or 'equivariant'")

    def case(evaluate, x, y, rng, rtol, atol, eq_nan):
        xa = _array(x)
        if xa.ndim == 0 or not -xa.ndim <= axis < xa.ndim:
            raise CaseError(f"cannot permute axis {axis} of a {xa.ndim}-d input")
        perm = rng.permutation(xa.shape[axis])
        y2 = evaluate(np.take(xa, perm, axis=axis))
        if kind == "invariant":
            expected = _array(y)
        else:
            ya = _array(y)
            if ya.ndim == 0 or ya.shape[0] != perm.size:
                raise CaseError("equivariance needs an output whose first axis matches the permuted axis")
            expected = ya[perm]
            if symmetric_output and ya.ndim == 2:
                expected = expected[:, perm]
        ok, dev, note = compare_values(y2, expected, rtol, atol, eq_nan)
        return CaseResult(ok, dev, {"permutation": perm.tolist(), "output": to_jsonable(y), "output_permuted_input": to_jsonable(y2), "note": note})

    return Relation("permutation", {"kind": kind, "axis": axis, "symmetric_output": symmetric_output},
                    f"f is permutation-{kind} along axis {axis}", case)


def idempotence() -> Relation:
    """``f(f(x)) == f(x)`` (sorting, projection, winsorising, normalising). The output must be a valid input."""
    def case(evaluate, x, y, rng, rtol, atol, eq_nan):
        y2 = evaluate(y)
        ok, dev, note = compare_values(y2, y, rtol, atol, eq_nan)
        return CaseResult(ok, dev, {"output": to_jsonable(y), "output_applied_twice": to_jsonable(y2), "note": note})

    return Relation("idempotence", {}, "f is idempotent and its output is a valid input", case)


def monotone(increasing: bool = True, index: int | None = None, step: float | None = None) -> Relation:
    """Raise one input coordinate (``index``, or one drawn per case) by ``step > 0``; a scalar output must not fall
    (``increasing``) or not rise (``decreasing``). Assumes weak monotonicity in that coordinate."""
    if step is not None and not step > 0:
        raise ValueError("step must be positive")

    def case(evaluate, x, y, rng, rtol, atol, eq_nan):
        xa = _array(x).copy()
        flat = xa.reshape(-1)
        if flat.size == 0:
            raise CaseError("empty input")
        j = int(index) if index is not None else int(rng.integers(0, flat.size))
        if not 0 <= j < flat.size:
            raise CaseError(f"index {j} out of range for {flat.size} elements")
        d = float(step if step is not None else rng.uniform(0.1, 1.0))
        flat[j] += d
        y0, y1 = _scalar(y), _scalar(evaluate(xa))
        fall = (y0 - y1) if increasing else (y1 - y0)                       # positive means the wrong direction
        ok = bool(fall <= atol + rtol * abs(y0))
        return CaseResult(ok, max(0.0, fall), {"index": j, "step": d, "output": y0, "output_after_increase": y1})

    return Relation("monotone", {"increasing": increasing, "index": index, "step": step},
                    f"f is weakly {'increasing' if increasing else 'decreasing'} in the tested coordinate", case)


def symmetry(kind: str = "even") -> Relation:
    """``even``: ``f(-x) == f(x)``. ``odd``: ``f(-x) == -f(x)``."""
    if kind not in ("even", "odd"):
        raise ValueError("kind must be 'even' or 'odd'")

    def case(evaluate, x, y, rng, rtol, atol, eq_nan):
        y2 = evaluate(-_array(x))
        expected = _array(y) if kind == "even" else -_array(y)
        ok, dev, note = compare_values(y2, expected, rtol, atol, eq_nan)
        return CaseResult(ok, dev, {"output": to_jsonable(y), "output_negated_input": to_jsonable(y2), "note": note})

    return Relation("symmetry", {"kind": kind}, f"f is {kind}", case)


RELATIONS: dict[str, Callable[..., Relation]] = {
    "scaling": scaling, "translation": translation, "permutation": permutation,
    "idempotence": idempotence, "monotone": monotone, "symmetry": symmetry,
}


def check_relation(fn: Callable[[Any], Any], relation: Relation, *, inputs: Sequence[Any] | None = None,
                   spec: InputSpec | str | None = None, cases: int = 50, seed: int = 0, rtol: float = 1e-7,
                   atol: float = 1e-9, equal_nan: bool = False, timeout_s: float = 10.0, max_counterexamples: int = 3) -> dict[str, Any]:
    """Check ``relation`` on ``fn`` over seeded inputs (``spec``) or explicit ``inputs``. Case ``i`` draws its input
    from ``rng_for(seed, i)`` and the relation's own randomness from ``rng_for(seed, i, 1)``."""
    if inputs is None and spec is None:
        raise ValueError("give either inputs= or spec= (for example 'vector:5')")
    cases_in = list(inputs) if inputs is not None else generate_inputs(spec, cases, seed)
    deviation_max, evaluated, violations, errors = 0.0, 0, [], []

    for i, x in enumerate(cases_in):
        def evaluate(arg: Any) -> Any:
            kind, value = call_guarded(fn, (arg,), timeout_s)
            if kind != RETURNED:
                raise CaseError(describe_error(kind, value))
            return value

        try:
            y = evaluate(x)
            result = relation.case(evaluate, x, y, rng_for(seed, i, 1), rtol, atol, equal_nan)
        except CaseError as exc:
            errors.append({"case": i, "error": str(exc)})
            continue
        except (TypeError, ValueError) as exc:                          # non-numeric output where the relation needs numbers
            errors.append({"case": i, "error": f"{type(exc).__name__}: {exc}"})
            continue
        evaluated += 1
        deviation_max = max(deviation_max, result.deviation)
        if not result.ok:
            violations.append({"case": i, "input": to_jsonable(x), "deviation": result.deviation, **result.detail})

    if not cases_in:
        status = "nothing_checked"
    elif violations:
        status = "violated"
    elif errors:
        status = "inconclusive"
    else:
        status = "holds"
    return {"check": "metamorphic", "relation": relation.name, "params": dict(relation.params), "assumption": relation.assumption,
            "status": status, "seed": seed, "cases": len(cases_in), "evaluated": evaluated, "violations": len(violations),
            "max_deviation": deviation_max, "tolerance": {"rtol": rtol, "atol": atol, "equal_nan": equal_nan},
            "counterexamples": violations[:max_counterexamples], "errors": errors[:5], "error_count": len(errors),
            "limits": LIMITS}
