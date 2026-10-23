"""SFMeridian configuration: schema, layered resolution, validation, hash.

Spec ``0114`` REQ-001 (realizing ``0113`` REQ-003, REQ-004, REQ-020, REQ-026).

Resolution order: built-in defaults -> the file -> ``SFMERIDIAN__*``
environment overrides -> per-call overrides (allowlisted, tightening only).
Validation fails closed: unknown keys, wrong types, missing fields,
unresolved ``<placeholder>`` values, embedded credentials, writable database
profiles, unsupported dialects or retrieval modes, and write-back targets
classed as lending, trading, or books-and-records are all errors.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import yamlsubset

__all__ = [
    "CONFIG_ENV", "DIALECTS", "Config", "ConfigError", "Issue",
    "apply_call_overrides", "config_hash", "load_config", "resolve", "validate_data",
]

CONFIG_ENV = "SFMERIDIAN_CONFIG"
ENV_PREFIX = "SFMERIDIAN__"
SCHEMA_VERSION = 1

#: Owner decision 2026-10-22 (``0113``): SQLite for offline tests plus the first
#: adopter targets. SQL Server and Snowflake are planned, not yet supported.
DIALECTS = ("sqlite", "postgres", "oracle", "databricks")
PLANNED_DIALECTS = ("mssql", "snowflake")
REPO_KINDS = ("git", "local", "object_store")
FORBIDDEN_WRITEBACK_CLASSES = ("lending", "trading", "books_and_records")

_PLACEHOLDER_RE = re.compile(r"<[^<>\s][^<>]*>")
_URI_CREDENTIAL_RE = re.compile(r"://[^/\s:@]+:[^/\s@]+@")
_CREDENTIAL_TEXT_RE = re.compile(r"(?i)(password|passwd|pwd|token|api[_-]?key|secret)\s*=")
_CREDENTIAL_KEYS = ("password", "passwd", "token", "api_key", "apikey", "secret", "private_key")
_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_HANDLE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


@dataclass(frozen=True)
class Issue:
    code: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


class ConfigError(ValueError):
    def __init__(self, issues: Sequence[Issue]) -> None:
        self.issues = list(issues)
        super().__init__("; ".join(f"{i.code} at {i.path}: {i.message}" for i in self.issues))


# --------------------------------------------------------------------------
# Defaults and schema
# --------------------------------------------------------------------------

DEFAULTS: dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "enabled": True,
    "index": {"dir": ".sfmeridian/index"},
    "catalog": {},
    "semantic_mapping": {},
    "governed_tier": {
        "enabled": True,
        "interpreter": "keyword",
        "packs_root": None,
        "domain_tags": ["securities_lending"],
        "metric_sources": [],
        "writeback": {"enabled": False},
    },
    "grounding": {
        "mode": "full",
        "retrieval_min_score": 0.05,
        "max_compose_retries": 2,
        "require_citation_per_number": True,
        "numeric_tolerance": 1.0e-9,
        "require_pit_predicate_for_as_of": True,
        "abstain_message": "Not enough verified evidence to answer; missing: {missing}.",
    },
    "verification": {"token_ttl_s": 300},
    "access": {"clearance_source": None, "redaction_classes": {}, "column_classes": {}},
    "llm": {"runtime_profile": None, "temperature": 0.0, "max_output_tokens": 2000},
    "retrieval": {"mode": "lexical", "embedding_profile": None},
    "feedback": {"inbox": ".sfmeridian/inbox", "promoters": [], "auto_propose_accepted_answers": False},
    "eval": {"golden_sets": [], "thresholds": {}, "seeds": [1, 2, 3]},
    "per_call_overrides_allowlist": ["as_of", "row_limit", "database_profile", "token_ttl_s"],
    "datasets": [],
    "research": {"output_dir": ".sfmeridian/research"},
}

# Field spec: (type(s), required). ``"str"`` etc. are names, checked in ``_type_ok``.
_REPO_FIELDS = {
    "id": ("str", True), "kind": ("str", True), "uri": ("str", True), "ref": ("str", False),
    "paths": ("map", True), "dialect": ("str", True), "database_profile": ("str", False),
    "metadata_convention": ("str", False), "trust_tier": ("str", False),
    "review_policy": ("str", False), "refresh": ("str", False),
}
_REPO_DEFAULTS = {
    "metadata_convention": "front_matter", "trust_tier": "reviewed",
    "review_policy": "reviewed_only", "refresh": "on_demand", "database_profile": None, "ref": None,
}
_DB_FIELDS = {
    "id": ("str", True), "dialect": ("str", True), "connection": ("map", True),
    "read_only": ("bool", True), "schemas_allowlist": ("list", False), "tables_allowlist": ("list", False),
    "row_limit": ("int", False), "timeout_s": ("int", False), "explain_cost_limit": ("num?", False),
    "max_concurrency": ("int", False),
}
_DB_DEFAULTS = {"schemas_allowlist": [], "tables_allowlist": [], "row_limit": 10000,
                "timeout_s": 60, "explain_cost_limit": None, "max_concurrency": 2}
_SECTIONS = {
    "index": {"dir": "str"},
    "governed_tier": {"enabled": "bool", "interpreter": "str", "packs_root": "str?",
                      "domain_tags": "list", "metric_sources": "list", "writeback": "map"},
    "grounding": {"mode": "str", "retrieval_min_score": "num", "max_compose_retries": "int",
                  "require_citation_per_number": "bool", "numeric_tolerance": "num",
                  "require_pit_predicate_for_as_of": "bool", "abstain_message": "str"},
    "verification": {"token_ttl_s": "int"},
    "access": {"clearance_source": "str?", "redaction_classes": "map", "column_classes": "map"},
    "llm": {"runtime_profile": "str?", "temperature": "num", "max_output_tokens": "int"},
    "retrieval": {"mode": "str", "embedding_profile": "str?"},
    "feedback": {"inbox": "str", "promoters": "list", "auto_propose_accepted_answers": "bool"},
    "eval": {"golden_sets": "list", "thresholds": "map", "seeds": "list"},
    "research": {"output_dir": "str"},
}
_TOP_LEVEL = {"schema_version", "enabled", "query_repositories", "databases", "catalog", "datasets",
              "semantic_mapping", "per_call_overrides_allowlist", *_SECTIONS}
_ENUMS = {
    ("query_repositories", "kind"): REPO_KINDS,
    ("query_repositories", "metadata_convention"): ("front_matter", "sidecar"),
    ("query_repositories", "trust_tier"): ("reviewed", "team", "personal"),
    ("query_repositories", "review_policy"): ("reviewed_only", "allow_unreviewed_as_hints"),
    ("grounding", "mode"): ("full", "retrieval_only"),
    ("governed_tier", "interpreter"): ("keyword", "llm"),
    ("semantic_mapping", "kind"): ("measure", "ratio"),
    ("semantic_mapping", "quote"): ("fee", "rebate"),
}
_OVERRIDABLE = ("as_of", "row_limit", "database_profile", "token_ttl_s")


def _type_ok(value: Any, kind: str) -> bool:
    optional = kind.endswith("?")
    kind = kind.rstrip("?")
    if value is None:
        return optional
    if kind == "str":
        return isinstance(value, str)
    if kind == "bool":
        return isinstance(value, bool)
    if kind == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "num":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "list":
        return isinstance(value, list)
    if kind == "map":
        return isinstance(value, dict)
    if kind == "any":
        return True
    raise AssertionError(kind)  # pragma: no cover


# --------------------------------------------------------------------------
# Resolution
# --------------------------------------------------------------------------

def _deep_merge(base: dict[str, Any], over: Mapping[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _env_overrides(env: Mapping[str, str]) -> dict[str, Any]:
    """``SFMERIDIAN__GROUNDING__MODE=retrieval_only`` -> ``{"grounding": {"mode": ...}}``.

    Keys are lower-cased; values are read as one YAML-subset scalar or flow
    collection. Variables are applied in sorted order, so the result does not
    depend on the environment's iteration order.
    """
    out: dict[str, Any] = {}
    for name in sorted(env):
        if not name.startswith(ENV_PREFIX) or name == CONFIG_ENV:
            continue
        parts = [p.lower() for p in name[len(ENV_PREFIX):].split("__") if p]
        if not parts:
            continue
        raw = env[name]
        text = raw.strip()
        if text.startswith(("[", "{")):
            value = yamlsubset.parse(f"v: {text}", name)["v"]
        else:
            value = yamlsubset.parse_scalar(text, name)
        node = out
        for part in parts[:-1]:
            node = node.setdefault(part, {})
            if not isinstance(node, dict):
                break
        else:
            node[parts[-1]] = value
    return out


def resolve(file_data: Mapping[str, Any], env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Defaults -> file -> environment, with per-item defaults for lists."""
    data = _deep_merge(DEFAULTS, file_data)
    data = _deep_merge(data, _env_overrides(env or {}))
    repos = data.get("query_repositories")
    if isinstance(repos, list):
        data["query_repositories"] = [
            {**_REPO_DEFAULTS, **r} if isinstance(r, dict) else r for r in repos]
    dbs = data.get("databases")
    if isinstance(dbs, list):
        data["databases"] = [{**_DB_DEFAULTS, **d} if isinstance(d, dict) else d for d in dbs]
    return data


