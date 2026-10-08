"""Read and resolve LLM profiles in QuantMeridian's ``llm-profiles/1`` format (spec ``0080`` REQ-019).

One profiles file serves QuantSmith and QuantMeridian's spec009 agent worker,
so this module reads the format unchanged and validates it with the standard
library against the same rules as the vendored schema
(``adapters/llm_runtime/llm-profiles.schema.json``). Endpoints, models,
credentials, and header values never live in the file: it names environment
variables, and :func:`resolve` reads them at call time.

Resolution follows spec009's order and checks::

    candidate = requested ?? module_default ?? env[default_profile_env] ?? default_profile
    exists                                   else LLM_PROFILE_UNKNOWN
    enabled, use in uses, data classes in data_classes
                                             else LLM_PROFILE_NOT_ALLOWED
    credential / base URL / model / header variables set
                                             else LLM_PROFILE_UNAVAILABLE
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import errors as E

SCHEMA_VERSION = "llm-profiles/1"
API_STYLES = ("anthropic_messages", "openai_chat_completions", "none")
AUTH_SCHEMES = ("provider_default", "bearer", "header", "none")
DATA_CLASSES = ("public_market_data", "module_context", "desk_simulated")
USES = ("copilot", "interpreter", "narrator", "drafter")

# Provider defaults, matching the official SDKs' base URLs: the Anthropic SDK appends
# ``/v1/messages`` to a host-only base URL; the OpenAI SDK appends ``/chat/completions``
# to a base URL that already ends in ``/v1``.
DEFAULT_BASE_URLS = {
    "anthropic_messages": "https://api.anthropic.com",
    "openai_chat_completions": "https://api.openai.com/v1",
}

_PROFILE_NAME = re.compile(r"^[a-z][a-z0-9\-]*$")
_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@\-]*$")
_HEADER_NAME = re.compile(r"^[A-Za-z0-9\-]+$")
_PROFILE_KEYS = {"enabled", "label", "api_style", "model", "model_env", "base_url_env", "auth",
                 "header_envs", "limits", "data_classes", "uses", "fallback_profile"}
_LIMIT_RANGES = {"max_output_tokens": (1, 32000), "timeout_ms": (1000, 600000), "max_retries": (0, 5),
                 "per_job_token_cap": (1, None)}
# A literal that looks like a URL or a credential may not appear outside an ``*_env`` field.
_LOOKS_SECRET = re.compile(r"(?i)(://|\bsk[-_]|bearer\s|api[_-]?key|secret|password|token=)")


@dataclass(frozen=True)
class Auth:
    scheme: str
    credential_env: str | None = None
    header_name: str | None = None


@dataclass(frozen=True)
class Limits:
    max_output_tokens: int
    timeout_ms: int
    max_retries: int
    per_job_token_cap: int
    daily_token_budget: int | None


@dataclass(frozen=True)
class Profile:
    name: str
    enabled: bool
    label: str
    api_style: str
    data_classes: tuple[str, ...]
    uses: tuple[str, ...]
    model: str | None = None
    model_env: str | None = None
    base_url_env: str | None = None
    auth: Auth | None = None
    header_envs: tuple[tuple[str, str], ...] = ()
    limits: Limits | None = None
    fallback_profile: str | None = None


@dataclass(frozen=True)
class ProfilesConfig:
    default_profile: str
    profiles: Mapping[str, Profile]
    default_profile_env: str | None = None
    source: str = "<memory>"


@dataclass(frozen=True)
class ResolvedProfile:
    """A profile with its environment references read. ``repr`` never shows secret values."""

    profile: Profile
    model: str | None
    base_url: str | None
    credential: str | None = field(default=None, repr=False)
    extra_headers: tuple[tuple[str, str], ...] = field(default=(), repr=False)

    @property
    def name(self) -> str:
        return self.profile.name

    @property
    def api_style(self) -> str:
        return self.profile.api_style

    def __repr__(self) -> str:  # explicit, so no field can leak through a dataclass default
        headers = [k for k, _ in self.extra_headers]
        return (f"ResolvedProfile(name={self.name!r}, api_style={self.api_style!r}, model={self.model!r}, "
                f"base_url={self.base_url!r}, credential={'<set>' if self.credential else None}, "
                f"extra_headers={headers!r})")


# --- loading and validation -----------------------------------------------------------------------

def _fail(where: str, message: str) -> E.LLMRuntimeError:
    return E.LLMRuntimeError(E.PROFILE_CONFIG_INVALID, f"{where}: {message}")


def _check_env(where: str, value: Any) -> str:
    if not isinstance(value, str) or len(value) > 64 or not _ENV_NAME.match(value):
        raise _fail(where, "must be an environment variable name (A-Z, 0-9, _; at most 64 characters)")
    return value


def _check_literal(where: str, value: str) -> None:
    if _LOOKS_SECRET.search(value):
        raise _fail(where, "looks like a URL or credential; put it in an environment variable and name it in an *_env field")


def _unique_enum(where: str, value: Any, allowed: Sequence[str], *, min_items: int) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) < min_items:
        raise _fail(where, f"must be a list with at least {min_items} item(s)")
    if len(set(value)) != len(value):
        raise _fail(where, "items must be unique")
    bad = [v for v in value if v not in allowed]
    if bad:
        raise _fail(where, f"unknown value(s) {bad}; allowed {list(allowed)}")
    return tuple(value)


def _parse_auth(where: str, raw: Any) -> Auth:
    if not isinstance(raw, dict):
        raise _fail(where, "must be an object")
    extra = set(raw) - {"scheme", "credential_env", "header_name"}
    if extra:
        raise _fail(where, f"unknown field(s) {sorted(extra)}")
    scheme = raw.get("scheme")
    if scheme not in AUTH_SCHEMES:
        raise _fail(f"{where}.scheme", f"must be one of {list(AUTH_SCHEMES)}")
    cred = _check_env(f"{where}.credential_env", raw["credential_env"]) if "credential_env" in raw else None
    header = raw.get("header_name")
    if header is not None and (not isinstance(header, str) or len(header) > 64 or not _HEADER_NAME.match(header)):
        raise _fail(f"{where}.header_name", "must be a header name")
    if scheme in ("provider_default", "bearer") and not cred:
        raise _fail(where, f"scheme {scheme!r} requires credential_env")
    if scheme == "header" and not (cred and header):
        raise _fail(where, "scheme 'header' requires header_name and credential_env")
    return Auth(scheme=scheme, credential_env=cred, header_name=header)


def _parse_limits(where: str, raw: Any) -> Limits:
    if not isinstance(raw, dict):
        raise _fail(where, "must be an object")
    keys = set(_LIMIT_RANGES) | {"daily_token_budget"}
    if set(raw) - keys:
        raise _fail(where, f"unknown field(s) {sorted(set(raw) - keys)}")
    if keys - set(raw):
        raise _fail(where, f"missing field(s) {sorted(keys - set(raw))}")
    values: dict[str, Any] = {}
    for key, (low, high) in _LIMIT_RANGES.items():
        v = raw[key]
        if not isinstance(v, int) or isinstance(v, bool) or v < low or (high is not None and v > high):
            raise _fail(f"{where}.{key}", f"must be an integer in [{low}, {high if high is not None else '∞'}]")
        values[key] = v
    budget = raw["daily_token_budget"]
    if budget is not None and (not isinstance(budget, int) or isinstance(budget, bool) or budget < 1):
        raise _fail(f"{where}.daily_token_budget", "must be a positive integer or null")
    return Limits(daily_token_budget=budget, **values)


def _parse_profile(name: str, raw: Any) -> Profile:
    where = f"profiles.{name}"
    if not _PROFILE_NAME.match(name):
        raise _fail(where, "profile names are lowercase letters, digits, and hyphens, starting with a letter")
    if not isinstance(raw, dict):
        raise _fail(where, "must be an object")
    unknown = set(raw) - _PROFILE_KEYS
    if unknown:
        raise _fail(where, f"unknown field(s) {sorted(unknown)} (llm-profiles/1 allows no others)")
    missing = {"enabled", "label", "api_style", "data_classes", "uses"} - set(raw)
    if missing:
        raise _fail(where, f"missing field(s) {sorted(missing)}")
    if not isinstance(raw["enabled"], bool):
        raise _fail(f"{where}.enabled", "must be true or false")
    label = raw["label"]
    if not isinstance(label, str) or not 1 <= len(label) <= 80:
        raise _fail(f"{where}.label", "must be 1-80 characters")
    _check_literal(f"{where}.label", label)
    style = raw["api_style"]
    if style not in API_STYLES:
        raise _fail(f"{where}.api_style", f"must be one of {list(API_STYLES)}")
    model = raw.get("model")
    if model is not None:
        if not isinstance(model, str) or not 1 <= len(model) <= 128 or not _MODEL.match(model):
            raise _fail(f"{where}.model", "must be a model identifier")
        _check_literal(f"{where}.model", model)
    model_env = _check_env(f"{where}.model_env", raw["model_env"]) if "model_env" in raw else None
    base_url_env = _check_env(f"{where}.base_url_env", raw["base_url_env"]) if "base_url_env" in raw else None
    if style == "none":
        present = [k for k in ("model", "model_env", "base_url_env", "auth", "limits") if k in raw]
        if present:
            raise _fail(where, f"api_style 'none' must not set {present}")
        auth, limits = None, None
    else:
        if "auth" not in raw or "limits" not in raw:
            raise _fail(where, f"api_style {style!r} requires auth and limits")
        auth = _parse_auth(f"{where}.auth", raw["auth"])
        limits = _parse_limits(f"{where}.limits", raw["limits"])
        if raw["enabled"] and not (model or model_env):
            raise _fail(where, "an enabled profile needs model or model_env")
    headers_raw = raw.get("header_envs", {})
    if not isinstance(headers_raw, dict):
        raise _fail(f"{where}.header_envs", "must be an object")
    headers = []
    for header, env in sorted(headers_raw.items()):
        if not _HEADER_NAME.match(header):
            raise _fail(f"{where}.header_envs", f"{header!r} is not a header name")
        headers.append((header, _check_env(f"{where}.header_envs.{header}", env)))
    fallback = raw.get("fallback_profile")
    if fallback is not None and (not isinstance(fallback, str) or not _PROFILE_NAME.match(fallback)):
        raise _fail(f"{where}.fallback_profile", "must be a profile name or null")
    return Profile(
        name=name, enabled=raw["enabled"], label=label, api_style=style,
        data_classes=_unique_enum(f"{where}.data_classes", raw["data_classes"], DATA_CLASSES, min_items=1),
        uses=_unique_enum(f"{where}.uses", raw["uses"], USES, min_items=0),
        model=model, model_env=model_env, base_url_env=base_url_env, auth=auth,
        header_envs=tuple(headers), limits=limits, fallback_profile=fallback,
    )


def parse_profiles(data: Any, *, source: str = "<memory>") -> ProfilesConfig:
    """Validate an ``llm-profiles/1`` document (already decoded from JSON)."""
    if not isinstance(data, dict):
        raise _fail(source, "must be a JSON object")
    unknown = set(data) - {"schema_version", "default_profile", "default_profile_env", "profiles"}
    if unknown:
        raise _fail(source, f"unknown top-level field(s) {sorted(unknown)}")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise _fail(f"{source}.schema_version", f"must be {SCHEMA_VERSION!r}")
    default = data.get("default_profile")
    if not isinstance(default, str) or not _PROFILE_NAME.match(default):
        raise _fail(f"{source}.default_profile", "must be a profile name")
    default_env = _check_env(f"{source}.default_profile_env", data["default_profile_env"]) \
        if "default_profile_env" in data else None
    raw_profiles = data.get("profiles")
    if not isinstance(raw_profiles, dict) or not raw_profiles:
        raise _fail(f"{source}.profiles", "must be an object with at least one profile")
    profiles = {name: _parse_profile(name, raw) for name, raw in raw_profiles.items()}
    if default not in profiles:
        raise _fail(f"{source}.default_profile", f"{default!r} is not a defined profile")
    for p in profiles.values():
        if p.fallback_profile is not None and (p.fallback_profile not in profiles or p.fallback_profile == p.name):
            raise _fail(f"profiles.{p.name}.fallback_profile", f"{p.fallback_profile!r} must name another defined profile")
    return ProfilesConfig(default_profile=default, profiles=profiles, default_profile_env=default_env, source=source)


def load_profiles(path: str | Path) -> ProfilesConfig:
    """Read and validate an ``llm-profiles/1`` file."""
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise E.LLMRuntimeError(E.PROFILE_CONFIG_INVALID, f"profiles file not found: {p}") from None
    except json.JSONDecodeError as exc:
        raise E.LLMRuntimeError(E.PROFILE_CONFIG_INVALID, f"{p}: not valid JSON ({exc.msg}, line {exc.lineno})") from None
    return parse_profiles(data, source=str(p))


# --- resolution ---------------------------------------------------------------------------------------

def _env(env: Mapping[str, str], name: str | None) -> str | None:
    if not name:
        return None
    value = env.get(name)
    return value if value else None


def candidate_name(config: ProfilesConfig, *, requested: str | None = None,
                   module_default: str | None = None, env: Mapping[str, str] | None = None) -> str:
    """spec009's precedence: requested, then the module's default, then the env override, then the file's default."""
    env = os.environ if env is None else env
    return requested or module_default or _env(env, config.default_profile_env) or config.default_profile


