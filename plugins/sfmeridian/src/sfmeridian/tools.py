"""The SFMeridian tool registry: one contract for apps and agents.

Spec ``0114`` REQ-012 (realizing ``0113`` REQ-001 and REQ-029). Every
capability is a named tool with a JSON-Schema input, a declared effect, and a
handler. Apps call tools through the Python API (later the MCP server and
Claude Code plugin, ``0118``); agents call the *same* tools through the loop
harness (``agent.py``). There is no agent-only back door.

Effects:

* ``read`` — reads configuration, repositories, or the index;
* ``index`` — rebuilds the local index cache, catalog snapshots, or the drift
  list (reversible: they are caches);
* ``propose`` — stages something for human review (the feedback inbox, or a
  pack-amendment proposal for the named pack reviewer);
* ``execute_read`` — runs plugin-rendered, statically checked read-only SQL
  against a configured source (``0121`` research templates);
* ``report`` — writes a local run bundle under the configured output directory;
* ``human_only`` — a decision reserved for a person (promotion, discard).
  The harness refuses to give these to any agent, whatever its manifest says.

Inputs are validated against a small JSON-Schema subset (``type``,
``properties``, ``required``, ``enum``, ``items``, ``additionalProperties:
false``, ``minimum``, ``maxLength``) before a handler runs.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import access as access_mod
from . import catalog as catalog_mod
from . import feedback as feedback_mod
from . import governance
from .config import Config, ConfigError, validate_data
from .index import build_index, load_index, search

__all__ = ["EFFECTS", "ToolContext", "ToolError", "ToolRegistry", "ToolResult", "ToolSpec", "default_registry"]

EFFECTS = ("read", "index", "propose", "execute_read", "report", "human_only")


class ToolError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass
class ToolContext:
    config: Config
    today: str                                  # injected ISO date: no wall-clock reads
    actor: str = "sfmeridian"                   # pseudonymous handle of the caller or agent
    clients: Mapping[str, Any] = field(default_factory=dict)
    agents_root: Path | None = None          # for governance checks against agents/
    session: dict[str, Any] = field(default_factory=dict)   # run-scoped state (e.g. a research session)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    effect: str
    handler: Callable[[ToolContext, dict[str, Any]], dict[str, Any]]

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "effect": self.effect,
                "input_schema": self.input_schema}


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    output: dict[str, Any]
    error_code: str | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        out = {"ok": self.ok, "output": self.output}
        if not self.ok:
            out.update({"error_code": self.error_code, "error": self.error})
        return out


def _check(value: Any, schema: Mapping[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    kind = schema.get("type")
    types = {"object": dict, "array": list, "string": str, "boolean": bool, "integer": int, "number": (int, float)}
    if kind:
        expected = types[kind]
        if not isinstance(value, expected) or (kind in ("integer", "number") and isinstance(value, bool)):
            return [f"{path or 'input'}: expected {kind}"]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: must be one of {schema['enum']}")
    if kind == "string" and "maxLength" in schema and len(value) > schema["maxLength"]:
        errors.append(f"{path}: longer than {schema['maxLength']}")
    if kind in ("integer", "number") and "minimum" in schema and value < schema["minimum"]:
        errors.append(f"{path}: below {schema['minimum']}")
    if kind == "array" and "items" in schema:
        for i, item in enumerate(value):
            errors.extend(_check(item, schema["items"], f"{path}[{i}]"))
    if kind == "object":
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key}: required" if path else f"{key}: required")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append(f"{path}.{key}: unexpected" if path else f"{key}: unexpected")
        for key, sub in props.items():
            if key in value:
                errors.extend(_check(value[key], sub, f"{path}.{key}" if path else key))
    return errors


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.effect not in EFFECTS:
            raise ValueError(f"unknown effect {spec.effect!r}")
        if spec.name in self._tools:
            raise ValueError(f"duplicate tool {spec.name!r}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise ToolError("E_TOOL_UNKNOWN", f"no tool named {name!r}")
        return self._tools[name]

    def names(self) -> list[str]:
        return sorted(self._tools)

    def describe(self, names: Sequence[str] | None = None) -> list[dict[str, Any]]:
        return [self._tools[n].describe() for n in sorted(names or self._tools)]

    def call(self, name: str, args: Mapping[str, Any], ctx: ToolContext) -> ToolResult:
        try:
            spec = self.get(name)
            errors = _check(dict(args), spec.input_schema, "")
            if errors:
                raise ToolError("E_TOOL_INPUT", "; ".join(errors))
            return ToolResult(True, spec.handler(ctx, dict(args)))
        except ToolError as exc:
            return ToolResult(False, {}, exc.code, access_mod.scrub(exc.message))
        except ConfigError as exc:
            return ToolResult(False, {"issues": [i.as_dict() for i in exc.issues]}, "E_CONFIG_INVALID", str(exc))
        except (feedback_mod.FeedbackError, catalog_mod.CatalogError) as exc:
            return ToolResult(False, {}, exc.code, access_mod.scrub(exc.message))


# --------------------------------------------------------------------------
# Built-in tools (0114 slice)
# --------------------------------------------------------------------------

def _obj(properties: dict[str, Any], required: Sequence[str] = ()) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}


def _index_dir(ctx: ToolContext) -> Path:
    return ctx.config.resolve_path(ctx.config.data["index"]["dir"])


def _read_json(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _config_validate(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    issues = validate_data(ctx.config.data)
    return {"valid": not issues, "config_hash": ctx.config.hash, "issues": [i.as_dict() for i in issues]}


def _repos_index(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    report = build_index(ctx.config, repo_ids=args.get("repo_ids"), force=args.get("force", False),
                         clients=ctx.clients)
    return report.as_dict()


def _repos_status(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    index_dir = _index_dir(ctx)
    manifest = _read_json(index_dir / "manifest.json", {})
    exemplars = _read_jsonl(index_dir / "exemplars.jsonl")
    rejected = _read_jsonl(index_dir / "rejected.jsonl")
    repos = []
    for repo in ctx.config.data["query_repositories"]:
        rid = repo["id"]
        ex = [e for e in exemplars if e["repo_id"] == rid]
        by_status: dict[str, int] = {}
        for e in ex:
            by_status[e["review_status"]] = by_status.get(e["review_status"], 0) + 1
        repos.append({"repo_id": rid, "indexed": rid in manifest, "ref": manifest.get(rid, {}).get("ref"),
                      "files": len(manifest.get(rid, {}).get("files", {})), "exemplars": len(ex),
                      "by_status": dict(sorted(by_status.items())),
                      "rejected": sum(1 for r in rejected if r["repo_id"] == rid)})
    return {"repositories": repos,
            "feedback_exemplars": sum(1 for e in exemplars if e["provenance"] == "feedback")}


def _queries_search(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    index = load_index(_index_dir(ctx))
    hits = search(index, args["query"], limit=args.get("limit", 5), profile=args.get("profile"),
                  tags=args.get("tags", []), include_hints=args.get("include_hints", True),
                  min_score=ctx.config.data["grounding"]["retrieval_min_score"])
    return {"hits": [h.as_dict() for h in hits]}


def _queries_get(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    for e in _read_jsonl(_index_dir(ctx) / "exemplars.jsonl"):
        if e["exemplar_id"] == args["exemplar_id"]:
            return {"exemplar": e}
    raise ToolError("E_NOT_FOUND", f"no exemplar {args['exemplar_id']}")


def _index_rejections(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return {"rejected": _read_jsonl(_index_dir(ctx) / "rejected.jsonl")}


def _index_findings(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    out = []
    for e in _read_jsonl(_index_dir(ctx) / "exemplars.jsonl"):
        if e["findings"] or e["review_status"] == "unreviewed":
            out.append({"exemplar_id": e["exemplar_id"], "query_id": e["query_id"], "repo_id": e["repo_id"],
                        "path": e["path"], "review_status": e["review_status"], "findings": e["findings"],
                        "structure": {k: e["structure"][k] for k in ("tables", "params", "pit_columns")
                                      if k in e["structure"]} | {"select": [s["name"] for s in e["structure"]["select"]]}})
    return {"exemplars": out}


def _index_metrics(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    metrics = _read_json(_index_dir(ctx) / "metric_candidates.json", [])
    if args.get("conflicts_only", False):
        metrics = [m for m in metrics if m["conflict"]]
    return {"metrics": metrics}


def _index_joins(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    joins = _read_json(_index_dir(ctx) / "join_graph.json", [])
    table = args.get("table")
    if table:
        joins = [j for j in joins if j["left"].rsplit(".", 1)[0] == table or j["right"].rsplit(".", 1)[0] == table]
    return {"joins": joins}


def _inbox(ctx: ToolContext) -> feedback_mod.Inbox:
    return feedback_mod.Inbox(ctx.config.resolve_path(ctx.config.data["feedback"]["inbox"]))


def _feedback_propose(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    record = _inbox(ctx).propose(kind=args["kind"], payload=args["payload"], proposer=ctx.actor,
                                 proposed_on=ctx.today, source_run_id=args.get("source_run_id"))
    return {"candidate": record}


def _feedback_list(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return {"candidates": _inbox(ctx).list(args.get("status"))}


def _feedback_promote(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    record = _inbox(ctx).promote(args["candidate_id"], promoter=ctx.actor,
                                 promoters=ctx.config.data["feedback"]["promoters"], promoted_on=ctx.today,
                                 note=args.get("note"))
    return {"candidate": record}


def _feedback_discard(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    record = _inbox(ctx).discard(args["candidate_id"], by=ctx.actor, reason=args["reason"], discarded_on=ctx.today)
    return {"candidate": record}


def _governance_validate(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    if ctx.agents_root is None:
        raise ToolError("E_TOOL_INPUT", "governance checks need the agents/ root in the tool context")
    return governance.validate_all(ctx.agents_root, strict=args.get("strict", False), registry=default_registry())


_PAYLOAD = {"type": "object"}


def default_registry() -> ToolRegistry:
    reg = ToolRegistry()
    tools = [
        ToolSpec("config.validate", "Validate the resolved configuration and report its hash.",
                 _obj({}), "read", _config_validate),
        ToolSpec("repos.index", "Fetch configured query repositories and rebuild the index incrementally.",
                 _obj({"repo_ids": {"type": "array", "items": {"type": "string"}}, "force": {"type": "boolean"}}),
                 "index", _repos_index),
        ToolSpec("repos.status", "Per-repository ref, file, exemplar, and rejection counts.",
                 _obj({}), "read", _repos_status),
        ToolSpec("queries.search", "Search indexed exemplars; reviewed first, hints flagged.",
                 _obj({"query": {"type": "string", "maxLength": 2000}, "limit": {"type": "integer", "minimum": 1},
                       "profile": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}},
                       "include_hints": {"type": "boolean"}}, ["query"]), "read", _queries_search),
        ToolSpec("queries.get", "Fetch one exemplar with its citation and structure.",
                 _obj({"exemplar_id": {"type": "string"}}, ["exemplar_id"]), "read", _queries_get),
        ToolSpec("index.rejections", "Files the indexer rejected, with codes and reasons.",
                 _obj({}), "read", _index_rejections),
        ToolSpec("index.findings", "Exemplars carrying findings, and unannotated files.",
                 _obj({}), "read", _index_findings),
        ToolSpec("index.metrics", "Learned metric candidates; optionally only conflicting names.",
                 _obj({"conflicts_only": {"type": "boolean"}}), "read", _index_metrics),
        ToolSpec("index.joins", "Learned join graph; optionally edges touching one table.",
                 _obj({"table": {"type": "string"}}), "read", _index_joins),
        ToolSpec("feedback.propose", "Stage a candidate exemplar or correction for human review.",
                 _obj({"kind": {"type": "string", "enum": list(feedback_mod.KINDS)}, "payload": _PAYLOAD,
                       "source_run_id": {"type": "string"}}, ["kind", "payload"]), "propose", _feedback_propose),
        ToolSpec("feedback.list", "List inbox candidates by status.",
                 _obj({"status": {"type": "string", "enum": ["staged", "promoted", "discarded"]}}), "read",
                 _feedback_list),
        ToolSpec("feedback.promote", "Promote a staged candidate (configured human promoter only).",
                 _obj({"candidate_id": {"type": "string"}, "note": {"type": "string"}}, ["candidate_id"]),
                 "human_only", _feedback_promote),
        ToolSpec("feedback.discard", "Discard a staged candidate with a reason (human only).",
                 _obj({"candidate_id": {"type": "string"}, "reason": {"type": "string"}}, ["candidate_id", "reason"]),
                 "human_only", _feedback_discard),
        ToolSpec("governance.validate", "Validate the roster, handoff map, tooling catalog, agent manifests, "
                 "and core imports.", _obj({"strict": {"type": "boolean"}}), "read", _governance_validate),
    ]
    for tool in tools:
        reg.register(tool)
    from .research.tools import register as register_research
    from .semantic_tools import register as register_semantic
    register_research(reg)
    register_semantic(reg)
    return reg
