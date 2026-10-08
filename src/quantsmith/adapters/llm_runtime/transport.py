"""The one module in ``llm_runtime`` that opens a network connection (spec ``0080`` REQ-019).

``urllib_transport`` sends an :class:`~.backends.HttpRequest` with the standard
library and returns an :class:`~.backends.HttpResponse` for every HTTP status,
so retry policy stays in ``client.py``. A connection failure or timeout raises
:class:`TransportFailure`. Callers may pass their own transport instead (any
callable with the same signature), for example a company HTTP client.
Nothing here logs request headers or bodies.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Callable

from .backends import HttpRequest, HttpResponse


class TransportFailure(Exception):
    """No HTTP response was received (connection refused, DNS, TLS, or timeout)."""


Transport = Callable[[HttpRequest, float], HttpResponse]


def urllib_transport(request: HttpRequest, timeout_s: float) -> HttpResponse:
    req = urllib.request.Request(request.url, data=request.body, method=request.method)
    for name, value in request.headers:
        req.add_header(name, value)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return HttpResponse(status=resp.status, body=resp.read(), headers=dict(resp.headers.items()))
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp is not None else b""
        return HttpResponse(status=exc.code, body=body, headers=dict(exc.headers.items()) if exc.headers else {})
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise TransportFailure(f"{type(exc).__name__}: {reason}") from None
