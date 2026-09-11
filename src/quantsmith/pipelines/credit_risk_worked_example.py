"""Cross-cutting worked example threading specs 0077, 0073, and 0074 together.

This is **not** a fifth credit-risk spec and does not consume a reserved
spec number. It adds no new capability, no new decision path, and no new
knowledge-pack record: every function it calls already exists, already has
its own acceptance tests, and already reuses `credit_risk_knowledge.py`'s
arithmetic. What was missing was a single narrative proving the three
runtimes compose into one coherent credit risk agent group rather than three
unrelated pipelines that happen to share a knowledge pack.

The story, in one reporting cycle for one fictional regional bank's credit
organization:

1. **Document intelligence (`0077`).** A credit analyst's memo on
   *Cascadia Fabricators, Inc.* — a synthetic wholesale obligor — is emitted
   as a real `0071` bundle and bridged through `0072`'s LLM evidence-
   admission boundary via `credit_document_intelligence.admit_bundle_result`.
   The memo's own fixture review promotes the result to `decision_input`
   (not merely `derived_evidence`) — the same promotion path
   `test_credit_document_intelligence.py` already proves against the
   committed `0077` example, exercised here against a second, distinct memo.
2. **Wholesale measurement (`0073`).** Cascadia's revolving facility, plus
   two peer counterparties in the same reporting cycle, are measured for
   EL/EAD/RWA and reviewed for counterparty-limit breach and portfolio
   concentration via `wholesale_credit_measurement.run_counterparty_limit_review`.
   The PD/LGD/risk-weight inputs are supplied here as illustrative credit-
   committee assumptions, consistent with — but never derived from — the
   memo's admitted observation that leverage improved; this module does not
   compute a rating or a PD from text, and never will (see `0073`'s own
   runtime-boundary note).
3. **Retail fairness testing (`0074`).** The same credit organization's
   *separate* retail underwriting book — a different consumer population,
   not Cascadia, which is a business obligor — is tested for adverse impact
   at its applied cutoff via `retail_fairness_harness.run_fairness_harness`,
   the exact function `decision_paths.json`'s `path.retail_underwriting_decision`
   names as its `disparate_impact_hook`.

Steps 2 and 3 are deliberately **not** the same borrower. `0072`'s own
knowledge pack draws that line: `path.wholesale_obligor_review` and
`path.counterparty_limit_review` are `consumer_decision: false` (an
institutional counterparty, no ECOA fairness obligation attaches), while
`path.retail_underwriting_decision` is `consumer_decision: true` and carries
the fairness-testing obligations. Fusing them into one person's story would
misstate what the pack itself certifies. The worked example instead shows
one governance program — the same admission boundary, the same measurement
discipline, the same honest "no model ships" boundary — operating correctly
across both sides of the book in the same cycle.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

from quantsmith.text_intelligence import TextDocumentInput

from .credit_document_intelligence import admit_bundle_result, emit_credit_document_evidence
from .retail_fairness_harness import FairnessHarnessReport, ScoredApplicant, run_fairness_harness
from .wholesale_credit_measurement import (
    CounterpartyLimitReviewReport,
    FacilityInput,
    run_counterparty_limit_review,
)


class WorkedExampleError(ValueError):
    """Raised when the worked example's own inputs are malformed."""


OBLIGOR_ID = "obligor.cascadia-fabricators"
CASCADIA_COUNTERPARTY_ID = "counterparty.cascadia-fabricators"
NORTHFIELD_COUNTERPARTY_ID = "counterparty.northfield-mills"
BLUE_HARBOR_COUNTERPARTY_ID = "counterparty.blue-harbor-forge"

# Same default definition/horizon basis throughout -- basis_compatible would
# reject a mismatched pairing, and this module has no reason to invite one.
_PD_BASIS = {"horizon": "P1Y", "default_definition_id": "defn.default.irb_reference"}
_LGD_BASIS = {"horizon": "workout_period", "default_definition_id": "defn.default.irb_reference"}


@dataclass(frozen=True)
class DocumentIntelligenceStep:
    """Step 1 output: a real 0077 bundle bridged through 0072's admission gate."""

    bundle_dir: Path
    admission: Dict[str, Any]


@dataclass(frozen=True)
class WorkedExampleReport:
    narrative: str
    document_intelligence: DocumentIntelligenceStep
    wholesale_measurement: CounterpartyLimitReviewReport
    retail_fairness: FairnessHarnessReport


