"""Credit document intelligence for spec 0077.

Composes two already-built, already-approved foundations rather than
inventing a third: spec 0071's text-intelligence producer emits a real,
validated corpus/task-result/audit/envelope bundle over synthetic credit
documents, and this module bridges one of that bundle's task results into
spec 0072's LLM-evidence admission gate
(``quantsmith.pipelines.credit_risk_knowledge.admit_derived_evidence``).

What this module does NOT do, stated plainly (0077 non-goals):

- It does not parse a credit agreement or extract a real covenant number.
  The underlying 0071 producer's ``entity_extraction``/``value_extraction``/
  ``sentiment_stance``/``theme_detection`` outputs are fixed reference-fixture
  stubs, unchanged from 0071's own committed examples, carried over here for
  schema completeness. Only the ``classification`` result is computed from
  the actual document text (a lexical check for improving/unclear language).
  A working covenant-extraction model is future work, not this module.
- It does not call a model provider, plugin, or vector store. No network I/O
  occurs anywhere in this module.
- It never promotes a value to a decision input itself. Promotion requires a
  named human reviewer recorded on the task result; this module only proves
  the promotion gate opens and closes correctly against real artifacts.

The one genuinely new piece of engineering this module adds, beyond calling
the built producer, is the field-name adapter in
``review_from_task_result``: 0071's task-result ``review`` object
(``reviewer``, ``reviewed_at``, ``owner``, ...) and 0072's review object
(``reviewer``, ``review_date``, ``scope``) do not share field names. Wiring
the two systems together surfaced this; the adapter makes the mapping
explicit rather than silently coercing one shape into the other.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from quantsmith.orchestration import load_json
from quantsmith.text_intelligence import TextDocumentInput, emit_lexical_signal_evidence

from .credit_risk_knowledge import admit_derived_evidence, repository_root


class CreditDocumentIntelligenceError(ValueError):
    """Raised when a credit document bundle cannot be bridged to 0072."""


def emit_credit_document_evidence(
    documents: Sequence[TextDocumentInput],
    output_dir: str | Path,
    *,
    run_id: str = "credit-document-intelligence",
    actor_id: str = "credit_document_intelligence",
    actor_clearance: str = "internal",
    started_at: str = "2026-09-10T09:00:00Z",
    repo_revision: str = "fixture",
) -> Path:
    """Emit a real, validated 0071 bundle over synthetic credit documents.

    A thin, credit-domain-named call into 0071's unchanged, Approved producer.
    No 0071 internals are reimplemented or forked.
    """

    for document in documents:
        if document.source_id != "credit_document_fixture":
            raise CreditDocumentIntelligenceError(
                f"{document.document_id}: credit document intelligence documents "
                "must cite source_id 'credit_document_fixture', not "
                f"{document.source_id!r} — register a source rather than reusing "
                "0071's generic text_intelligence_fixture"
            )
    return emit_lexical_signal_evidence(
        documents,
        output_dir,
        run_id=run_id,
        actor_id=actor_id,
        actor_clearance=actor_clearance,
        started_at=started_at,
        repo_revision=repo_revision,
    )


def review_from_task_result(review: Mapping[str, Any]) -> Dict[str, Any]:
    """Adapt a 0071 task-result review object into 0072's review shape.

    0071: ``reviewer``, ``reviewed_at`` (timestamp), ``owner``, ``uncertainty``.
    0072: ``reviewer``, ``review_date`` (date), ``scope``.

    Neither field set is wrong; they were designed for different documents
    (a text-intelligence task result vs. a credit knowledge record) and
    happen to need the same three facts. This function is the seam between
    them, written once here rather than reimplemented ad hoc by every future
    caller that bridges the two specs.
    """

    reviewed_at = str(review.get("reviewed_at") or "")
    return {
        "reviewer": review.get("reviewer"),
        "review_date": reviewed_at[:10] if reviewed_at else None,
        "scope": f"{review.get('owner', 'unknown')}: {review.get('uncertainty', '')}".strip(": "),
    }


def _resolve_source_spans(
    corpus: Mapping[str, Any], evidence_span_ids: Sequence[str]
) -> list[dict[str, Any]]:
    spans_by_id = {span["span_id"]: span for span in corpus.get("spans", [])}
    resolved = []
    for span_id in evidence_span_ids:
        span = spans_by_id.get(span_id)
        if span is None:
            raise CreditDocumentIntelligenceError(
                f"evidence_span_id {span_id!r} does not resolve in the corpus snapshot"
            )
        resolved.append(
            {
                "span_id": span["span_id"],
                "document_id": span["document_id"],
                "start": span["start"],
                "end": span["end"],
            }
        )
    return resolved


def admission_input_from_bundle(
    bundle_dir: str | Path,
    *,
    result_task_type: str = "value_extraction",
    include_review: bool = True,
) -> Dict[str, Any]:
    """Build a 0072 admission-function input from a real emitted 0071 bundle.

    Loads the actual corpus, task results, and run envelope this module just
    emitted — nothing here is hand-typed to pass validation, unlike the
    illustrative fixtures in ``tests/test_credit_risk_knowledge.py``.

    ``bundle_dir`` accepts either the bundle directory or the
    ``text_intelligence_manifest.json`` path that
    ``emit_lexical_signal_evidence`` returns, normalized here so a caller
    does not need to remember which of the two 0071 hands back.
    """

    bundle = Path(bundle_dir)
    if bundle.is_file():
        bundle = bundle.parent
    corpus = load_json(bundle / "corpus_snapshot.json")
    task_results = load_json(bundle / "task_results.json")
    envelope = load_json(bundle / "run_envelope.json")

    result = next(
        (r for r in task_results["results"] if r["task_type"] == result_task_type), None
    )
    if result is None:
        raise CreditDocumentIntelligenceError(
            f"no task result with task_type {result_task_type!r} in {bundle}"
        )

    spans = _resolve_source_spans(corpus, result["evidence_span_ids"])
    assumption_path = bundle / "assumptions.jsonl"
    prompt_manifest_ref = envelope.get("prompt_manifest", {}).get("path")

    admission_input: Dict[str, Any] = {
        "artifact_ref": result["result_id"],
        "source_spans": spans,
        "envelope_ref": envelope["run_id"],
        "prompt_context_manifest": prompt_manifest_ref,
        "assumption_ledger_entry": (
            f"{assumption_path.name}#0" if assumption_path.exists() else None
        ),
        "replay_ref": envelope["replay"]["command"],
    }
    if include_review:
        admission_input["review"] = review_from_task_result(result["review"])
    return admission_input


def admit_bundle_result(
    bundle_dir: str | Path,
    governance: Mapping[str, Any] | None = None,
    *,
    result_task_type: str = "value_extraction",
    include_review: bool = True,
) -> Dict[str, Any]:
    """Run a real emitted bundle's task result through 0072's admission gate.

    Convenience wrapper composing ``admission_input_from_bundle`` with
    ``credit_risk_knowledge.admit_derived_evidence``, so a caller does not
    need to import from two different pipeline modules to prove the boundary
    end to end.
    """

    if governance is None:
        root = repository_root()
        governance = load_json(root / "knowledge" / "credit_risk" / "governance.json")
    admission_input = admission_input_from_bundle(
        bundle_dir, result_task_type=result_task_type, include_review=include_review
    )
    return admit_derived_evidence(admission_input, governance)


def generate_credit_document_examples(root: str | Path) -> Path:
    """Regenerate the one committed 0077 example deterministically."""

    root = Path(root)
    return emit_credit_document_evidence(
        (
            TextDocumentInput(
                document_id="credit-memo-obligor-001",
                text=(
                    "The Borrower's total leverage ratio declined this quarter as "
                    "EBITDA improved, and the Borrower maintained ample liquidity "
                    "headroom under its revolving credit facility."
                ),
                source_id="credit_document_fixture",
                # Well before started_at, matching 0071's own reference examples:
                # a document must be knowable before the run's decision cutoff
                # (started_at + a few seconds), not merely before "now".
                publication_time="2026-09-08T09:00:00Z",
                observation_time="2026-09-08T09:00:05Z",
                ingestion_time="2026-09-08T09:01:00Z",
                split="backtest",
            ),
            TextDocumentInput(
                document_id="credit-memo-covenant-001",
                text=(
                    "Per the credit agreement, the Borrower shall maintain a "
                    "maximum total leverage ratio; management notes covenant "
                    "headroom remains stable this period."
                ),
                source_id="credit_document_fixture",
                publication_time="2026-09-08T09:02:00Z",
                observation_time="2026-09-08T09:02:05Z",
                ingestion_time="2026-09-08T09:03:00Z",
                split="backtest",
            ),
        ),
        root / "credit_document_intelligence",
        run_id="credit-document-intelligence-001",
    )
