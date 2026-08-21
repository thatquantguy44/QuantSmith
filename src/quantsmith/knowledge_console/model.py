"""Filesystem store-loader and pure view-model builder for the Knowledge Console.

Spec ``0057-knowledge-console`` (T-001..T-005). Imports the ``0048`` runtime
(``quantsmith.pipelines.workflow_memory``) for parsing, typed records, freshness
constants, ranking, and validation — this module adds only the things ``0048``
left out: a loader that walks a whole ``memory/`` tree per its manifest, and a
deterministic view-model (counts, trends, graph, changes, review queue).

Design commitments:

- **Read-only.** Nothing here opens a file for writing under ``memory/`` (spec
  NFR-003).
- **Standard library only** (spec NFR-001) — the same constraint ``0048`` holds,
  for the same reason: the console must run in a copied scaffold with nothing
  installed.
- **Deterministic** (spec NFR-004). ``build_model`` is a pure function of its
  inputs; ordering is total everywhere; the only wall-clock value
  (``generated_at``) is *passed in*, never read from the clock here, so two
  builds with the same arguments are byte-identical.
- **Degrades, never crashes** (spec NFR-005). A missing tree, absent git, or an
  empty store yields a well-formed empty model.
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from quantsmith.pipelines import workflow_memory as wm

SHARED_WORKFLOW = "_shared"
_DEFAULT_FRESHNESS = 90
_RECORD_FILENAMES = ("index.yaml", "provenance.yaml")

# Severity ordering for the review queue (highest first).
_SEVERITY_RANK = {"error": 0, "warn": 1, "info": 2}


# --------------------------------------------------------------------------
# Loaded store
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class LoadedRecord:
    """A ``0048`` record tagged with the workflow it was loaded from.

    ``Record`` is frozen and has no workflow field (it is a property of *where*
    the record lives, not of the record), so attribution is carried alongside
    rather than by mutating the record.
    """

    record: wm.Record
    workflow: str


@dataclass(frozen=True)
class Store:
    """Every record loaded from one ``memory/`` tree, with governance metadata."""

    records: Tuple[LoadedRecord, ...]
    freshness_days: int = _DEFAULT_FRESHNESS
    files: Tuple[str, ...] = ()
    root: str = "memory"


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _manifest(root: Path) -> Dict:
    """Parse ``manifest.yaml`` into a dict; ``{}`` if absent or unreadable."""
    text = _read_text(root / "manifest.yaml")
    if text is None:
        return {}
    try:
        return wm.parse_memory_file(text, str(root / "manifest.yaml"))
    except wm.MemoryParseError:
        return {}


def _load_file(path: Path, workflow: str) -> Tuple[List[LoadedRecord], Optional[str]]:
    """Load one record catalog; return (records, source_file) or ([], None)."""
    text = _read_text(path)
    if text is None:
        return [], None
    try:
        records = wm.load_records(text, str(path))
    except wm.MemoryParseError:
        # A malformed catalog must not take the whole console down; it will show
        # up as a validation finding elsewhere. Skip its records loudly-in-logs,
        # quietly-in-UI (spec NFR-005).
        return [], str(path)
    return [LoadedRecord(record=r, workflow=workflow) for r in records], str(path)


def _iter_catalogs(base: Path):
    """Yield record-catalog files under ``base`` in a deterministic order."""
    if not base.is_dir():
        return
    for path in sorted(base.rglob("*")):
        if path.is_file() and path.name in _RECORD_FILENAMES:
            yield path


def load_store(root: str | os.PathLike = "memory") -> Store:
    """Load an entire ``memory/`` tree into a :class:`Store`.

    Follows ``manifest.yaml`` when present: the ``shared.path`` subtree is tagged
    ``_shared`` and each declared workflow's subtree is tagged with its name.
    When the manifest is missing, falls back to walking the tree and attributing
    each catalog to its top-level directory. Either way, a record from
    ``_shared/.../provenance.yaml`` and one from ``<workflow>/index.yaml`` both
    load, tagged with their workflow and source file (spec REQ-001, AC-001).

    A missing or empty tree yields an empty store — never an error (NFR-005).
    """
    root_path = Path(root)
    loaded: List[LoadedRecord] = []
    files: List[str] = []
    seen_dirs: set = set()

    if not root_path.is_dir():
        return Store(records=(), freshness_days=_DEFAULT_FRESHNESS, files=(), root=str(root_path))

    manifest = _manifest(root_path)
    defaults = manifest.get("defaults") or {}
    freshness = defaults.get("freshness_days", _DEFAULT_FRESHNESS)
    try:
        freshness = int(freshness)
    except (TypeError, ValueError):
        freshness = _DEFAULT_FRESHNESS

    def ingest(base: Path, workflow: str) -> None:
        resolved = base.resolve()
        if resolved in seen_dirs:
            return
        seen_dirs.add(resolved)
        for path in _iter_catalogs(base):
            recs, src = _load_file(path, workflow)
            loaded.extend(recs)
            if src is not None:
                files.append(src)

    used_manifest = False
    if manifest:
        shared = manifest.get("shared") or {}
        shared_path = shared.get("path", SHARED_WORKFLOW)
        ingest(root_path / str(shared_path), SHARED_WORKFLOW)

        for wf in manifest.get("workflows") or []:
            if not isinstance(wf, dict):
                continue
            name = str(wf.get("name") or "").strip()
            wf_path = str(wf.get("path") or name)
            if not name:
                continue
            base = Path(wf_path)
            if not base.is_absolute():
                base = root_path / wf_path
            # External/absolute stores may be unreadable in a copied scaffold;
            # ingest() simply finds nothing and moves on (NFR-005).
            ingest(base, name)
            used_manifest = True

    if not used_manifest:
        # No manifest (or no workflows declared): walk and attribute by top dir.
        for path in _iter_catalogs(root_path):
            rel = path.relative_to(root_path)
            workflow = rel.parts[0] if len(rel.parts) > 1 else SHARED_WORKFLOW
            recs, src = _load_file(path, workflow)
            loaded.extend(recs)
            if src is not None:
                files.append(src)

    # Deduplicate by (source_file, record id) in case manifest + fallback overlap.
    unique: Dict[Tuple[str, str], LoadedRecord] = {}
    for lr in loaded:
        unique[(lr.record.source_file, lr.record.id)] = lr

    ordered = tuple(sorted(unique.values(), key=lambda lr: (lr.record.id, lr.record.source_file)))
    return Store(
        records=ordered,
        freshness_days=freshness,
        files=tuple(sorted(set(files))),
        root=str(root_path),
    )


# --------------------------------------------------------------------------
# Recent changes feed (T-004, REQ-005)
# --------------------------------------------------------------------------

def git_changes(root: str | os.PathLike = "memory", *, limit: int = 50) -> List[Dict]:
    """Recent git commits touching the memory tree, newest first.

    Uses author *name* (never email — the memory gate forbids addresses in the
    tree, and the feed should not reintroduce one). Degrades to an empty list on
    any failure — no git, no history, a shallow clone, a timeout — so the page
    renders either way (spec AC-007, NFR-005).
    """
    root_path = Path(root)
    repo = root_path.parent if root_path.name else root_path
    sep = "\x1f"
    fmt = sep.join(["%h", "%an", "%aI", "%s"])
    try:
        out = subprocess.run(
            ["git", "log", f"-n{int(limit)}", f"--pretty=format:{fmt}",
             "--name-only", "--", str(root_path)],
            cwd=str(repo) if repo.exists() else None,
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0 or not out.stdout.strip():
        return []

    changes: List[Dict] = []
    current: Optional[Dict] = None
    for line in out.stdout.splitlines():
        if sep in line:
            if current is not None:
                changes.append(current)
            h, author, date, subject = (line.split(sep) + ["", "", "", ""])[:4]
            current = {"hash": h, "author": author, "date": date,
                       "subject": subject, "files": []}
        elif line.strip() and current is not None:
            current["files"].append(line.strip())
    if current is not None:
        changes.append(current)
    return changes


# --------------------------------------------------------------------------
# View-model builder (T-002, T-003, REQ-002, REQ-003, REQ-013, NFR-004)
# --------------------------------------------------------------------------

def _record_view(lr: LoadedRecord, as_of: datetime.date, freshness_days: int) -> Dict:
    r = lr.record
    days = (as_of - r.last_confirmed).days
    runs = sorted({e["source_run"] for e in r.evidence if "source_run" in e})
    return {
        "id": r.id,
        "scope": r.scope,
        "type": r.type,
        "statement": r.statement,
        "confidence": r.confidence,
        "corroboration_count": r.corroboration_count,
        "corroboration_derived": r.corroboration_derived,
        "first_seen": r.first_seen.isoformat(),
        "last_confirmed": r.last_confirmed.isoformat(),
        "status": r.status,
        "pit_scope": r.pit_scope,
        "access_level": r.access_level,
        "author": r.author,
        "workflow": lr.workflow,
        "source_file": r.source_file,
        "days_since_confirmed": days,
        "overdue": days > freshness_days,
        "evidence_runs": runs,
    }


def _tally(values) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    return {k: counts[k] for k in sorted(counts)}


def _trends(records: Sequence[wm.Record], as_of: datetime.date,
            freshness_days: int) -> Dict:
    # Cumulative record count by first_seen (non-decreasing, ends at total).
    by_date: Dict[str, int] = {}
    for r in records:
        d = r.first_seen.isoformat()
        by_date[d] = by_date.get(d, 0) + 1
    cumulative: List[Dict] = []
    running = 0
    for d in sorted(by_date):
        running += by_date[d]
        cumulative.append({"date": d, "count": running})

    # Confirmations by month from last_confirmed.
    by_month: Dict[str, int] = {}
    for r in records:
        m = r.last_confirmed.strftime("%Y-%m")
        by_month[m] = by_month.get(m, 0) + 1
    confirmations = [{"month": m, "count": by_month[m]} for m in sorted(by_month)]

    # Staleness split against the freshness policy.
    fresh = overdue = 0
    for r in records:
        if (as_of - r.last_confirmed).days > freshness_days:
            overdue += 1
        else:
            fresh += 1

    return {
        "cumulative_by_date": cumulative,
        "confirmations_by_month": confirmations,
        "staleness": {"fresh": fresh, "overdue": overdue},
    }


def build_graph(store: Store) -> Dict:
    """Nodes and edges linking records to their workflow, scope, and evidence runs.

    Deterministic: nodes sorted by id, edges by (source, target, kind). Every
    record node has an edge to its workflow node and its scope node; a run node
    exists for each distinct ``source_run`` (spec REQ-004, AC-006).
    """
    nodes: Dict[str, Dict] = {}
    edges: set = set()

    def add_node(node_id: str, label: str, kind: str, **meta) -> None:
        if node_id not in nodes:
            nodes[node_id] = {"id": node_id, "label": label, "kind": kind, "meta": {}}
        # Accumulate a record count in meta for grouping nodes.
        if meta:
            nodes[node_id]["meta"].update(meta)

    wf_counts: Dict[str, int] = {}
    scope_counts: Dict[str, int] = {}

    for lr in store.records:
        r = lr.record
        rec_id = f"rec:{r.id}"
        wf_id = f"wf:{lr.workflow}"
        scope_id = f"scope:{r.scope}"
        add_node(rec_id, r.id, "record",
                 type=r.type, confidence=r.confidence, status=r.status,
                 access_level=r.access_level, workflow=lr.workflow)
        add_node(wf_id, lr.workflow, "workflow")
        add_node(scope_id, r.scope, "scope")
        wf_counts[wf_id] = wf_counts.get(wf_id, 0) + 1
        scope_counts[scope_id] = scope_counts.get(scope_id, 0) + 1
        edges.add((rec_id, wf_id, "in_workflow"))
        edges.add((rec_id, scope_id, "about"))
        for e in r.evidence:
            run = e.get("source_run")
            if run:
                run_id = f"run:{run}"
                add_node(run_id, run, "run")
                edges.add((rec_id, run_id, "evidenced_by"))

    for wf_id, c in wf_counts.items():
        nodes[wf_id]["meta"]["record_count"] = c
    for scope_id, c in scope_counts.items():
        nodes[scope_id]["meta"]["record_count"] = c

    node_list = [nodes[k] for k in sorted(nodes)]
    edge_list = [{"source": s, "target": t, "kind": k}
                 for (s, t, k) in sorted(edges)]
    return {"nodes": node_list, "edges": edge_list}


def build_review_queue(store: Store, as_of: datetime.date,
                       findings: Sequence[wm.Finding]) -> List[Dict]:
    """The needed-review queue: every record carrying a curation signal.

    Signals (spec REQ-006):
    - **freshness** — ``last_confirmed`` older than ``freshness_days`` as of
      ``as_of`` (severity warn).
    - **validation** — any ``validate()`` error/warn finding on the record
      (severity from the finding).
    - **unsupported confidence** — declared ``corroboration_count`` exceeds the
      count derived from evidence, or ``high`` confidence on <=1 evidence run
      (severity warn). This is the MEM-0001 case (AC-008).
    - **thin corroboration** — an ``active`` record with fewer than two distinct
      evidence runs (severity info).

    An item's severity is the most severe of its reasons. Ordered by severity
    then id (deterministic).
    """
    findings_by_id: Dict[str, List[wm.Finding]] = {}
    for f in findings:
        if f.severity in ("error", "warn"):
            findings_by_id.setdefault(f.record_id, []).append(f)

    queue: List[Dict] = []
    for lr in store.records:
        r = lr.record
        reasons: List[Dict] = []
        days = (as_of - r.last_confirmed).days

        if days > store.freshness_days:
            reasons.append({
                "kind": "freshness", "severity": "warn",
                "detail": (f"last confirmed {days}d ago; policy re-validates after "
                           f"{store.freshness_days}d"),
            })

        for f in findings_by_id.get(r.id, []):
            reasons.append({"kind": "validation", "severity": f.severity,
                            "detail": f.message})

        if r.corroboration_count > r.corroboration_derived:
            reasons.append({
                "kind": "unsupported_confidence", "severity": "warn",
                "detail": (f"declares corroboration_count {r.corroboration_count} "
                           f"but evidences {r.corroboration_derived} distinct run(s)"),
            })
        elif r.confidence == "high" and r.corroboration_derived <= 1:
            reasons.append({
                "kind": "unsupported_confidence", "severity": "warn",
                "detail": (f"high confidence on {r.corroboration_derived} evidence "
                           "run(s)"),
            })

        if r.status == "active" and r.corroboration_derived < 2:
            reasons.append({
                "kind": "thin_corroboration", "severity": "info",
                "detail": (f"only {r.corroboration_derived} distinct evidence "
                           "run(s); corroborate before treating as fact"),
            })

        if not reasons:
            continue
        severity = min((rr["severity"] for rr in reasons),
                       key=lambda s: _SEVERITY_RANK.get(s, 9))
        queue.append({
            "record_id": r.id,
            "severity": severity,
            "reasons": reasons,
            "scope": r.scope,
            "type": r.type,
            "workflow": lr.workflow,
            "last_confirmed": r.last_confirmed.isoformat(),
            "access_level": r.access_level,
        })

    queue.sort(key=lambda item: (_SEVERITY_RANK.get(item["severity"], 9),
                                 item["record_id"]))
    return queue


def build_model(store: Store, *, as_of: Optional[datetime.date] = None,
                changes: Optional[Sequence[Dict]] = None,
                generated_at: Optional[str] = None) -> Dict:
    """Build the full JSON view-model. Pure and deterministic (spec NFR-004).

    ``generated_at`` is *passed in*, never read from the clock here, so identical
    inputs produce byte-identical output (AC-002). The server passes a wall-clock
    timestamp; tests pass a fixed one or ``None``.
    """
    as_of = as_of or datetime.date.today()
    changes = list(changes) if changes is not None else []

    plain = [lr.record for lr in store.records]
    findings = wm.validate(plain)

    records_view = [_record_view(lr, as_of, store.freshness_days)
                    for lr in store.records]
    records_view.sort(key=lambda d: d["id"])

    counts = {
        "total": len(store.records),
        "by_type": _tally(r.type for r in plain),
        "by_status": _tally(r.status for r in plain),
        "by_confidence": _tally(r.confidence for r in plain),
        "by_access_level": _tally(r.access_level for r in plain),
        "by_workflow": _tally(lr.workflow for lr in store.records),
    }

    model = {
        "generated_at": generated_at,
        "as_of": as_of.isoformat(),
        "freshness_days": store.freshness_days,
        "counts": counts,
        "records": records_view,
        "trends": _trends(plain, as_of, store.freshness_days),
        "graph": build_graph(store),
        "changes": changes,
        "review_queue": build_review_queue(store, as_of, findings),
        "findings": [
            {"record_id": f.record_id, "severity": f.severity,
             "message": f.message, "file": f.file}
            for f in findings
        ],
    }
    return model


def build_model_from_root(root: str | os.PathLike = "memory", *,
                          as_of: Optional[datetime.date] = None,
                          generated_at: Optional[str] = None,
                          with_changes: bool = True) -> Dict:
    """Convenience: load a tree and build its model in one call."""
    store = load_store(root)
    changes = git_changes(root) if with_changes else []
    return build_model(store, as_of=as_of, changes=changes,
                       generated_at=generated_at)


def model_json(model: Dict) -> str:
    """Serialise a model deterministically (sorted keys, compact-ish)."""
    return json.dumps(model, ensure_ascii=False, sort_keys=True, indent=2)
