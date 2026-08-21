"""Natural-language query seam for the Knowledge Console.

Spec ``0057-knowledge-console`` (T-007, REQ-008, REQ-009, NFR-006). This module
is the *pluggable point* the user asked for: a stable query contract, a grounded
keyword engine that ships today, and a registration hook so a real LLM engine
can take over later **without changing any caller**.

Grounding is the contract, not a nicety (``instructions/knowledge_base.md``):
every answer carries citations to real record ids, and a question that matches
nothing returns an empty citation list and says so — it never invents a record
id (spec NFR-006, AC-011). A future LLM engine inherits this contract: it
receives records already loaded (and, in a later access-aware world, already
filtered) by the caller, so it can never widen access, and it must cite ids
drawn from those records.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Protocol, Sequence, runtime_checkable

from quantsmith.pipelines import workflow_memory as wm

_WORD_RE = re.compile(r"[a-z0-9]+")

# Very common words carry no discriminating signal; dropping them keeps a
# question like "why not use adjusted close" from matching on "use"/"not".
_STOPWORDS = frozenset("""
a an and are as at be but by for from how in into is it its no not of on or
that the their then there these this to use used using was what when where
which who why with you your do does can could should would we our
""".split())


@dataclass(frozen=True)
class Answer:
    """A grounded answer: prose plus the record ids it stands on.

    ``citations`` reference only ids present in the records the engine was given
    (spec NFR-006). ``matched`` is ``False`` — and ``citations`` empty — when
    nothing in the store was relevant, which is a valid, required answer.
    """

    answer: str
    citations: List[str] = field(default_factory=list)
    mode: str = "keyword"
    matched: bool = False

    def to_dict(self) -> Dict:
        return {
            "answer": self.answer,
            "citations": list(self.citations),
            "mode": self.mode,
            "matched": self.matched,
        }


@runtime_checkable
class QueryEngine(Protocol):
    """The contract a natural-language backend implements.

    ``answer`` receives the question and the records to answer *from* (already
    loaded by the caller), and returns an :class:`Answer`. ``name`` identifies
    the engine in the response ``mode`` (e.g. ``keyword`` or ``llm:<vendor>``).
    """

    @property
    def name(self) -> str:  # pragma: no cover - trivial
        ...

    def answer(self, question: str, records: Sequence[wm.Record],
               k: int = 5) -> Answer:
        ...


def _tokens(text: str) -> List[str]:
    return [t for t in _WORD_RE.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1]


class KeywordQueryEngine:
    """Grounded term-overlap search — the default engine (spec REQ-009).

    Ranks records by how many distinct question terms appear in their
    ``statement``/``scope``/``type``, breaking ties by ``0048``'s ``rank_key``
    (confidence, corroboration, recency) so the most trustworthy record wins a
    tie. Returns the top-``k`` as citations. Zero overlap ⇒ an explicit
    "nothing matched" answer with no citations (NFR-006, AC-011).

    Deterministic: the same question over the same records always yields the same
    answer and citation order.
    """

    name = "keyword"

    def answer(self, question: str, records: Sequence[wm.Record],
               k: int = 5) -> Answer:
        terms = set(_tokens(question))
        if not terms or not records:
            return Answer(
                answer="Nothing in the store matched that question.",
                citations=[], mode=self.name, matched=False,
            )

        scored = []
        for r in records:
            haystack = set(_tokens(f"{r.statement} {r.scope} {r.type}"))
            overlap = terms & haystack
            if overlap:
                scored.append((len(overlap), r))

        if not scored:
            return Answer(
                answer=("Nothing in the store matched that question. The store "
                        "holds no record touching those terms — treat that as "
                        "\"not found\", not as \"no\"."),
                citations=[], mode=self.name, matched=False,
            )

        # Overlap desc, then 0048 rank order (a total order, so deterministic).
        scored.sort(key=lambda pair: (-pair[0], wm.rank_key(pair[1])))
        top = [r for _, r in scored[:max(1, k)]]
        citations = [r.id for r in top]

        lead = top[0]
        body = "; ".join(
            f"[{r.id}] {r.statement} (confidence {r.confidence}, "
            f"confirmed {r.last_confirmed.isoformat()})"
            for r in top
        )
        answer = (
            f"{len(scored)} record(s) in the store touch that question. "
            f"Most relevant: {body}. "
            f"Grounded in {len(citations)} record(s); see the cited ids for "
            f"provenance. (Leading record: {lead.id}.)"
        )
        return Answer(answer=answer, citations=citations, mode=self.name,
                      matched=True)


# --------------------------------------------------------------------------
# Engine resolution (the pluggable seam)
# --------------------------------------------------------------------------

_registered: Optional[QueryEngine] = None
_default = KeywordQueryEngine()


def register_engine(engine: Optional[QueryEngine]) -> None:
    """Register (or clear, with ``None``) the active query engine.

    A future LLM engine calls this once at startup to take over ``/api/query``.
    Everything else is unchanged: the server always calls ``resolve_engine()``.
    """
    global _registered
    if engine is not None and not isinstance(engine, QueryEngine):
        raise TypeError("engine must implement the QueryEngine protocol "
                        "(a `name` property and an `answer(question, records, k)` method)")
    _registered = engine


def resolve_engine() -> QueryEngine:
    """Return the active engine: a registered one, else the keyword default.

    When nothing is registered, the keyword engine is returned and reports its
    mode as ``keyword`` (spec AC-012).
    """
    return _registered if _registered is not None else _default
