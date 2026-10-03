"""Venture knowledge integration for spec 0092.

Ties the venture work to the repository's existing knowledge systems without changing them:

* **Local store.** Validates the gitignored ``knowledge_local/<domain>/`` stores that pair with the
  committed packs under ``knowledge/`` and refuses to stage anything outside them.
* **Memory.** Builds ``0049`` write-path candidates (source quirks, channel lessons, screening
  decisions) and stages them to a local inbox. Nothing is promoted here: a named human promotes.
* **Retrieval contract.** A deterministic, standard-library retriever that implements the order of
  operations the live RAG server (``0054``) must also follow: clearance filter first, then
  point-in-time filter, then ranking on the *eligible* passages only, returning cited spans or an
  explicit ``not_found`` that is indistinguishable from "only restricted material matched".
  ``retrieval_contract_violations`` checks any retriever's output against that contract.

No network, no model, no embeddings. Live semantic search stays with ``0054``.
"""

from __future__ import annotations

import hashlib
import math
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from quantsmith.adapters.mcp_servers.contract import ACCESS_RANK, clearance_allows, contains_secret
from quantsmith.asian_nlp import segment

from . import workflow_memory as wm
from .access_control import AUTHOR_HANDLE_RE

ACCESS_LEVELS = tuple(sorted(ACCESS_RANK, key=ACCESS_RANK.get))
LOCAL_ROOT = "knowledge_local"
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
MAX_STATEMENT_CHARS = 500
BM25_K1, BM25_B = 1.5, 0.75


# ------------------------------------------------------------------ local store
def parse_flat_yaml(text: str) -> Dict[str, str]:
    """Parse a flat ``key: value`` file (comments and blank lines ignored). No nesting."""
    out: Dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].rstrip() if " #" in raw else raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def validate_store(store_dir: Path) -> List[str]:
    """Errors for one ``knowledge_local/<domain>/`` store; empty when it is sound."""
    store_dir = Path(store_dir)
    errors: List[str] = []
    manifest = store_dir / "store.yml"
    if not manifest.is_file():
        return [f"{store_dir.name}: store.yml is missing"]
    meta = parse_flat_yaml(manifest.read_text(encoding="utf-8"))
    if meta.get("domain") != store_dir.name:
        errors.append(f"{store_dir.name}: domain {meta.get('domain')!r} does not match the folder name")
    if meta.get("access_level") not in ACCESS_RANK:
        errors.append(f"{store_dir.name}: access_level must be one of {', '.join(ACCESS_LEVELS)}")
    if not AUTHOR_HANDLE_RE.match(meta.get("owner", "")):
        errors.append(f"{store_dir.name}: owner must be a pseudonymous handle, not a name or email")
    elif meta["owner"] == "your-pseudonymous-handle":
        errors.append(f"{store_dir.name}: owner is still the template placeholder")
    if EMAIL_RE.search(manifest.read_text(encoding="utf-8")):
        errors.append(f"{store_dir.name}: store.yml contains an email address")
    return errors


