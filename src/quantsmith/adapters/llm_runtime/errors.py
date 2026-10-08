"""Typed errors for the LLM runtime adapter (spec ``0080`` REQ-019).

The codes match QuantMeridian spec009's profile layer so both repositories
report the same failure the same way. No message ever carries a credential,
an authorization header, or a header value: messages name environment
*variables*, never their contents.
"""

from __future__ import annotations

# Configuration file does not satisfy llm-profiles/1.
PROFILE_CONFIG_INVALID = "LLM_PROFILE_CONFIG_INVALID"
# Named profile does not exist.
PROFILE_UNKNOWN = "LLM_PROFILE_UNKNOWN"
# Profile exists but is disabled, not allowed for this use, or not allowed for the call's data classes.
PROFILE_NOT_ALLOWED = "LLM_PROFILE_NOT_ALLOWED"
# A referenced environment variable (credential, base URL, model, header) is unset.
PROFILE_UNAVAILABLE = "LLM_PROFILE_UNAVAILABLE"
# Provider or transport failure (after retries).
PROVIDER_ERROR = "LLM_PROVIDER_ERROR"
# Provider answered, but not in the expected shape.
OUTPUT_INVALID = "LLM_OUTPUT_INVALID"
# The model declined the request (Anthropic ``stop_reason: refusal``).
REFUSAL = "LLM_REFUSAL"
# The per-answer token cap (``limits.per_job_token_cap``) would be exceeded.
TOKEN_CAP_EXCEEDED = "LLM_TOKEN_CAP_EXCEEDED"


class LLMRuntimeError(Exception):
    """A typed, readable failure. ``code`` is one of the module constants."""

    def __init__(self, code: str, message: str, *, retryable: bool = False,
                 profile: str | None = None, status: int | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.retryable = retryable
        self.profile = profile
        self.status = status
