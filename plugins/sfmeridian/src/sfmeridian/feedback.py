"""Reviewed feedback inbox: propose, list, promote, discard.

Spec ``0114`` REQ-008 (realizing ``0113`` REQ-014; the ``0049`` pattern).
A candidate — a corrected or new query, usually from an accepted answer or a
user correction — is a JSON file under ``<inbox>/candidates/``. It is
invisible to search until a configured promoter, who is not its proposer,
promotes it into ``<inbox>/promoted/``; the next index run then serves it with
``feedback`` provenance. Every file is plain JSON so a pull request can carry
a promotion and its review.

People are named by pseudonymous handles, never email addresses.
"""

from __future__ import annotations

import builtins
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

__all__ = ["FeedbackError", "Inbox"]

_HANDLE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
KINDS = ("exemplar", "correction")
PAYLOAD_KEYS = ("query_id", "title", "intent", "sql", "dialect", "profile", "params", "tables",
                "pit_columns", "grain", "tags", "concepts", "viewpoint", "corrects", "note")


class FeedbackError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _handle(value: Any, role: str) -> str:
    if not isinstance(value, str) or "@" in value or not _HANDLE_RE.match(value):
        raise FeedbackError("E_FEEDBACK_HANDLE", f"{role} must be a pseudonymous handle, not {value!r}")
    return value


def _date(value: Any, role: str) -> str:
    if not isinstance(value, str) or not _DATE_RE.match(value):
        raise FeedbackError("E_FEEDBACK_INVALID", f"{role} must be an ISO date YYYY-MM-DD")
    return value


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class Inbox:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    @property
    def candidates_dir(self) -> Path:
        return self.root / "candidates"

    @property
    def promoted_dir(self) -> Path:
        return self.root / "promoted"

    def _write(self, path: Path, record: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, sort_keys=True, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    def _read(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def propose(self, *, kind: str, payload: Mapping[str, Any], proposer: str, proposed_on: str,
                source_run_id: str | None = None) -> dict[str, Any]:
        """Stage a candidate; return its record. Idempotent for identical payloads."""
        if kind not in KINDS:
            raise FeedbackError("E_FEEDBACK_INVALID", f"kind must be one of {', '.join(KINDS)}")
        unknown = set(payload) - set(PAYLOAD_KEYS)
        if unknown:
            raise FeedbackError("E_FEEDBACK_INVALID", f"unknown payload keys {sorted(unknown)}")
        for key in ("title", "intent", "sql"):
            if not isinstance(payload.get(key), str) or not payload[key].strip():
                raise FeedbackError("E_FEEDBACK_INVALID", f"payload needs {key!r}")
        if kind == "correction" and not payload.get("corrects"):
            raise FeedbackError("E_FEEDBACK_INVALID", "a correction names the exemplar or query it corrects")
        record = {
            "kind": kind, "payload": dict(payload), "proposer": _handle(proposer, "proposer"),
            "proposed_on": _date(proposed_on, "proposed_on"), "source_run_id": source_run_id,
        }
        candidate_id = hashlib.sha256(_canonical({"kind": kind, "payload": record["payload"]}).encode()).hexdigest()[:16]
        path = self.candidates_dir / f"{candidate_id}.json"
        if path.exists():
            return self._read(path)
        record.update({"candidate_id": candidate_id, "status": "staged"})
        self._write(path, record)
        return record

    def list(self, status: str | None = None) -> builtins.list[dict[str, Any]]:
        if not self.candidates_dir.exists():
            return []
        records = [self._read(p) for p in sorted(self.candidates_dir.glob("*.json"))]
        return [r for r in records if status is None or r["status"] == status]

    def promoted(self) -> builtins.list[dict[str, Any]]:
        if not self.promoted_dir.exists():
            return []
        return [self._read(p) for p in sorted(self.promoted_dir.glob("*.json"))]

    def _get(self, candidate_id: str) -> dict[str, Any]:
        if not re.fullmatch(r"[0-9a-f]{16}", candidate_id or ""):
            raise FeedbackError("E_FEEDBACK_NOT_FOUND", f"malformed candidate id {candidate_id!r}")
        path = self.candidates_dir / f"{candidate_id}.json"
        if not path.exists():
            raise FeedbackError("E_FEEDBACK_NOT_FOUND", f"no candidate {candidate_id}")
        return self._read(path)

    def promote(self, candidate_id: str, *, promoter: str, promoters: Sequence[str], promoted_on: str,
                note: str | None = None) -> dict[str, Any]:
        """Promote a staged candidate; only a configured promoter who is not the proposer may."""
        record = self._get(candidate_id)
        promoter = _handle(promoter, "promoter")
        if record["status"] != "staged":
            raise FeedbackError("E_FEEDBACK_STATE", f"candidate is {record['status']}, not staged")
        if promoter not in promoters:
            raise FeedbackError("E_FEEDBACK_NOT_PROMOTER", f"{promoter} is not a configured promoter")
        if promoter == record["proposer"]:
            raise FeedbackError("E_FEEDBACK_SELF_PROMOTION", "a candidate needs a promoter other than its proposer")
        record.update({"status": "promoted", "promoted_by": promoter,
                       "promoted_on": _date(promoted_on, "promoted_on"), "promotion_note": note})
        self._write(self.promoted_dir / f"{candidate_id}.json", record)
        self._write(self.candidates_dir / f"{candidate_id}.json", record)
        return record

    def discard(self, candidate_id: str, *, by: str, reason: str, discarded_on: str) -> dict[str, Any]:
        record = self._get(candidate_id)
        if record["status"] != "staged":
            raise FeedbackError("E_FEEDBACK_STATE", f"candidate is {record['status']}, not staged")
        if not reason.strip():
            raise FeedbackError("E_FEEDBACK_INVALID", "discarding needs a reason")
        record.update({"status": "discarded", "discarded_by": _handle(by, "by"),
                       "discarded_on": _date(discarded_on, "discarded_on"), "discard_reason": reason})
        self._write(self.candidates_dir / f"{candidate_id}.json", record)
        return record