def tracked_files_under(repo_root: Path, folder: str = LOCAL_ROOT) -> List[str]:
    """Files git tracks under ``folder`` (must be empty). Returns [] when git is unavailable."""
    repo_root = Path(repo_root)
    if not (repo_root / ".git").exists():
        return []
    try:
        out = subprocess.run(["git", "ls-files", folder], cwd=repo_root, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return []
    return [line for line in out.stdout.splitlines() if line.strip()]


# ----------------------------------------------------------------------- memory
def _check_statement(statement: str) -> str:
    s = " ".join(statement.split())
    if not s:
        raise ValueError("memory statement is empty")
    if len(s) > MAX_STATEMENT_CHARS:
        raise ValueError(f"memory statement exceeds {MAX_STATEMENT_CHARS} characters")
    if contains_secret(s):
        raise ValueError("memory statement looks like it contains a credential")
    if EMAIL_RE.search(s):
        raise ValueError("memory statement contains an email address")
    return s


def load_source_quality(path: Path) -> Dict[str, Any]:
    """Read ``quality.known_issues`` and ``last_assessed`` from a ``sources/*.yml`` file (flat-line parse)."""
    issues: List[str] = []
    last = ""
    in_issues = False
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("known_issues:"):
            in_issues = True
            continue
        if in_issues:
            m = re.match(r'^\s{4}-\s+"(.*)"\s*$', line)
            if m:
                issues.append(m.group(1))
                continue
            in_issues = False
        m = re.match(r'^\s*last_assessed:\s*"?([0-9-]+)"?', line)
        if m:
            last = m.group(1)
    return {"known_issues": issues, "last_assessed": last}


def source_quirk_candidates(source_id: str, known_issues: Sequence[str], last_assessed: str,
                            access_level: str = "internal") -> List[wm.CandidateSpec]:
    """One low-confidence ``quirk`` candidate per known issue, scoped to the source as a dataset."""
    if access_level not in ACCESS_RANK:
        raise ValueError(f"unknown access level {access_level!r}")
    return [wm.CandidateSpec(
        scope=f"dataset:{source_id}", type="quirk", statement=_check_statement(issue), confidence="low",
        pit_scope="<= decision date", evidence=({"source_run": f"source-catalog-{source_id}-{last_assessed}"},),
        target_catalog=f"_shared/datasets/{source_id}/provenance.yaml", access_level=access_level)
        for issue in known_issues]


def channel_lesson_candidate(channel_id: str, statement: str, source_run: str, kind: str = "pitfall",
                             confidence: str = "low", access_level: str = "internal") -> wm.CandidateSpec:
    if kind not in ("pitfall", "pattern"):
        raise ValueError("a channel lesson is a pitfall or a pattern")
    return wm.CandidateSpec(scope=f"channel:{channel_id}", type=kind, statement=_check_statement(statement),
                            confidence=confidence, pit_scope="<= decision date",
                            evidence=({"source_run": source_run},),
                            target_catalog="venture_intelligence/index.yaml", access_level=access_level)


def screening_decision_candidate(case_id: str, statement: str, source_run: str,
                                 confidence: str = "medium") -> wm.CandidateSpec:
    """A screening decision record. Always ``restricted``; the caller cannot lower it."""
    return wm.CandidateSpec(scope=f"case:{case_id}", type="decision", statement=_check_statement(statement),
                            confidence=confidence, pit_scope="<= decision date",
                            evidence=({"source_run": source_run},),
                            target_catalog="venture_intelligence/index.yaml", access_level="restricted")


def stage_to_local_store(specs: Sequence[wm.CandidateSpec], *, store_dir: Path, repo_root: Path,
                         workflow: str = "venture_intelligence", source_run: str) -> Path:
    """Stage candidates into ``<store_dir>/memory`` (the ``0049`` inbox). Promotes nothing.

    Refuses any ``store_dir`` that is not inside ``<repo_root>/knowledge_local/``, so a mistake cannot
    write private material into a committed directory.
    """
    local = (Path(repo_root) / LOCAL_ROOT).resolve()
    target = Path(store_dir).resolve()
    if local != target and local not in target.parents:
        raise ValueError(f"refusing to stage outside {LOCAL_ROOT}/: {target}")
    candidates = wm.propose_records(list(specs), workflow=workflow, source_run=source_run)
    return wm.stage_candidates(candidates, root=target / "memory")


# -------------------------------------------------------------------- retrieval
@dataclass(frozen=True)
class Document:
    doc_id: str
    source_id: str
    text: str
    access_level: str
    known_at: str                      # ISO date; the document counts only on or after it
    source_grade: str = "F6"           # letter then digit; F6 = cannot be judged
    language: str = "en"
    superseded_by: Optional[str] = None

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


def validate_documents(documents: Sequence[Document]) -> List[str]:
    """Corpus-owner checks, run over *every* document at load (never inside a caller's query)."""
    errors: List[str] = []
    seen = set()
    for d in documents:
        if d.doc_id in seen:
            errors.append(f"{d.doc_id}: duplicate doc_id")
        seen.add(d.doc_id)
        if d.access_level not in ACCESS_RANK:
            errors.append(f"{d.doc_id}: unknown access level {d.access_level!r}")
        if contains_secret(d.text):
            errors.append(f"{d.doc_id}: credential-shaped text; quarantine before indexing")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", d.known_at):
            errors.append(f"{d.doc_id}: known_at must be an ISO date")
    return errors


def _passages(doc: Document) -> List[Tuple[int, int, str]]:
    out: List[Tuple[int, int, str]] = []
    pos = 0
    for block in re.split(r"\n\s*\n", doc.text):
        start = doc.text.find(block, pos)
        if start < 0:
            continue
        pos = start + len(block)
        stripped = block.strip()
        if not stripped:
            continue
        lead = len(block) - len(block.lstrip())
        out.append((start + lead, start + lead + len(stripped), stripped))
    return out


def _terms(text: str) -> List[str]:
    return [t["text"].casefold() for t in segment(text)["tokens"]]


def retrieve(query: str, documents: Sequence[Document], caller_clearance: Optional[str], as_of: str,
             k: int = 3, min_score: float = 0.0) -> Dict[str, Any]:
    """Cited passages for ``query``. Order of operations is the contract:

    1. ``caller_clearance`` is required (``PermissionError`` if absent or unknown);
    2. documents above the caller's clearance, not yet known at ``as_of``, or superseded are dropped;
    3. ranking (BM25) uses statistics from the *eligible* passages only, so a restricted document
       cannot change what a lower-clearance caller sees, not even a score;
    4. the response never mentions dropped documents, and "nothing eligible matched" is the same
       ``not_found`` whether the document was absent, future-dated, or restricted.
    """
    if caller_clearance not in ACCESS_RANK:
        raise PermissionError("caller_clearance is required and must be one of: " + ", ".join(ACCESS_LEVELS))
    if k < 1:
        raise ValueError("k must be at least 1")
    q_terms = _terms(query)
    eligible = [d for d in documents
                if clearance_allows(d.access_level, caller_clearance) and d.known_at <= as_of
                and d.superseded_by is None and not contains_secret(d.text)]
    passages: List[Tuple[Document, int, int, str, List[str]]] = []
    for d in eligible:
        for start, end, text in _passages(d):
            passages.append((d, start, end, text, _terms(text)))
    base = {"as_of": as_of, "caller_clearance": caller_clearance, "tokenizer": segment("")["tokenizer"]}
    if not passages or not q_terms:
        return {**base, "status": "not_found", "reason": "no_passage_above_threshold", "passages": []}
    n = len(passages)
    avg_len = sum(len(p[4]) for p in passages) / n
    df: Dict[str, int] = {}
    for p in passages:
        for term in set(p[4]):
            df[term] = df.get(term, 0) + 1
    scored = []
    for d, start, end, text, terms in passages:
        score = 0.0
        for term in set(q_terms):
            f = terms.count(term)
            if not f:
                continue
            idf = math.log(1.0 + (n - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * f * (BM25_K1 + 1) / (f + BM25_K1 * (1 - BM25_B + BM25_B * len(terms) / avg_len))
        if score > min_score:
            scored.append((score, d, start, end, text))
    scored.sort(key=lambda x: (-x[0], x[1].doc_id, x[2]))
    top = scored[:k]
    if not top:
        return {**base, "status": "not_found", "reason": "no_passage_above_threshold", "passages": []}
    return {**base, "status": "ok", "reason": None, "passages": [
        {"citation_id": f"{d.doc_id}:{start}-{end}", "doc_id": d.doc_id, "source_id": d.source_id, "start": start,
         "end": end, "text": text, "score": round(score, 6), "content_hash": d.content_hash,
         "passage_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(), "access_level": d.access_level,
         "known_at": d.known_at, "source_grade": d.source_grade, "language": d.language}
        for score, d, start, end, text in top]}


REQUIRED_PASSAGE_FIELDS = ("citation_id", "doc_id", "source_id", "start", "end", "text", "content_hash",
                           "access_level", "known_at", "source_grade")


def retrieval_contract_violations(result: Mapping[str, Any], caller_clearance: str, as_of: str) -> List[str]:
    """Check any retriever's output (including the future ``0054`` server) against the contract."""
    errors: List[str] = []
    if result.get("status") not in ("ok", "not_found"):
        errors.append("status must be ok or not_found")
    passages = result.get("passages") or []
    if result.get("status") == "not_found" and passages:
        errors.append("not_found must carry no passages")
    if result.get("status") == "ok" and not passages:
        errors.append("ok must carry at least one passage")
    for p in passages:
        for f in REQUIRED_PASSAGE_FIELDS:
            if f not in p:
                errors.append(f"passage missing {f}")
        if p.get("access_level") not in ACCESS_RANK or not clearance_allows(p.get("access_level", "restricted"),
                                                                              caller_clearance):
            errors.append(f"passage {p.get('citation_id')} exceeds caller clearance")
        if str(p.get("known_at", "9999")) > as_of:
            errors.append(f"passage {p.get('citation_id')} was not known at {as_of}")
        if not (isinstance(p.get("start"), int) and isinstance(p.get("end"), int) and 0 <= p["start"] < p["end"]):
            errors.append(f"passage {p.get('citation_id')} has invalid offsets")
        if p.get("citation_id") != f"{p.get('doc_id')}:{p.get('start')}-{p.get('end')}":
            errors.append(f"passage {p.get('citation_id')} citation_id does not match doc and offsets")
    for forbidden in ("filtered", "withheld", "restricted_count", "hidden"):
        if forbidden in result:
            errors.append(f"response must not mention dropped documents ({forbidden})")
    return errors
