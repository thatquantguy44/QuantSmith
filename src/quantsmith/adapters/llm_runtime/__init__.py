"""Provider-neutral LLM calls configured by QuantMeridian's ``llm-profiles/1`` format (spec ``0080`` REQ-019).

``load_profiles`` reads and validates a profiles file; ``resolve`` picks and
checks a profile for one call; ``complete`` runs a single-turn completion with
retries, the per-answer token cap, and a one-hop fallback. Standard library
only; ``transport.py`` is the one module that opens a connection, and callers
may inject their own transport. ``quantsmith.nl_analytics`` never imports this
package: it receives a plain completion callable (spec ``0080`` AC-019).
"""

from .backends import (
    Completion,
    HttpRequest,
    HttpResponse,
    Usage,
    build_request,
    parse_response,
)
from .client import TokenBudget, complete
from .errors import LLMRuntimeError
from .profiles import (
    API_STYLES,
    SCHEMA_VERSION,
    Profile,
    ProfilesConfig,
    ResolvedProfile,
    load_profiles,
    parse_profiles,
    resolve,
    resolve_named,
)
from .transport import TransportFailure, urllib_transport

__all__ = [
    "API_STYLES", "SCHEMA_VERSION", "Completion", "HttpRequest", "HttpResponse", "LLMRuntimeError",
    "Profile", "ProfilesConfig", "ResolvedProfile", "TokenBudget", "TransportFailure", "Usage",
    "build_request", "complete", "load_profiles", "parse_profiles", "parse_response", "resolve",
    "resolve_named", "urllib_transport",
]