def resolve(config: ProfilesConfig, *, use: str, data_classes: Sequence[str] = (),
            requested: str | None = None, module_default: str | None = None,
            env: Mapping[str, str] | None = None) -> ResolvedProfile:
    """Pick and check a profile for one call; raise a typed error naming what is wrong."""
    env = os.environ if env is None else env
    name = candidate_name(config, requested=requested, module_default=module_default, env=env)
    return resolve_named(config, name, use=use, data_classes=data_classes, env=env)


def resolve_named(config: ProfilesConfig, name: str, *, use: str, data_classes: Sequence[str] = (),
                  env: Mapping[str, str] | None = None) -> ResolvedProfile:
    env = os.environ if env is None else env
    if use not in USES:
        raise ValueError(f"unknown use {use!r}; one of {list(USES)}")
    profile = config.profiles.get(name)
    if profile is None:
        raise E.LLMRuntimeError(E.PROFILE_UNKNOWN, f"no profile named {name!r} in {config.source}", profile=name)
    if not profile.enabled:
        raise E.LLMRuntimeError(E.PROFILE_NOT_ALLOWED, f"profile {name!r} is disabled", profile=name)
    if use not in profile.uses:
        raise E.LLMRuntimeError(E.PROFILE_NOT_ALLOWED, f"profile {name!r} does not allow use {use!r}", profile=name)
    outside = sorted(set(data_classes) - set(profile.data_classes))
    if outside:
        raise E.LLMRuntimeError(E.PROFILE_NOT_ALLOWED,
                                f"profile {name!r} does not allow data class(es) {outside}", profile=name)
    if profile.api_style == "none":
        return ResolvedProfile(profile=profile, model=None, base_url=None)
    missing: list[str] = []
    model = _env(env, profile.model_env) or profile.model   # model_env wins when set
    if profile.model_env and not _env(env, profile.model_env) and not profile.model:
        missing.append(profile.model_env)
    base_url = DEFAULT_BASE_URLS[profile.api_style]
    if profile.base_url_env:
        base_url = _env(env, profile.base_url_env)
        if base_url is None:
            missing.append(profile.base_url_env)
    credential = None
    if profile.auth and profile.auth.scheme != "none":
        credential = _env(env, profile.auth.credential_env)
        if credential is None:
            missing.append(profile.auth.credential_env or "")
    headers = []
    for header, var in profile.header_envs:
        value = _env(env, var)
        if value is None:
            missing.append(var)
        else:
            headers.append((header, value))
    if missing:
        raise E.LLMRuntimeError(E.PROFILE_UNAVAILABLE,
                                f"profile {name!r} needs environment variable(s) {sorted(set(missing))} set",
                                profile=name)
    return ResolvedProfile(profile=profile, model=model, base_url=base_url.rstrip("/") if base_url else None,
                           credential=credential, extra_headers=tuple(headers))