def run_document_intelligence_step(root: str | Path) -> DocumentIntelligenceStep:
    """0077: emit and admit Cascadia's credit memo evidence.

    A second, Cascadia-specific memo pair -- not a reuse of the committed
    `0077` example -- so this step is genuinely about *this* obligor rather
    than borrowing someone else's admitted evidence.
    """

    documents = (
        TextDocumentInput(
            document_id="credit-memo-cascadia-001",
            text=(
                "Cascadia Fabricators, Inc.'s total leverage ratio improved this "
                "quarter as EBITDA grew faster than debt service, and the "
                "Borrower maintained ample liquidity headroom under its "
                "revolving credit facility."
            ),
            source_id="credit_document_fixture",
            # Well before the run's decision cutoff (started_at + a few
            # seconds), matching 0077's own committed-example convention: a
            # document must be knowable before the run, not merely before
            # "now".
            publication_time="2026-09-09T09:00:00Z",
            observation_time="2026-09-09T09:00:05Z",
            ingestion_time="2026-09-09T09:01:00Z",
            split="backtest",
        ),
        TextDocumentInput(
            document_id="credit-memo-cascadia-002",
            text=(
                "Per the credit agreement, Cascadia Fabricators, Inc. shall "
                "maintain a maximum total leverage ratio; management notes "
                "covenant headroom remains stable this period."
            ),
            source_id="credit_document_fixture",
            publication_time="2026-09-09T09:02:00Z",
            observation_time="2026-09-09T09:02:05Z",
            ingestion_time="2026-09-09T09:03:00Z",
            split="backtest",
        ),
    )
    bundle_dir = emit_credit_document_evidence(
        documents,
        Path(root) / "document_intelligence",
        run_id="credit-risk-worked-example-cascadia",
        started_at="2026-09-11T09:00:00Z",
    )
    admission = admit_bundle_result(bundle_dir)
    return DocumentIntelligenceStep(bundle_dir=bundle_dir, admission=admission)


def run_wholesale_measurement_step() -> CounterpartyLimitReviewReport:
    """0073: measure Cascadia's facility alongside two peer counterparties.

    Three counterparties, not one, so the limit check and concentration
    index have something real to compare Cascadia against -- a single-name
    portfolio makes both checks trivially true and proves nothing.
    """

    facilities = (
        FacilityInput(
            facility_id="facility.cascadia-revolver-001",
            obligor_id=OBLIGOR_ID,
            counterparty_id=CASCADIA_COUNTERPARTY_ID,
            # A slightly better PD than the peers -- an illustrative
            # credit-committee assumption consistent with the admitted
            # memo's observation that leverage improved, never computed
            # from it: see the module docstring's runtime-boundary note.
            pd={"value": 0.015, **_PD_BASIS},
            lgd={"value": 0.40, **_LGD_BASIS},
            drawn_balance=3_000_000.0,
            limit=5_000_000.0,
            ccf=0.5,
            risk_weight=0.75,
        ),
        FacilityInput(
            facility_id="facility.northfield-term-001",
            obligor_id="obligor.northfield-mills",
            counterparty_id=NORTHFIELD_COUNTERPARTY_ID,
            pd={"value": 0.02, **_PD_BASIS},
            lgd={"value": 0.45, **_LGD_BASIS},
            ead_override=2_500_000.0,
            risk_weight=1.0,
        ),
        FacilityInput(
            facility_id="facility.blue-harbor-term-001",
            obligor_id="obligor.blue-harbor-forge",
            counterparty_id=BLUE_HARBOR_COUNTERPARTY_ID,
            pd={"value": 0.02, **_PD_BASIS},
            lgd={"value": 0.45, **_LGD_BASIS},
            ead_override=1_500_000.0,
            risk_weight=1.0,
        ),
    )
    limits = {
        CASCADIA_COUNTERPARTY_ID: 5_000_000.0,
        # Below Northfield's own EAD on purpose, so the review demonstrates
        # a real breach rather than every counterparty passing quietly.
        NORTHFIELD_COUNTERPARTY_ID: 2_000_000.0,
        BLUE_HARBOR_COUNTERPARTY_ID: 2_000_000.0,
    }
    return run_counterparty_limit_review(facilities, limits, concentration_threshold=0.4)


def _retail_book_population(n: int = 150, seed: int = 2026) -> List[ScoredApplicant]:
    """A synthetic retail underwriting population for the same reporting
    cycle -- a different, consumer book, not Cascadia. See the module
    docstring for why these stay two separate populations.

    Gaussian score/feature generation, same pattern `0074`'s own acceptance
    tests use (`_population` in `tests/test_retail_fairness_harness.py`),
    seeded here for a deterministic, reproducible committed example rather
    than the tests' own arbitrary seed.
    """

    rng = random.Random(seed)
    applicants: List[ScoredApplicant] = []
    for i in range(n):
        applicants.append(
            ScoredApplicant(
                applicant_id=f"retail-ref-{i}",
                score=rng.gauss(680, 45),
                protected_class_member=False,
                feature_values={"zip_income_proxy": rng.gauss(72000, 11000)},
            )
        )
    for i in range(n):
        applicants.append(
            ScoredApplicant(
                applicant_id=f"retail-prot-{i}",
                score=rng.gauss(635, 45),
                protected_class_member=True,
                feature_values={"zip_income_proxy": rng.gauss(52000, 11000)},
            )
        )
    return applicants