def config_hash(data: Mapping[str, Any]) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def _walk_strings(value: Any, path: str):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _walk_strings(v, f"{path}.{k}" if path else str(k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _walk_strings(v, f"{path}[{i}]")


def _walk_keys(value: Any, path: str):
    if isinstance(value, dict):
        for k, v in value.items():
            here = f"{path}.{k}" if path else str(k)
            yield here, str(k)
            yield from _walk_keys(v, here)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _walk_keys(v, f"{path}[{i}]")


def _check_fields(item: Any, fields: dict[str, Any], path: str, section: str,
                  issues: list[Issue]) -> None:
    if not isinstance(item, dict):
        issues.append(Issue("E_CONFIG_TYPE", path, "expected a mapping"))
        return
    for key in item:
        if key not in fields:
            issues.append(Issue("E_CONFIG_UNKNOWN_KEY", f"{path}.{key}", "unknown key"))
    for key, (kind, required) in fields.items():
        if key not in item or item[key] is None and not kind.endswith("?"):
            if required:
                issues.append(Issue("E_CONFIG_MISSING", f"{path}.{key}", "required field missing"))
            continue
        if not _type_ok(item[key], kind):
            issues.append(Issue("E_CONFIG_TYPE", f"{path}.{key}", f"expected {kind.rstrip('?')}"))
            continue
        allowed = _ENUMS.get((section, key))
        if allowed and item[key] not in allowed:
            issues.append(Issue("E_CONFIG_INVALID", f"{path}.{key}",
                                f"{item[key]!r} is not one of {', '.join(allowed)}"))


def _check_dialect(value: Any, path: str, issues: list[Issue]) -> None:
    if not isinstance(value, str) or _PLACEHOLDER_RE.search(value):
        return  # an unresolved placeholder is reported once, as E_CONFIG_PLACEHOLDER
    if value in PLANNED_DIALECTS:
        issues.append(Issue("E_CONFIG_UNSUPPORTED", path,
                            f"dialect {value!r} is planned but not yet supported "
                            f"(supported: {', '.join(DIALECTS)})"))
    elif value not in DIALECTS:
        issues.append(Issue("E_CONFIG_INVALID", path,
                            f"dialect {value!r} is not one of {', '.join(DIALECTS)}"))


def validate_data(data: Mapping[str, Any], *, allow_placeholders: bool = False) -> list[Issue]:
    """Every issue in resolved configuration ``data``; empty means valid."""
    issues: list[Issue] = []
    if not isinstance(data, dict):
        return [Issue("E_CONFIG_TYPE", "", "configuration must be a mapping")]

    for key in data:
        if key not in _TOP_LEVEL:
            issues.append(Issue("E_CONFIG_UNKNOWN_KEY", key, "unknown top-level key"))
    if data.get("schema_version") != SCHEMA_VERSION:
        issues.append(Issue("E_CONFIG_INVALID", "schema_version",
                            f"expected schema_version {SCHEMA_VERSION}"))
    if not isinstance(data.get("enabled", True), bool):
        issues.append(Issue("E_CONFIG_TYPE", "enabled", "expected bool"))

    for section, fields in _SECTIONS.items():
        value = data.get(section)
        if not isinstance(value, dict):
            issues.append(Issue("E_CONFIG_TYPE", section, "expected a mapping"))
            continue
        _check_fields(value, {k: (t, False) for k, t in fields.items()}, section, section, issues)

    # Databases (read-only profiles).
    dbs = data.get("databases")
    profile_ids: list[str] = []
    if not isinstance(dbs, list) or not dbs:
        issues.append(Issue("E_CONFIG_MISSING", "databases", "at least one database profile is required"))
        dbs = []
    for i, db in enumerate(dbs):
        path = f"databases[{i}]"
        _check_fields(db, _DB_FIELDS, path, "databases", issues)
        if not isinstance(db, dict):
            continue
        db_id = db.get("id")
        if isinstance(db_id, str):
            if not _ID_RE.match(db_id) and not _PLACEHOLDER_RE.search(db_id):
                issues.append(Issue("E_CONFIG_INVALID", f"{path}.id", "use lower_snake_case ids"))
            if db_id in profile_ids:
                issues.append(Issue("E_CONFIG_INVALID", f"{path}.id", f"duplicate profile id {db_id!r}"))
            profile_ids.append(db_id)
        _check_dialect(db.get("dialect"), f"{path}.dialect", issues)
        if db.get("read_only") is not True:
            issues.append(Issue("E_CONFIG_INVALID", f"{path}.read_only",
                                "database profiles must be read_only: true"))
        conn = db.get("connection")
        if isinstance(conn, dict):
            for key in conn:
                if key != "secret_ref":
                    issues.append(Issue("E_CONFIG_UNKNOWN_KEY", f"{path}.connection.{key}",
                                        "connection holds only secret_ref, a pointer to the secret store"))
            if not isinstance(conn.get("secret_ref"), str) or not conn.get("secret_ref"):
                issues.append(Issue("E_CONFIG_MISSING", f"{path}.connection.secret_ref",
                                    "secret_ref (a pointer, never a value) is required"))
        for key in ("row_limit", "timeout_s", "max_concurrency"):
            if isinstance(db.get(key), int) and db[key] <= 0:
                issues.append(Issue("E_CONFIG_INVALID", f"{path}.{key}", "must be positive"))
        cost_limit = db.get("explain_cost_limit")
        finite_cost = True
        if isinstance(cost_limit, (int, float)) and not isinstance(cost_limit, bool):
            try:
                finite_cost = math.isfinite(float(cost_limit))
            except OverflowError:
                finite_cost = False
        if (isinstance(cost_limit, (int, float)) and not isinstance(cost_limit, bool)
                and (not finite_cost or cost_limit <= 0)):
            issues.append(Issue(
                "E_CONFIG_INVALID", f"{path}.explain_cost_limit", "must be positive and finite"))

    verification = data.get("verification")
    if isinstance(verification, dict):
        token_ttl_s = verification.get("token_ttl_s")
        if (isinstance(token_ttl_s, int) and not isinstance(token_ttl_s, bool)
                and not 1 <= token_ttl_s <= 3600):
            issues.append(Issue(
                "E_CONFIG_INVALID", "verification.token_ttl_s", "must be between 1 and 3600 seconds"))

    # Query repositories.
    repos = data.get("query_repositories")
    repo_ids: list[str] = []
    if not isinstance(repos, list) or not repos:
        issues.append(Issue("E_CONFIG_MISSING", "query_repositories",
                            "at least one query repository is required"))
        repos = []
    for i, repo in enumerate(repos):
        path = f"query_repositories[{i}]"
        _check_fields(repo, _REPO_FIELDS, path, "query_repositories", issues)
        if not isinstance(repo, dict):
            continue
        repo_id = repo.get("id")
        if isinstance(repo_id, str):
            if not _ID_RE.match(repo_id) and not _PLACEHOLDER_RE.search(repo_id):
                issues.append(Issue("E_CONFIG_INVALID", f"{path}.id", "use lower_snake_case ids"))
            if repo_id in repo_ids or repo_id == "feedback":
                issues.append(Issue("E_CONFIG_INVALID", f"{path}.id",
                                    f"duplicate or reserved repository id {repo_id!r}"))
            repo_ids.append(repo_id)
        _check_dialect(repo.get("dialect"), f"{path}.dialect", issues)
        if repo.get("kind") == "git" and not repo.get("ref"):
            issues.append(Issue("E_CONFIG_MISSING", f"{path}.ref",
                                "git repositories need a ref (branch, tag, or commit) to pin"))
        paths = repo.get("paths")
        if isinstance(paths, dict):
            for key in paths:
                if key not in ("include", "exclude"):
                    issues.append(Issue("E_CONFIG_UNKNOWN_KEY", f"{path}.paths.{key}", "unknown key"))
            include = paths.get("include")
            if not isinstance(include, list) or not include or not all(isinstance(p, str) for p in include):
                issues.append(Issue("E_CONFIG_MISSING", f"{path}.paths.include",
                                    "a non-empty list of include globs is required"))
            exclude = paths.get("exclude", [])
            if not isinstance(exclude, list) or not all(isinstance(p, str) for p in exclude):
                issues.append(Issue("E_CONFIG_TYPE", f"{path}.paths.exclude", "expected a list of globs"))
        profile = repo.get("database_profile")
        if isinstance(profile, str) and profile not in profile_ids and not _PLACEHOLDER_RE.search(profile):
            issues.append(Issue("E_CONFIG_INVALID", f"{path}.database_profile",
                                f"unknown database profile {profile!r}"))

    # Per-profile sections must reference configured profiles.
    for section in ("catalog", "semantic_mapping"):
        value = data.get(section)
        if not isinstance(value, dict):
            issues.append(Issue("E_CONFIG_TYPE", section, "expected a mapping keyed by database profile"))
            continue
        for profile in value:
            if profile not in profile_ids and not _PLACEHOLDER_RE.search(profile):
                issues.append(Issue("E_CONFIG_INVALID", f"{section}.{profile}",
                                    f"unknown database profile {profile!r}"))
    _validate_catalog_entries(data.get("catalog"), issues)
    _validate_bindings(data.get("semantic_mapping"), issues)
    gov_tier = data.get("governed_tier")
    if isinstance(gov_tier, dict):
        _validate_metric_sources(gov_tier.get("metric_sources"), issues)

    _validate_datasets(data.get("datasets"), {d["id"]: d for d in dbs if isinstance(d, dict) and isinstance(d.get("id"), str)},
                       issues)

    # Retrieval: lexical only (owner decision 2026-10-22).
    retrieval = data.get("retrieval")
    if isinstance(retrieval, dict) and retrieval.get("mode") not in (None, "lexical"):
        code = "E_CONFIG_UNSUPPORTED" if retrieval.get("mode") == "lexical+embeddings" else "E_CONFIG_INVALID"
        issues.append(Issue(code, "retrieval.mode",
                            "only lexical retrieval is enabled in this release"))

    # Write-back: off by default; never a lending, trading, or books-and-records target.
    gov = data.get("governed_tier")
    writeback = gov.get("writeback") if isinstance(gov, dict) else None
    if isinstance(writeback, dict):
        for key in writeback:
            if key not in ("enabled", "target"):
                issues.append(Issue("E_CONFIG_UNKNOWN_KEY", f"governed_tier.writeback.{key}", "unknown key"))
        if not isinstance(writeback.get("enabled", False), bool):
            issues.append(Issue("E_CONFIG_TYPE", "governed_tier.writeback.enabled", "expected bool"))
        target = writeback.get("target")
        if target is not None:
            target_class = target.get("class") if isinstance(target, dict) else None
            if target_class in FORBIDDEN_WRITEBACK_CLASSES:
                issues.append(Issue("E_CONFIG_WRITEBACK_TARGET", "governed_tier.writeback.target.class",
                                    f"write-back may never target a {target_class} system"))
            elif not isinstance(target, dict) or not isinstance(target_class, str):
                issues.append(Issue("E_CONFIG_INVALID", "governed_tier.writeback.target",
                                    "target needs a name and a class"))
        if writeback.get("enabled") is True and target is None:
            issues.append(Issue("E_CONFIG_MISSING", "governed_tier.writeback.target",
                                "enabled write-back needs a declared target"))

    feedback = data.get("feedback")
    if isinstance(feedback, dict) and isinstance(feedback.get("promoters"), list):
        for i, handle in enumerate(feedback["promoters"]):
            if not isinstance(handle, str) or not (_HANDLE_RE.match(handle) or _PLACEHOLDER_RE.search(handle)):
                issues.append(Issue("E_CONFIG_INVALID", f"feedback.promoters[{i}]",
                                    "promoters are pseudonymous handles (lowercase, no email addresses)"))

    allow = data.get("per_call_overrides_allowlist")
    if not isinstance(allow, list) or not all(isinstance(a, str) for a in allow):
        issues.append(Issue("E_CONFIG_TYPE", "per_call_overrides_allowlist", "expected a list of field names"))
    else:
        for i, name in enumerate(allow):
            if name not in _OVERRIDABLE:
                issues.append(Issue("E_CONFIG_INVALID", f"per_call_overrides_allowlist[{i}]",
                                    f"{name!r} cannot be overridden per call "
                                    f"(overridable: {', '.join(_OVERRIDABLE)})"))

    # Credentials anywhere, and unresolved placeholders.
    for path, key in _walk_keys(data, ""):
        if key.lower() in _CREDENTIAL_KEYS:
            issues.append(Issue("E_CONFIG_CREDENTIAL", path,
                                "credentials never belong in configuration; use a secret_ref"))
    for path, value in _walk_strings(data, ""):
        if _URI_CREDENTIAL_RE.search(value) or _CREDENTIAL_TEXT_RE.search(value):
            issues.append(Issue("E_CONFIG_CREDENTIAL", path,
                                "value appears to embed a credential; use a secret_ref or credential helper"))
        if not allow_placeholders and _PLACEHOLDER_RE.search(value) and not path.endswith("abstain_message"):
            issues.append(Issue("E_CONFIG_PLACEHOLDER", path, f"unresolved placeholder in {value!r}"))
    if not allow_placeholders:
        for path, key in _walk_keys(data, ""):
            if _PLACEHOLDER_RE.search(key):
                issues.append(Issue("E_CONFIG_PLACEHOLDER", path, f"unresolved placeholder key {key!r}"))
    return sorted(set(issues), key=lambda i: (i.path, i.code, i.message))


_CATALOG_FIELDS = {"source": ("str", True), "file": ("str?", False), "refresh": ("str", False),
                   "drift_policy": ("str", False), "default_schema": ("str?", False)}
_BINDING_FIELDS = {
    "concept": ("str", True), "kind": ("str", False), "expression": ("str", False), "aggregation": ("str", False),
    "dimensions": ("any", False), "numerator": ("str", False), "denominator": ("str", False),
    "grain": ("str", False), "pit_column": ("str", False), "viewpoint": ("str", True), "unit": ("str", True),
    "source_unit": ("str", False), "conversion": ("str", False), "quote": ("str", False),
    "day_count": ("str", False), "owner": ("str", True), "evidence": ("map", False),
}
_SOURCE_FIELDS = {"metric": ("str", True), "exemplar_id": ("str", True), "period_column": ("str", True),
                  "dimension_columns": ("map", False), "measure_columns": ("map", True)}


def _validate_catalog_entries(cat: Any, issues: list[Issue]) -> None:
    """``catalog.<profile>`` (spec 0115 REQ-001): introspect, or a declared file; drift policy."""
    if not isinstance(cat, dict):
        return
    for profile, entry in cat.items():
        path = f"catalog.{profile}"
        _check_fields(entry, _CATALOG_FIELDS, path, "catalog", issues)
        if not isinstance(entry, dict):
            continue
        if entry.get("source") not in ("introspect", "file") and not _PLACEHOLDER_RE.search(str(entry.get("source"))):
            issues.append(Issue("E_CONFIG_INVALID", f"{path}.source", "source is introspect or file"))
        if entry.get("source") == "file" and not isinstance(entry.get("file"), str):
            issues.append(Issue("E_CONFIG_MISSING", f"{path}.file", "a file catalog needs a file path"))
        if entry.get("drift_policy", "exclude") not in ("exclude", "warn"):
            issues.append(Issue("E_CONFIG_INVALID", f"{path}.drift_policy", "drift_policy is exclude or warn"))


def _validate_bindings(mapping: Any, issues: list[Issue]) -> None:
    """``semantic_mapping.<profile>`` shape only; meaning is checked by ``mapping.validate`` (spec 0115)."""
    if not isinstance(mapping, dict):
        return
    for profile, bindings in mapping.items():
        if not isinstance(bindings, list):
            issues.append(Issue("E_CONFIG_TYPE", f"semantic_mapping.{profile}", "expected a list of bindings"))
            continue
        for i, b in enumerate(bindings):
            path = f"semantic_mapping.{profile}[{i}]"
            _check_fields(b, _BINDING_FIELDS, path, "semantic_mapping", issues)
            if isinstance(b, dict) and isinstance(b.get("evidence"), dict):
                for key in b["evidence"]:
                    if key not in ("exemplars", "owner_confirmation"):
                        issues.append(Issue("E_CONFIG_UNKNOWN_KEY", f"{path}.evidence.{key}", "unknown key"))


def _validate_metric_sources(sources: Any, issues: list[Issue]) -> None:
    if not isinstance(sources, list):
        return
    for i, src in enumerate(sources):
        _check_fields(src, _SOURCE_FIELDS, f"governed_tier.metric_sources[{i}]", "metric_sources", issues)


_DATASET_FIELDS = {
    "id": ("str", True), "source": ("str", True), "profile": ("str", False), "object": ("str", False),
    "object_type": ("str", False), "path": ("str", False), "columns": ("list", True), "order_by": ("list", False),
    "filters": ("list", False), "version": ("int", False), "dataset_kind": ("str", False),
    "contract": ("map", False), "max_rows": ("int", False),
}
_SIMPLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DATASET_KINDS = ("loan_book", "lendable_inventory", "borrow_rates", "collateral", "recalls", "program_revenue",
                  "generic")


def _validate_datasets(datasets: Any, profiles: Mapping[str, Any], issues: list[Issue]) -> None:
    """``datasets[]`` (spec 0121 REQ-003): every location, object, and column is declared, never free text."""
    if datasets is None:
        return
    if not isinstance(datasets, list):
        issues.append(Issue("E_CONFIG_TYPE", "datasets", "expected a list"))
        return
    def ph(v: Any) -> bool:
        return isinstance(v, str) and bool(_PLACEHOLDER_RE.search(v))   # reported once as E_CONFIG_PLACEHOLDER

    seen: list[str] = []
    for i, d in enumerate(datasets):
        path = f"datasets[{i}]"
        _check_fields(d, _DATASET_FIELDS, path, "datasets", issues)
        if not isinstance(d, dict):
            continue
        if d.get("id") in seen:
            issues.append(Issue("E_CONFIG_INVALID", f"{path}.id", f"duplicate dataset id {d.get('id')!r}"))
        seen.append(d.get("id"))
        cols = d.get("columns") if isinstance(d.get("columns"), list) else []
        if not cols or not all(isinstance(c, str) and (_SIMPLE_NAME.match(c) or ph(c)) for c in cols) \
                or len(cols) != len(set(cols)):
            issues.append(Issue("E_CONFIG_INVALID", f"{path}.columns",
                                "explicit, unique, simple column names are required"))
        source = d.get("source")
        if source == "database":
            prof = d.get("profile")
            if prof not in profiles and not ph(prof):
                issues.append(Issue("E_CONFIG_INVALID", f"{path}.profile", f"unknown database profile {prof!r}"))
            obj = d.get("object")
            parts = obj.split(".") if isinstance(obj, str) else []
            if not ph(obj) and (not 1 <= len(parts) <= 3 or not all(_SIMPLE_NAME.match(x) for x in parts)):
                issues.append(Issue("E_CONFIG_INVALID", f"{path}.object",
                                    "object must be a simple name with up to three dotted parts (no SQL)"))
            if not d.get("order_by"):
                issues.append(Issue("E_CONFIG_MISSING", f"{path}.order_by",
                                    "database datasets need an explicit ordering for extracts"))
            if d.get("version") is not None and profiles.get(prof, {}).get("dialect") != "databricks":
                issues.append(Issue("E_CONFIG_INVALID", f"{path}.version", "version pins are Databricks Delta only"))
        elif source == "file":
            if not isinstance(d.get("path"), str):
                issues.append(Issue("E_CONFIG_MISSING", f"{path}.path", "file datasets need a path"))
        else:
            issues.append(Issue("E_CONFIG_INVALID", f"{path}.source", "source must be database or file"))
        if d.get("object_type") not in (None, "table", "view"):
            issues.append(Issue("E_CONFIG_INVALID", f"{path}.object_type", "object_type is table or view"))
        if d.get("dataset_kind", "generic") not in _DATASET_KINDS:
            issues.append(Issue("E_CONFIG_INVALID", f"{path}.dataset_kind",
                                f"dataset_kind must be one of {', '.join(_DATASET_KINDS)}"))
        for key in ("order_by",):
            for c in d.get(key) or []:
                if c not in cols and not ph(c):
                    issues.append(Issue("E_CONFIG_INVALID", f"{path}.{key}", f"{c!r} is not a declared column"))
        for j, f in enumerate(d.get("filters") or []):
            ok = (isinstance(f, dict) and set(f) == {"column", "op", "value"}
                  and (f.get("column") in cols or ph(f.get("column")))
                  and f.get("op") in ("=", ">=", ">", "<=", "<", "<>")
                  and isinstance(f.get("value"), (str, int, float)) and not isinstance(f.get("value"), bool))
            if not ok:
                issues.append(Issue("E_CONFIG_INVALID", f"{path}.filters[{j}]",
                                    "filters are {column, op, value} on a declared column with a scalar value"))
        if isinstance(d.get("max_rows"), int) and not 1 <= d["max_rows"] <= 50000:
            issues.append(Issue("E_CONFIG_INVALID", f"{path}.max_rows", "max_rows must be 1..50000"))


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Config:
    data: dict[str, Any]
    hash: str
    source: str

    def repository(self, repo_id: str) -> dict[str, Any]:
        for repo in self.data["query_repositories"]:
            if repo["id"] == repo_id:
                return repo
        raise KeyError(repo_id)

    def profile(self, profile_id: str) -> dict[str, Any]:
        for db in self.data["databases"]:
            if db["id"] == profile_id:
                return db
        raise KeyError(profile_id)

    def resolve_path(self, value: str) -> Path:
        """A path from the config, relative to the config file's directory."""
        path = Path(value)
        if path.is_absolute() or self.source in ("<inline>", ""):
            return path
        return Path(self.source).parent / path


def read_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        data = json.loads(text)
    else:
        data = yamlsubset.parse(text, str(path))
    if not isinstance(data, dict):
        raise ConfigError([Issue("E_CONFIG_TYPE", "", f"{path} must contain a mapping")])
    return data


def load_config(path: str | os.PathLike | None = None, *, env: Mapping[str, str] | None = None,
                data: Mapping[str, Any] | None = None, allow_placeholders: bool = False) -> Config:
    """Load, resolve, and validate; raise :class:`ConfigError` listing every issue."""
    env = dict(os.environ if env is None else env)
    if data is not None:
        source, file_data = "<inline>", dict(data)
    else:
        chosen = path or env.get(CONFIG_ENV)
        if not chosen:
            raise ConfigError([Issue("E_CONFIG_MISSING", "", f"pass a config path or set {CONFIG_ENV}")])
        file_path = Path(chosen)
        try:
            file_data = read_file(file_path)
        except FileNotFoundError:
            raise ConfigError([Issue("E_CONFIG_MISSING", "", f"config file not found: {file_path}")]) from None
        except yamlsubset.YamlSubsetError as exc:
            raise ConfigError([Issue("E_CONFIG_INVALID", f"line {exc.line}", exc.message)]) from None
        source = str(file_path)
    try:
        resolved = resolve(file_data, env)
    except yamlsubset.YamlSubsetError as exc:
        raise ConfigError([Issue("E_CONFIG_INVALID", exc.source, exc.message)]) from None
    issues = validate_data(resolved, allow_placeholders=allow_placeholders)
    if issues:
        raise ConfigError(issues)
    return Config(data=resolved, hash=config_hash(resolved), source=source)


def apply_call_overrides(config: Config, overrides: Mapping[str, Any]) -> dict[str, Any]:
    """Validate per-call overrides; return the effective call settings.

    Only fields in ``per_call_overrides_allowlist`` may be set, and safety
    fields may only tighten: ``row_limit`` and ``token_ttl_s`` can be lowered,
    never raised, and ``database_profile`` must name a configured profile.
    """
    allow = set(config.data["per_call_overrides_allowlist"])
    issues: list[Issue] = []
    effective: dict[str, Any] = {}
    profiles = {db["id"]: db for db in config.data["databases"]}
    profile_id = overrides.get("database_profile", config.data["databases"][0]["id"])
    for key, value in overrides.items():
        if key not in allow:
            issues.append(Issue("E_CONFIG_OVERRIDE_DENIED", key, "not in per_call_overrides_allowlist"))
            continue
        if key == "database_profile" and value not in profiles:
            issues.append(Issue("E_CONFIG_OVERRIDE_DENIED", key, f"unknown database profile {value!r}"))
        elif key == "row_limit":
            ceiling = profiles.get(profile_id, {}).get("row_limit")
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                issues.append(Issue("E_CONFIG_OVERRIDE_DENIED", key, "row_limit must be a positive integer"))
            elif ceiling is not None and value > ceiling:
                issues.append(Issue("E_CONFIG_OVERRIDE_DENIED", key,
                                    f"row_limit may only be lowered (profile limit {ceiling})"))
        elif key == "token_ttl_s":
            ceiling = config.data["verification"]["token_ttl_s"]
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                issues.append(Issue("E_CONFIG_OVERRIDE_DENIED", key, "token_ttl_s must be a positive integer"))
            elif value > ceiling:
                issues.append(Issue("E_CONFIG_OVERRIDE_DENIED", key,
                                    f"token_ttl_s may only be lowered (configured TTL {ceiling})"))
        elif key == "as_of" and not (isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)):
            issues.append(Issue("E_CONFIG_OVERRIDE_DENIED", key, "as_of must be an ISO date YYYY-MM-DD"))
        effective[key] = value
    if issues:
        raise ConfigError(issues)
    return effective
