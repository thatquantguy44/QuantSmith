"""Request builders and response parsers per ``api_style`` (spec ``0080`` REQ-019).

Pure and network-free: a builder turns a resolved profile and a prompt into an
:class:`HttpRequest`; a parser turns an :class:`HttpResponse` into a
:class:`Completion` or raises a typed error. Only ``transport.py`` sends.

Wire formats follow the providers' public APIs and their SDKs' base-URL
conventions, so a gateway that proxies either API works by base URL alone:

- ``anthropic_messages``: ``POST {base}/v1/messages`` with ``anthropic-version``;
  ``provider_default`` auth sends ``x-api-key``.
- ``openai_chat_completions``: ``POST {base}/chat/completions``; ``provider_default``
  and ``bearer`` auth send ``Authorization: Bearer``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from . import errors as E
from .profiles import ResolvedProfile

ANTHROPIC_VERSION = "2023-06-01"


@dataclass(frozen=True)
class HttpRequest:
    method: str
    url: str
    headers: tuple[tuple[str, str], ...] = field(repr=False)
    body: bytes = field(repr=False)

    @property
    def header_names(self) -> tuple[str, ...]:
        return tuple(k for k, _ in self.headers)

    def header(self, name: str) -> str | None:
        low = name.lower()
        return next((v for k, v in self.headers if k.lower() == low), None)


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes
    headers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None

    @property
    def total(self) -> int:
        return (self.input_tokens or 0) + (self.output_tokens or 0)


@dataclass(frozen=True)
class Completion:
    """The normalized result, shaped like the ``adapters/llm_runtime`` output contract."""

    profile: str
    api_style: str
    model: str | None
    status: str                      # completed | skipped
    output_text: str | None
    usage: Usage = field(default_factory=Usage)
    stop_reason: str | None = None
    latency_ms: int | None = None
    attempts: int = 0
    fallback_from: str | None = None

    def to_contract(self) -> dict[str, Any]:
        return {
            "adapter_name": "llm_runtime", "provider_style": self.api_style, "model_profile": self.profile,
            "model": self.model, "status": self.status, "output_text": self.output_text,
            "usage": {"input_tokens": self.usage.input_tokens, "output_tokens": self.usage.output_tokens,
                      "cost_estimate": None},
            "stop_reason": self.stop_reason, "latency_ms": self.latency_ms, "attempts": self.attempts,
            "fallback_from": self.fallback_from, "retryable": False, "error_code": None,
            "error_message_redacted": None,
        }


def _auth_headers(resolved: ResolvedProfile) -> tuple[tuple[str, str], ...]:
    auth = resolved.profile.auth
    if auth is None or auth.scheme == "none" or not resolved.credential:
        return ()
    if auth.scheme == "header":
        return ((auth.header_name or "", resolved.credential),)
    if auth.scheme == "provider_default" and resolved.api_style == "anthropic_messages":
        return (("x-api-key", resolved.credential),)
    return (("Authorization", f"Bearer {resolved.credential}"),)


def build_request(resolved: ResolvedProfile, prompt: str, *, system: str | None = None,
                  max_output_tokens: int | None = None) -> HttpRequest:
    """The exact HTTP request for one single-turn completion."""
    style = resolved.api_style
    if style == "none":
        raise ValueError("api_style 'none' makes no request")
    limits = resolved.profile.limits
    max_tokens = max_output_tokens or (limits.max_output_tokens if limits else 1024)
    headers = [("Content-Type", "application/json")]
    if style == "anthropic_messages":
        url = f"{resolved.base_url}/v1/messages"
        headers.append(("anthropic-version", ANTHROPIC_VERSION))
        payload: dict[str, Any] = {"model": resolved.model, "max_tokens": max_tokens,
                                   "messages": [{"role": "user", "content": prompt}]}
        if system:
            payload["system"] = system
    else:
        url = f"{resolved.base_url}/chat/completions"
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        payload = {"model": resolved.model, "max_tokens": max_tokens, "messages": messages}
    headers.extend(_auth_headers(resolved))
    headers.extend(resolved.extra_headers)
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return HttpRequest(method="POST", url=url, headers=tuple(headers), body=body)


def _decode(resolved: ResolvedProfile, response: HttpResponse) -> dict[str, Any]:
    try:
        data = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise E.LLMRuntimeError(E.OUTPUT_INVALID, "response body is not JSON", profile=resolved.name,
                                status=response.status) from None
    if not isinstance(data, dict):
        raise E.LLMRuntimeError(E.OUTPUT_INVALID, "response is not a JSON object", profile=resolved.name,
                                status=response.status)
    return data


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def parse_response(resolved: ResolvedProfile, response: HttpResponse) -> Completion:
    """Turn a 2xx response into a :class:`Completion`; non-2xx is the caller's (retry) concern."""
    data = _decode(resolved, response)
    style = resolved.api_style
    if style == "anthropic_messages":
        stop = data.get("stop_reason")
        if stop == "refusal":
            raise E.LLMRuntimeError(E.REFUSAL, "the model declined the request", profile=resolved.name,
                                    status=response.status)
        blocks = data.get("content")
        if not isinstance(blocks, list):
            raise E.LLMRuntimeError(E.OUTPUT_INVALID, "missing content blocks", profile=resolved.name)
        texts = [b.get("text") for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
        if not texts or not all(isinstance(t, str) for t in texts):
            raise E.LLMRuntimeError(E.OUTPUT_INVALID, "no text content in the response", profile=resolved.name)
        usage_raw = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        usage = Usage(_int(usage_raw.get("input_tokens")), _int(usage_raw.get("output_tokens")))
        text = "".join(texts)
    else:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise E.LLMRuntimeError(E.OUTPUT_INVALID, "missing choices", profile=resolved.name)
        message = choices[0].get("message")
        text = message.get("content") if isinstance(message, dict) else None
        stop = choices[0].get("finish_reason")
        if not isinstance(text, str):
            raise E.LLMRuntimeError(E.OUTPUT_INVALID, "no message content in the response", profile=resolved.name)
        usage_raw = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        usage = Usage(_int(usage_raw.get("prompt_tokens")), _int(usage_raw.get("completion_tokens")))
    model = data.get("model") if isinstance(data.get("model"), str) else resolved.model
    return Completion(profile=resolved.name, api_style=style, model=model, status="completed",
                      output_text=text, usage=usage, stop_reason=stop if isinstance(stop, str) else None)
