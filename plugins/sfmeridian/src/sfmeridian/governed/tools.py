"""Shared registry tools for spec 0116's governed SQL runtime.

This module intentionally imports no QuantSmith module at import time.  The
``ask`` handler loads the governed bridge lazily, so the core registry remains
usable when the optional SDK is absent.  Composition and verified queries are
kept in :class:`~sfmeridian.tools.ToolContext` session memory; ``sql.execute``
accepts a token and exact parameters, never SQL.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from .. import access as access_mod
from .. import catalog as catalog_mod
from ..compose import CompositionError, CompositionRequest, compose
from ..execute import ExecutionError, QueryOnlyAdapter, adapt_query_source, execute
from ..index import load_index
from ..mapping import Vocabulary, validate_mapping
from ..tools import ToolContext, ToolError, ToolRegistry, ToolSpec, _index_dir, _obj
from ..verify import verify

__all__ = ["register"]

_PARAMS = {"type": "object"}
_PROFILE = {"type": "string", "maxLength": 200}
_CALLER = {"type": "string", "maxLength": 200}
_AS_OF = {"type": "string", "maxLength": 10}


def _snapshot(ctx: ToolContext, profile: str) -> dict[str, Any]:
    snapshot = catalog_mod.load_snapshot(_index_dir(ctx), profile)
    if snapshot is None:
        raise ToolError("E_NOT_FOUND", f"profile {profile!r} has no catalog snapshot")
    return snapshot


def _graph(ctx: ToolContext) -> list[dict[str, Any]]:
    path = _index_dir(ctx) / "join_graph.json"
    if not path.exists():
        raise ToolError("E_NOT_FOUND", "join graph is not indexed")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ToolError("E_NOT_FOUND", "join graph is invalid")
    return value


def _security(ctx: ToolContext) -> tuple[str, bytes, Mapping[str, bytes], int, Any]:
    value = ctx.clients.get("verification")
    if not isinstance(value, Mapping):
        raise ToolError("E_TOOL_INPUT", "verification client configuration is required")
    key_id, signing_key = value.get("key_id"), value.get("signing_key")
    keys, now = value.get("keys"), value.get("now")
    if (not isinstance(key_id, str) or not isinstance(signing_key, bytes)
            or not isinstance(keys, Mapping) or not all(isinstance(k, str) and isinstance(v, bytes)
                                                        for k, v in keys.items())):
        raise ToolError("E_TOOL_INPUT", "verification keys are invalid")
    current = now() if callable(now) else now
    if not isinstance(current, int) or isinstance(current, bool):
        raise ToolError("E_TOOL_INPUT", "verification clock is invalid")
    return key_id, signing_key, keys, current, value.get("explainer")


def _source(ctx: ToolContext, profile: str) -> QueryOnlyAdapter:
    sources = ctx.clients.get("query_sources")
    raw = sources.get(profile) if isinstance(sources, Mapping) else None
    if raw is None:
        raise ToolError("E_TOOL_INPUT", f"query source for profile {profile!r} is required")
    profile_config = ctx.config.profile(profile)
    if isinstance(raw, QueryOnlyAdapter):
        return raw
    try:
        return adapt_query_source(raw, profile=profile, dialect=str(profile_config["dialect"]))
    except ExecutionError as exc:
        raise ToolError(exc.code, exc.message) from None


def _mapping(ctx: ToolContext) -> dict[str, Any]:
    return validate_mapping(ctx.config, _index_dir(ctx), Vocabulary.load(ctx.config))


def _compositions(ctx: ToolContext) -> dict[str, Any]:
    return ctx.session.setdefault("sql.compositions", {})


def _verified(ctx: ToolContext) -> dict[str, Any]:
    return ctx.session.setdefault("sql.verified", {})


def _compose(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    profile = ctx.config.profile(args["profile"])
    request = CompositionRequest(
        question=args["question"],
        profile=args["profile"],
        params=args.get("params", {}),
        as_of=args.get("as_of"),
        route_outcome=args["route_outcome"],
        pit_columns=tuple(args.get("pit_columns", ())),
        tags=tuple(args.get("tags", ())),
    )
    try:
        record = compose(
            request,
            index=load_index(_index_dir(ctx)),
            profile=profile,
            snapshot=_snapshot(ctx, args["profile"]),
            completer=ctx.clients.get("sql_completer"),
            min_score=ctx.config.data["grounding"]["retrieval_min_score"],
        )
    except CompositionError as exc:
        raise ToolError(exc.code, exc.message) from None
    _compositions(ctx)[record.content_hash] = record
    return {"composition_id": record.content_hash, **record.as_dict()}


def _verify(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    record = _compositions(ctx).get(args["composition_id"])
    if record is None:
        raise ToolError("E_NOT_FOUND", "composition is not present in this run")
    key_id, signing_key, keys, now, explainer = _security(ctx)
    who = access_mod.caller(ctx.config, args.get("caller", ctx.actor))
    snapshot = _snapshot(ctx, record.profile)
    outcome = verify(
        record.verification_request(clearance=who.clearance),
        profile=ctx.config.profile(record.profile),
        snapshot=snapshot,
        join_graph=_graph(ctx),
        config_hash=ctx.config.hash,
        key_id=key_id,
        signing_key=signing_key,
        now=now,
        ttl_s=int(ctx.config.data["verification"]["token_ttl_s"]),
        explainer=explainer,
    )
    if outcome.verified is not None:
        verification_id = f"sha256:{hashlib.sha256(outcome.verified.token.encode()).hexdigest()}"
        _verified(ctx)[outcome.verified.token] = {
            "query": outcome.verified,
            "composition": record,
            "keys": keys,
        }
        return {"verification_id": verification_id, **outcome.as_dict()}
    return outcome.as_dict()


def _execute(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    state = _verified(ctx).get(args["token"])
    if state is None:
        raise ToolError("E_EXEC_TOKEN", "token has no verified query in this run")
    query, record = state["query"], state["composition"]
    _key_id, _signing_key, current_keys, now, _explainer = _security(ctx)
    # Current host keys, not a historical copy, decide whether the token is
    # still executable after a rotation.
    who = access_mod.caller(ctx.config, args.get("caller", ctx.actor))
    try:
        result = execute(
            query,
            token=args["token"],
            params=args["params"],
            keys=current_keys,
            now=now,
            config=ctx.config,
            snapshot_id=str(_snapshot(ctx, query.record.profile)["snapshot_id"]),
            caller=who,
            source=_source(ctx, query.record.profile),
            source_exemplars=tuple(item["id"] for item in record.source_exemplars),
        )
    except ExecutionError as exc:
        raise ToolError(exc.code, exc.message) from None
    return result.as_dict()


def _ask(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    if args.get("action", "read") != "read":
        raise ToolError(
            "E_WRITEBACK_DISABLED",
            "write-back is disabled in spec 0116; publish, persist, submit, and reverse requests are refused",
        )
    # Lazy import preserves the optional-SDK boundary for registry discovery.
    from .ask import AskRequest, ask

    key_id, signing_key, keys, now, _explainer = _security(ctx)
    profile = args["profile"]
    try:
        request = AskRequest(
            question=args["question"], as_of=args["as_of"],
            caller=args.get("caller", ctx.actor), profile=profile,
            params=args.get("params", {}), pit_columns=tuple(args.get("pit_columns", ())),
            default_window_periods=args.get("default_window_periods", 1),
            max_repairs=args.get("max_repairs", 1),
        )
    except ValueError as exc:
        raise ToolError("E_TOOL_INPUT", str(exc)) from None
    outcome = ask(
        request, config=ctx.config, index=load_index(_index_dir(ctx)),
        mapping_report=_mapping(ctx), snapshot=_snapshot(ctx, profile), join_graph=_graph(ctx),
        source=_source(ctx, profile), key_id=key_id, signing_key=signing_key,
        keys=keys, now=now, completer=ctx.clients.get("sql_completer"),
    )
    return outcome.as_dict()


def register(reg: ToolRegistry) -> None:
    reg.register(ToolSpec(
        "sql.compose",
        "Compose a catalog-bound query after a recorded no-governed-match route.",
        _obj({
            "question": {"type": "string", "maxLength": 2000},
            "profile": _PROFILE,
            "params": _PARAMS,
            "as_of": _AS_OF,
            "route_outcome": {"type": "string", "enum": ["no_governed_match"]},
            "pit_columns": {"type": "array", "items": {"type": "string", "maxLength": 300}},
            "tags": {"type": "array", "items": {"type": "string", "maxLength": 100}},
        }, ("question", "profile", "route_outcome")),
        "read",
        _compose,
    ))
    reg.register(ToolSpec(
        "sql.verify",
        "Verify a run-scoped composition and issue an exact-context token.",
        _obj({"composition_id": {"type": "string", "maxLength": 80}, "caller": _CALLER},
             ("composition_id",)),
        "read",
        _verify,
    ))
    reg.register(ToolSpec(
        "sql.execute",
        "Execute a run-scoped verified token with exact parameters; raw SQL is not accepted.",
        _obj({
            "token": {"type": "string", "maxLength": 10000},
            "params": _PARAMS,
            "caller": _CALLER,
        }, ("token", "params")),
        "execute_read",
        _execute,
    ))
    reg.register(ToolSpec(
        "ask",
        "Route through governed analytics first, then the verified shadow-mode SQL tail.",
        _obj({
            "question": {"type": "string", "maxLength": 2000},
            "as_of": _AS_OF,
            "caller": _CALLER,
            "profile": _PROFILE,
            "params": _PARAMS,
            "pit_columns": {"type": "array", "items": {"type": "string", "maxLength": 300}},
            "default_window_periods": {"type": "integer", "minimum": 1},
            "max_repairs": {"type": "integer", "minimum": 0},
            "action": {"type": "string", "enum": ["read", "publish", "persist", "submit", "reverse"]},
        }, ("question", "as_of", "profile")),
        "execute_read",
        _ask,
    ))