def run_retail_fairness_step() -> FairnessHarnessReport:
    """0074: disparate-impact testing on the retail book's applied cutoff --
    the real function `path.retail_underwriting_decision` in
    `decision_paths.json` names as its `disparate_impact_hook`."""

    applicants = _retail_book_population()
    return run_fairness_harness(
        applicants,
        cutoff=650,
        disparity_threshold=0.8,
        features=["zip_income_proxy"],
        candidate_cutoffs=[600, 610, 620, 630, 640, 650],
        max_approval_rate_delta=0.35,
    )


def _render_narrative(
    document_intelligence: DocumentIntelligenceStep,
    wholesale: CounterpartyLimitReviewReport,
    retail: FairnessHarnessReport,
) -> str:
    cascadia = next(
        m for m in wholesale.facility_measurements if m.counterparty_id == CASCADIA_COUNTERPARTY_ID
    )
    cascadia_limit = next(
        lc for lc in wholesale.limit_checks if lc.counterparty_id == CASCADIA_COUNTERPARTY_ID
    )
    lda = retail.less_discriminatory_alternative
    lda_line = (
        f"a less-discriminatory-alternative search recommended cutoff "
        f"{lda.recommended_cutoff}" if lda and lda.alternative_found
        else "the less-discriminatory-alternative search found no candidate within tolerance"
    )

    return f"""# Credit Risk Worked Example: Cascadia Fabricators, Inc.

A single reporting cycle threading three Approved, tested credit-risk
runtimes (`0077`, `0073`, `0074`) under the same `0072` governance program.
Every number below is computed by this module's real functions, not
hand-typed — see `report.json` for the full machine-readable output.

## 1. Document intelligence (spec `0077`)

Cascadia's credit memo was admitted through `0072`'s LLM evidence-admission boundary as `{document_intelligence.admission["evidence_class"]}` (admitted: {document_intelligence.admission["admitted"]}).

## 2. Wholesale measurement (spec `0073`)

Cascadia's revolving facility: EAD = {cascadia.ead:,.2f}, expected loss = {cascadia.expected_loss:,.2f}, RWA = {cascadia.rwa:,.2f}. Counterparty limit status: {cascadia_limit.status} (utilization {cascadia_limit.utilization:.1%}). Portfolio concentration: largest counterparty share {wholesale.concentration.largest_counterparty_share:.1%} (Herfindahl index {wholesale.concentration.herfindahl_index:.4f}), threshold breached: {wholesale.concentration.threshold_breached}. Breached counterparties: {list(wholesale.breached_counterparty_ids) or "none"}.

## 3. Retail fairness testing (spec `0074`)

A separate retail underwriting book (not Cascadia — see this module's docstring for why the two stay distinct) was tested at cutoff {retail.baseline.cutoff}: adverse impact ratio {retail.baseline.adverse_impact_ratio:.3f}, threshold breached: {retail.baseline.threshold_breached}. Where breached, {lda_line}.

## What this does not claim

No rating, PD/LGD estimate, or credit score is produced anywhere in this
module. Cascadia's PD/LGD/risk-weight are illustrative credit-committee
inputs, not a model output; the retail population's scores are synthetic
stand-ins for whatever an adopter's own underwriting model produces. See
`docs/credit_risk_worked_example_synthetic_data_disclosure.md`.
"""


def run_worked_example(root: str | Path) -> WorkedExampleReport:
    """Run all three steps and assemble the cross-cutting report."""

    document_intelligence = run_document_intelligence_step(root)
    wholesale = run_wholesale_measurement_step()
    retail = run_retail_fairness_step()
    narrative = _render_narrative(document_intelligence, wholesale, retail)
    return WorkedExampleReport(
        narrative=narrative,
        document_intelligence=document_intelligence,
        wholesale_measurement=wholesale,
        retail_fairness=retail,
    )


def _report_to_json(report: WorkedExampleReport) -> Dict[str, Any]:
    return {
        "document_intelligence": {
            "bundle_dir": str(report.document_intelligence.bundle_dir),
            "admission": report.document_intelligence.admission,
        },
        "wholesale_measurement": asdict(report.wholesale_measurement),
        "retail_fairness": asdict(report.retail_fairness),
    }


def generate_worked_example(root: str | Path) -> Path:
    """Regenerate the one committed cross-cutting example deterministically."""

    out_dir = Path(root) / "credit_risk_worked_example"
    out_dir.mkdir(parents=True, exist_ok=True)
    report = run_worked_example(out_dir)
    (out_dir / "report.json").write_text(
        json.dumps(_report_to_json(report), indent=2, sort_keys=True) + "\n"
    )
    (out_dir / "narrative.md").write_text(report.narrative)
    return out_dir
