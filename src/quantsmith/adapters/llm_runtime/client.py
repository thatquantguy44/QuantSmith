"""``complete()``: one model call through a resolved profile (spec ``0080`` REQ-019, AC-028).

Retries 408, 409, 429, 5xx, and transport failures up to ``limits.max_retries``
(honoring ``retry-after`` up to a cap), then tries ``fallback_profile`` once,
on provider errors only — never on a refusal, a bad response shape, or a
resolution error. A :class:`TokenBudget` enforces ``limits.per_job_token_cap``
across the calls of one answer. ``api_style: none`` returns a ``skipped``
completion so the caller uses its deterministic path.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace

from . import errors as E
from .backends import Completion, HttpResponse, build_request, parse_response
from .profiles import ProfilesConfig, ResolvedProfile, resolve, resolve_named
from .transport import Transport, TransportFailure, urllib_transport

RETRYABLE_STATUS = frozenset({408, 409, 429})
MAX_RETRY_AFTER_S = 30.0


@dataclass
class TokenBudget:
    """Tokens spent across the calls of one answer, against the profile's ``per_job_token_cap``."""

    spent: int = 0

    def check(self, resolved: ResolvedProfile, max_output_tokens: int) -> None:
        limits = resolved.profile.limits
        if limits and self.spent + max_output_tokens > limits.per_job_token_cap:
            raise E.LLMRuntimeError(
                E.TOKEN_CAP_EXCEEDED,
                f"{self.spent} tokens spent; another call of up to {max_output_tokens} would pass "
                f"the cap of {limits.per_job_token_cap}", profile=resolved.name)

    def charge(self, completion: Completion) -> None:
        self.spent += completion.usage.total


def _retryable(status: int) -> bool:
    return status in RETRYABLE_STATUS or status >= 500


def _delay(response: HttpResponse | None, attempt: int) -> float:
    if response is not None:
        raw = next((v for k, v in response.headers.items() if k.lower() == "retry-after"), None)
        try:
            if raw is not None:
                return min(max(float(raw), 0.0), MAX_RETRY_AFTER_S)
        except ValueError:
            pass
    return min(0.5 * (2 ** attempt), MAX_RETRY_AFTER_S)


def _status_message(response: HttpResponse) -> str:
    # The provider's error *type* is safe to report; its free-text message is not echoed,
    # since a gateway may reflect request headers back in it.
    try:
        data = json.loads(response.body.decode("utf-8"))
        err = data.get("error") if isinstance(data, dict) else None
        kind = err.get("type") if isinstance(err, dict) else None
    except (UnicodeDecodeError, ValueError):
        kind = None
    return f"HTTP {response.status}" + (f" ({kind})" if isinstance(kind, str) else "")


def _call(resolved: ResolvedProfile, prompt: str, *, system: str | None, max_output_tokens: int,
          transport: Transport, sleep: Callable[[float], None], clock: Callable[[], float]) -> Completion:
    request = build_request(resolved, prompt, system=system, max_output_tokens=max_output_tokens)
    limits = resolved.profile.limits
    retries = limits.max_retries if limits else 0
    timeout_s = (limits.timeout_ms / 1000.0) if limits else 60.0
    started = clock()
    last: E.LLMRuntimeError | None = None
    for attempt in range(retries + 1):
        response: HttpResponse | None = None
        try:
            response = transport(request, timeout_s)
        except TransportFailure as exc:
            last = E.LLMRuntimeError(E.PROVIDER_ERROR, f"no response: {exc}", retryable=True, profile=resolved.name)
        else:
            if 200 <= response.status < 300:
                completion = parse_response(resolved, response)
                return replace(completion, latency_ms=int((clock() - started) * 1000), attempts=attempt + 1)
            last = E.LLMRuntimeError(E.PROVIDER_ERROR, _status_message(response),
                                     retryable=_retryable(response.status), profile=resolved.name,
                                     status=response.status)
            if not last.retryable:
                raise last
        if attempt < retries:
            sleep(_delay(response, attempt))
    assert last is not None
    raise last


def complete(prompt: str, *, config: ProfilesConfig, use: str, data_classes: Sequence[str] = (),
             system: str | None = None, requested: str | None = None,
             module_default: str | None = None, max_output_tokens: int | None = None,
             budget: TokenBudget | None = None, transport: Transport | None = None,
             env: Mapping[str, str] | None = None, sleep: Callable[[float], None] = time.sleep,
             clock: Callable[[], float] = time.monotonic) -> Completion:
    """Resolve a profile for ``use`` and run one single-turn completion through it."""
    resolved = resolve(config, use=use, data_classes=data_classes, requested=requested,
                       module_default=module_default, env=env)
    return _complete_resolved(resolved, prompt, config=config, use=use, data_classes=data_classes,
                              system=system, max_output_tokens=max_output_tokens, budget=budget,
                              transport=transport or urllib_transport, env=env, sleep=sleep, clock=clock)


def _complete_resolved(resolved: ResolvedProfile, prompt: str, *, config: ProfilesConfig, use: str,
                       data_classes: Sequence[str], system: str | None, max_output_tokens: int | None,
                       budget: TokenBudget | None, transport: Transport, env: Mapping[str, str] | None,
                       sleep: Callable[[float], None], clock: Callable[[], float],
                       fallback_from: str | None = None) -> Completion:
    if resolved.api_style == "none":
        return Completion(profile=resolved.name, api_style="none", model=None, status="skipped",
                          output_text=None, fallback_from=fallback_from)
    limits = resolved.profile.limits
    cap = max_output_tokens or (limits.max_output_tokens if limits else 1024)
    if limits:
        cap = min(cap, limits.max_output_tokens)
    if budget is not None:
        budget.check(resolved, cap)
    try:
        completion = _call(resolved, prompt, system=system, max_output_tokens=cap,
                           transport=transport, sleep=sleep, clock=clock)
    except E.LLMRuntimeError as exc:
        fallback = resolved.profile.fallback_profile
        if exc.code != E.PROVIDER_ERROR or not fallback or fallback_from is not None:
            raise
        backup = resolve_named(config, fallback, use=use, data_classes=data_classes, env=env)
        return _complete_resolved(backup, prompt, config=config, use=use, data_classes=data_classes,
                                  system=system, max_output_tokens=max_output_tokens, budget=budget,
                                  transport=transport, env=env, sleep=sleep, clock=clock,
                                  fallback_from=resolved.name)
    completion = replace(completion, fallback_from=fallback_from)
    if budget is not None:
        budget.charge(completion)
    return completion
