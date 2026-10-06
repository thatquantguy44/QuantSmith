"""Value comparison and JSON conversion shared by the model-testing helpers (spec 0098)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def as_float_array(value: Any):
    """``value`` as a float array, or ``None`` when it is not numeric."""
    try:
        return np.asarray(value, dtype=float)
    except (TypeError, ValueError):
        return None


def compare_values(actual: Any, expected: Any, rtol: float, atol: float, equal_nan: bool = False) -> tuple[bool, float, str]:
    """``(ok, max_abs_deviation, note)``. Numeric values use ``|a-b| <= atol + rtol*|b|``; shape differences
    and (unless ``equal_nan``) NaNs are deviations; non-numeric values compare with ``==``."""
    a, b = as_float_array(actual), as_float_array(expected)
    if a is None or b is None:
        same = bool(actual == expected)
        return same, 0.0 if same else math.inf, "" if same else "non-numeric values differ"
    if a.shape != b.shape:
        return False, math.inf, f"shape mismatch {a.shape} vs {b.shape}"
    if a.size == 0:
        return True, 0.0, ""
    nan_a, nan_b = np.isnan(a), np.isnan(b)
    if equal_nan:
        both = nan_a & nan_b
        if (nan_a ^ nan_b).any():
            return False, math.inf, "NaN in one value only"
        a, b = np.where(both, 0.0, a), np.where(both, 0.0, b)
    elif nan_a.any() or nan_b.any():
        return False, math.inf, "NaN present"
    same = a == b                                                      # equal infinities count as equal
    with np.errstate(invalid="ignore"):
        diff = np.where(same, 0.0, np.abs(a - b))
        tolerance = atol + rtol * np.abs(b)                            # infinite when b is, and nan for rtol=0 and b infinite
    diff = np.where(np.isnan(diff), math.inf, diff)
    # An infinite expected value is matched only by the same infinity: `inf <= inf` must never make 5.0 agree with inf.
    ok = bool(np.all(same | (np.isfinite(b) & (diff <= tolerance))))
    return ok, float(diff.max()), ""


def to_jsonable(value: Any, max_items: int = 20) -> Any:
    """A JSON-safe, size-capped copy of arrays, scalars and sequences."""
    if isinstance(value, np.ndarray):
        flat = value.reshape(-1)
        shown = [to_jsonable(v) for v in flat[:max_items]]
        return {"shape": list(value.shape), "values": shown, "truncated": bool(flat.size > max_items)}
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v, max_items) for v in list(value)[:max_items]]
    if isinstance(value, (int, str, bool)) or value is None:
        return value
    return repr(value)[:200]
