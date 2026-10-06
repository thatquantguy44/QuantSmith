"""Guarded call used by the model-testing helpers (spec 0098).

Calls ``fn(*args)`` with a wall-clock timeout and captures every ordinary exception, so one bad case
cannot hang or abort a whole check. The positional-argument twin of ``edgecases._call``. POSIX only
(SIGALRM, main thread); the callable runs in this process, so use it only on code you own or may test.
"""

from __future__ import annotations

import signal
from collections.abc import Callable, Sequence
from typing import Any

RETURNED, RAISED, TIMEOUT = "returned", "raised", "timeout"


class _Timeout(Exception):
    pass


def _alarm(_signum: int, _frame: Any) -> None:
    raise _Timeout()


def call_guarded(fn: Callable[..., Any], args: Sequence[Any] = (), timeout_s: float = 10.0) -> tuple[str, Any]:
    """Return ``("returned", value)``, ``("raised", exception)`` or ``("timeout", None)``."""
    old = signal.signal(signal.SIGALRM, _alarm)
    try:
        signal.setitimer(signal.ITIMER_REAL, timeout_s)
        try:
            return RETURNED, fn(*args)
        except _Timeout:
            return TIMEOUT, None
        except Exception as exc:                                       # noqa: BLE001 - every failure mode is a result
            return RAISED, exc
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def describe_error(kind: str, value: BaseException | None) -> str:
    return "timeout" if kind == TIMEOUT else f"{type(value).__name__}: {value}"
