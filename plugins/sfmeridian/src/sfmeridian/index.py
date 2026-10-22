"""Index query repositories into cited exemplars and learned structure; search them.

Spec ``0114`` REQ-006 and REQ-007 (realizing ``0113`` REQ-006, REQ-009's
retrieval half, NFR-001, NFR-005).

Artifacts under the configured ``index.dir`` (all sorted, all byte-stable):

* ``exemplars.jsonl`` — one record per indexed query, content-addressed;
* ``rejected.jsonl`` — files that failed, with code, reason, and line;
* ``join_graph.json`` — table-column pairs seen joined, with support;
* ``metric_candidates.json`` — named select expressions, with a conflict flag;
* ``filter_patterns.json`` — filtered columns and operators (no literals);
* ``manifest.json`` — per repository: resolved ref and file content hashes.

Re-indexing unchanged inputs rewrites nothing. The index holds SQL and
metadata only — never result rows, never credentials.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import feedback as feedback_mod
from .config import Config
from .frontmatter import ParsedQuery, QueryRejected, parse_query, validate_meta
from .repos import ObjectStoreClient, RepoFetchError, RepoSnapshot, fetch
from .sqlstructure import extract

__all__ = ["Hit", "Index", "IndexReport", "build_index", "load_index", "search"]

ARTIFACTS = ("exemplars.jsonl", "rejected.jsonl", "join_graph.json", "metric_candidates.json",
             "filter_patterns.json", "manifest.json")
FEEDBACK_REPO = "feedback"


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _write_if_changed(path: Path, text: str) -> bool:
    data = text.encode("utf-8")
    if path.exists() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    return True


def _eligibility(status: str, trust_tier: str, policy: str) -> str:
    if status == "deprecated":
        return "never"
    if status == "reviewed" and trust_tier in ("reviewed", "team"):
        return "primary"
    return "hint" if policy == "allow_unreviewed_as_hints" else "never"


def _exemplar(repo: Mapping[str, Any], snapshot_ref: str, path: str, sql_sha: str,
              parsed, provenance: str = "repository") -> dict[str, Any]:
    meta = parsed.meta or {}
    status = parsed.review_status
    exemplar_id = hashlib.sha256(f"{repo['id']}\0{path}\0{sql_sha}".encode()).hexdigest()[:16]
    return {
        "exemplar_id": exemplar_id,
        "query_id": meta.get("id"),
        "repo_id": repo["id"],
        "ref": snapshot_ref,
        "path": path,
        "line_span": list(parsed.line_span),
        "sql_sha256": sql_sha,
        "normalized_sql_hash": parsed.structure["normalized_sql_hash"],
        "title": meta.get("title"),
        "intent": " ".join(str(meta.get("intent", "")).split()) or None,
        "owner": meta.get("owner"),
        "dialect": meta.get("dialect", repo["dialect"]),
        "profile": meta.get("profile", repo.get("database_profile")),
        "params": meta.get("params", []),
        "tables": meta.get("tables", []),
        "pit_columns": meta.get("pit_columns", []),
        "grain": meta.get("grain"),
        "concepts": meta.get("concepts", []) or [],
        "viewpoint": meta.get("viewpoint"),
        "tags": meta.get("tags", []) or [],
        "supersedes": meta.get("supersedes"),
        "review_status": status,
        "reviewed_by": meta.get("reviewed_by"),
        "reviewed_on": meta.get("reviewed_on"),
        "trust_tier": repo.get("trust_tier", "reviewed"),
        "eligibility": _eligibility(status, repo.get("trust_tier", "reviewed"), repo.get("review_policy", "reviewed_only")),
        "provenance": provenance,
        "structure": parsed.structure,
        "findings": parsed.findings,
    }


@dataclass
class IndexReport:
    repositories: list[dict[str, Any]] = field(default_factory=list)
    written: list[str] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "repositories": self.repositories, "written": self.written, "errors": self.errors}


def _load_previous(index_dir: Path) -> tuple[dict[str, Any], dict[tuple[str, str], dict[str, Any]],
                                              dict[tuple[str, str], dict[str, Any]]]:
    manifest = {}
    if (index_dir / "manifest.json").exists():
        manifest = json.loads((index_dir / "manifest.json").read_text(encoding="utf-8"))
    exemplars = {(e["repo_id"], e["path"]): e for e in _read_jsonl(index_dir / "exemplars.jsonl")}
    rejected = {(r["repo_id"], r["path"]): r for r in _read_jsonl(index_dir / "rejected.jsonl")}
    return manifest, exemplars, rejected


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sidecar_for(snapshot: RepoSnapshot, path: str):
    stem = path[:-4]
    return snapshot.file(stem + ".yml") or snapshot.file(stem + ".yaml")


def _index_repo(repo: Mapping[str, Any], snapshot: RepoSnapshot, previous_files: Mapping[str, str],
                prev_ex: Mapping[tuple[str, str], dict[str, Any]],
                prev_rej: Mapping[tuple[str, str], dict[str, Any]]):
    exemplars: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    files: dict[str, str] = {}
    parsed_count = reused = 0
    sidecar_mode = repo.get("metadata_convention") == "sidecar"
    for source in snapshot.files:
        if not source.path.endswith(".sql"):
            continue
        sidecar = _sidecar_for(snapshot, source.path) if sidecar_mode else None
        content_key = source.sha256 + (":" + sidecar.sha256 if sidecar else "")
        files[source.path] = content_key
        key = (repo["id"], source.path)
        if previous_files.get(source.path) == content_key and (key in prev_ex or key in prev_rej):
            reused += 1
            if key in prev_ex:
                exemplars.append({**prev_ex[key], "ref": snapshot.ref})
            else:
                rejected.append({**prev_rej[key], "ref": snapshot.ref})
            continue
        parsed_count += 1
        try:
            text = source.data.decode("utf-8")
        except UnicodeDecodeError:
            rejected.append({"repo_id": repo["id"], "ref": snapshot.ref, "path": source.path,
                             "code": "E_SQL_UNREADABLE", "reason": "file is not UTF-8", "line": 0})
            continue
        try:
            parsed = parse_query(text, f"{repo['id']}:{source.path}", dialect=repo["dialect"],
                                 sidecar=sidecar.data.decode("utf-8") if sidecar else None)
        except QueryRejected as exc:
            rejected.append({"repo_id": repo["id"], "ref": snapshot.ref, "path": source.path,
                             "code": exc.code, "reason": exc.reason, "line": exc.line})
            continue
        exemplars.append(_exemplar(repo, snapshot.ref, source.path, source.sha256, parsed))
    stats = {"repo_id": repo["id"], "kind": snapshot.kind, "ref": snapshot.ref, "files": len(files),
             "parsed": parsed_count, "reused": reused}
    return exemplars, rejected, files, stats


def _feedback_exemplars(config: Config) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    inbox = feedback_mod.Inbox(config.resolve_path(config.data["feedback"]["inbox"]))
    exemplars, rejected = [], []
    repo = {"id": FEEDBACK_REPO, "dialect": "sqlite", "database_profile": None,
            "trust_tier": "reviewed", "review_policy": "reviewed_only"}
    for record in inbox.promoted():
        payload = record["payload"]
        path = f"promoted/{record['candidate_id']}.json"
        meta = {
            "id": payload.get("query_id") or f"feedback.{record['candidate_id']}",
            "title": payload.get("title"), "intent": payload.get("intent"),
            "review_status": "reviewed", "owner": record["proposer"],
            "dialect": payload.get("dialect"), "profile": payload.get("profile"),
            "params": payload.get("params", []), "tables": payload.get("tables", []),
            "pit_columns": payload.get("pit_columns", []), "grain": payload.get("grain"),
            "reviewed_by": record["promoted_by"], "reviewed_on": record["promoted_on"],
            "tags": payload.get("tags", []), "concepts": payload.get("concepts", []),
            "viewpoint": payload.get("viewpoint"),
        }
        meta = {k: v for k, v in meta.items() if v is not None}
        sql = payload.get("sql", "")
        try:
            structure = extract(sql, payload.get("dialect") or "sqlite")
            findings = validate_meta(meta, structure)
        except (QueryRejected, ValueError) as exc:
            rejected.append({"repo_id": FEEDBACK_REPO, "ref": "inbox", "path": path,
                             "code": getattr(exc, "code", "E_SQL_UNREADABLE"),
                             "reason": getattr(exc, "reason", str(exc)), "line": 0})
            continue
        parsed = ParsedQuery(meta, sql, (1, max(1, len(sql.splitlines()))), structure, findings)
        sql_sha = hashlib.sha256(sql.encode("utf-8")).hexdigest()
        exemplars.append(_exemplar(repo, "inbox", path, sql_sha, parsed, provenance="feedback"))
    return exemplars, rejected


def _aggregate(exemplars: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]],
                                                                list[dict[str, Any]]]:
    joins: dict[tuple[str, str], dict[str, Any]] = {}
    metrics: dict[str, dict[str, Any]] = {}
    filters: dict[tuple[str, str], dict[str, Any]] = {}
    for e in exemplars:
        if e["eligibility"] == "never":
            continue
        primary = e["eligibility"] == "primary"
        s = e["structure"]
        for j in s["joins"]:
            entry = joins.setdefault((j["left"], j["right"]), {
                "left": j["left"], "right": j["right"], "join_types": set(),
                "support": 0, "hint_support": 0, "exemplar_ids": set()})
            entry["join_types"].update(j["join_types"])
            entry["support" if primary else "hint_support"] += 1
            entry["exemplar_ids"].add(e["exemplar_id"])
        for item in s["select"]:
            if not item["metric"] or not item["name"]:
                continue
            m = metrics.setdefault(item["name"], {"name": item["name"], "definitions": {}})
            d = m["definitions"].setdefault(item["expression"], {
                "expression": item["expression"], "columns": item["columns"], "aggregates": item["aggregates"],
                "review_statuses": set(), "exemplar_ids": set()})
            d["review_statuses"].add(e["review_status"])
            d["exemplar_ids"].add(e["exemplar_id"])
        if primary:
            for f in s["filters"]:
                value_kind = "param" if f["value"].startswith((":", "%(", "$")) else (
                    "null" if f["value"] == "NULL" else "literal")
                entry = filters.setdefault((f["column"], f["op"]), {
                    "column": f["column"], "op": f["op"], "value_kinds": set(), "params": set(),
                    "support": 0, "exemplar_ids": set()})
                entry["value_kinds"].add(value_kind)
                entry["params"].update(v for v in f["value"].replace("..", ",").split(",")
                                       if v.startswith((":", "%(", "$")))
                entry["support"] += 1
                entry["exemplar_ids"].add(e["exemplar_id"])

    def finish(d: dict[str, Any]) -> dict[str, Any]:
        return {k: sorted(v) if isinstance(v, set) else v for k, v in d.items()}

    join_list = [finish(v) for _, v in sorted(joins.items())]
    metric_list = []
    for name, m in sorted(metrics.items()):
        definitions = [finish(d) for _, d in sorted(m["definitions"].items())]
        metric_list.append({"name": name, "conflict": len(definitions) > 1, "definitions": definitions})
    filter_list = [finish(v) for _, v in sorted(filters.items())]
    return join_list, metric_list, filter_list


def build_index(config: Config, *, repo_ids: Iterable[str] | None = None, force: bool = False,
                clients: Mapping[str, ObjectStoreClient] | None = None) -> IndexReport:
    """Index the configured repositories; return what was parsed, reused, and written."""
    index_dir = config.resolve_path(config.data["index"]["dir"])
    base_dir = config.resolve_path(".")
    cache_dir = index_dir / "cache"
    manifest, prev_ex, prev_rej = ({}, {}, {}) if force else _load_previous(index_dir)
    wanted = set(repo_ids) if repo_ids else None
    report = IndexReport()
    exemplars: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    new_manifest: dict[str, Any] = {}

    for repo in config.data["query_repositories"]:
        repo_id = repo["id"]
        if wanted is not None and repo_id not in wanted:
            # Keep the previous state of repositories not asked for.
            exemplars.extend(e for (r, _), e in prev_ex.items() if r == repo_id)
            rejected.extend(x for (r, _), x in prev_rej.items() if r == repo_id)
            if repo_id in manifest:
                new_manifest[repo_id] = manifest[repo_id]
            continue
        try:
            snapshot = fetch(repo, base_dir=base_dir, cache_dir=cache_dir, clients=clients)
        except RepoFetchError as exc:
            report.errors.append({"repo_id": repo_id, "code": exc.code, "message": exc.message})
            exemplars.extend(e for (r, _), e in prev_ex.items() if r == repo_id)
            rejected.extend(x for (r, _), x in prev_rej.items() if r == repo_id)
            if repo_id in manifest:
                new_manifest[repo_id] = manifest[repo_id]
            continue
        previous_files = manifest.get(repo_id, {}).get("files", {})
        ex, rej, files, stats = _index_repo(repo, snapshot, previous_files, prev_ex, prev_rej)
        exemplars.extend(ex)
        rejected.extend(rej)
        new_manifest[repo_id] = {"kind": snapshot.kind, "ref": snapshot.ref, "files": files}
        report.repositories.append({**stats, "exemplars": len(ex), "rejected": len(rej)})

    fb_ex, fb_rej = _feedback_exemplars(config)
    exemplars.extend(fb_ex)
    rejected.extend(fb_rej)

    # Duplicate query ids: a reviewed file keeps the id over a draft or a
    # deprecated one; (repo, path) order breaks ties.
    rank = {"reviewed": 0, "draft": 1, "deprecated": 2}
    exemplars.sort(key=lambda e: (rank.get(e["review_status"], 3), e["repo_id"], e["path"]))
    seen: dict[str, str] = {}
    unique: list[dict[str, Any]] = []
    for e in exemplars:
        qid = e["query_id"]
        if qid is not None and qid in seen:
            rejected.append({"repo_id": e["repo_id"], "ref": e["ref"], "path": e["path"],
                             "code": "E_FRONTMATTER_DUPLICATE_ID",
                             "reason": f"query id {qid!r} is already used by {seen[qid]}", "line": 0})
            continue
        if qid is not None:
            seen[qid] = f"{e['repo_id']}:{e['path']}"
        unique.append(e)
    unique.sort(key=lambda e: e["exemplar_id"])
    rejected.sort(key=lambda r: (r["repo_id"], r["path"], r["code"]))
    joins, metrics, filters = _aggregate(unique)

    outputs = {
        "exemplars.jsonl": "".join(_json(e) + "\n" for e in unique),
        "rejected.jsonl": "".join(_json(r) + "\n" for r in rejected),
        "join_graph.json": json.dumps(joins, sort_keys=True, indent=1) + "\n",
        "metric_candidates.json": json.dumps(metrics, sort_keys=True, indent=1) + "\n",
        "filter_patterns.json": json.dumps(filters, sort_keys=True, indent=1) + "\n",
        "manifest.json": json.dumps(new_manifest, sort_keys=True, indent=1) + "\n",
    }
    for name in ARTIFACTS:
        if _write_if_changed(index_dir / name, outputs[name]):
            report.written.append(name)
    return report


# --------------------------------------------------------------------------
# Search
# --------------------------------------------------------------------------

_STOP = frozenset(["a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "in", "is", "it", "of", "on", "or", "per", "the", "to", "what", "which", "with", "show", "me", "give", "list", "get"])
_K1, _B = 1.2, 0.75


def _terms(text: str) -> list[str]:
    out: list[str] = []
    for word in re.findall(r"[A-Za-z0-9_.]+", text.lower()):
        pieces = [p for p in re.split(r"[._]", word) if p]
        for piece in pieces:
            if piece not in _STOP:
                out.append(piece)
        if len(pieces) > 1:
            out.append(word)
    return out


def _doc_text(e: Mapping[str, Any]) -> str:
    fields = [e.get("query_id") or "", e.get("title") or "", e.get("intent") or "",
              " ".join(e.get("tags", [])), " ".join(e.get("concepts", [])), " ".join(e.get("tables", [])),
              " ".join(p.get("name", "") for p in e.get("params", []) if isinstance(p, dict)),
              " ".join(s["name"] for s in e["structure"]["select"] if s["name"])]
    return " ".join(fields)


@dataclass(frozen=True)
class Hit:
    score: float
    hint: bool
    exemplar: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        e = self.exemplar
        return {"score": round(self.score, 6), "hint": self.hint, "exemplar_id": e["exemplar_id"],
                "query_id": e["query_id"], "title": e["title"], "review_status": e["review_status"],
                "citation": {"repo_id": e["repo_id"], "ref": e["ref"], "path": e["path"],
                             "line_span": e["line_span"]}}


class Index:
    def __init__(self, exemplars: list[dict[str, Any]]) -> None:
        self.exemplars = [e for e in exemplars if e["eligibility"] != "never"]
        self.docs = [Counter(_terms(_doc_text(e))) for e in self.exemplars]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg_len = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        df: Counter = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def get(self, exemplar_id: str) -> dict[str, Any] | None:
        return next((e for e in self.exemplars if e["exemplar_id"] == exemplar_id), None)


def load_index(index_dir: Path) -> Index:
    return Index(_read_jsonl(Path(index_dir) / "exemplars.jsonl"))


def search(index: Index, query: str, *, limit: int = 5, profile: str | None = None,
           tags: Sequence[str] = (), include_hints: bool = True, min_score: float = 0.0) -> list[Hit]:
    """BM25 over exemplar metadata; normalized score in ``[0, 1)``.

    The score is BM25 divided by its supremum for the query, Σ idf·(k1+1), so
    it is comparable across queries. Reviewed (``primary``) exemplars rank
    before hints; ties break by exemplar ID.
    """
    q_terms = sorted(set(_terms(query)))
    ceiling = sum(self_idf * (_K1 + 1) for self_idf in (index.idf.get(t, 0.0) for t in q_terms))
    hits: list[Hit] = []
    for e, doc, length in zip(index.exemplars, index.docs, index.lengths):
        if profile and e.get("profile") not in (profile, None):
            continue
        if tags and not set(tags) <= set(e.get("tags", [])):
            continue
        hint = e["eligibility"] == "hint"
        if hint and not include_hints:
            continue
        score = 0.0
        for t in q_terms:
            tf = doc.get(t, 0)
            if not tf:
                continue
            norm = 1 - _B + _B * (length / index.avg_len if index.avg_len else 0)
            score += index.idf[t] * tf * (_K1 + 1) / (tf + _K1 * norm)
        normalized = score / ceiling if ceiling else 0.0
        if normalized > 0 and normalized >= min_score:
            hits.append(Hit(normalized, hint, e))
    hits.sort(key=lambda h: (h.hint, -h.score, h.exemplar["exemplar_id"]))
    return hits[:limit]
