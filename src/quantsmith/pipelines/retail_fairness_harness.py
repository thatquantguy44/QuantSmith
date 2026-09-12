"""Retail underwriting fairness harness for spec 0074.

Closes gap `G-0072-005` in `0072`'s gap register: `decision_paths.json`
declared `hook.disparate_impact.*` as a callable fairness test, but nothing
implemented it, and per-feature proxy association was required-and-declared
rather than measured. This module is that implementation.

**No scorecard ships here, deliberately.** `0072`'s own open question asked
whether `0074` should ship a reference scoring model; the answer, resolved
the same way `0073` resolved the analogous question for wholesale rating and
PD, is no. A shipped scorecard risks being mistaken for a validated,
ECOA-compliant model at the highest-stakes point in this whole domain — an
actual consumer credit decision. This module takes an already-scored
population as input (from an adopter's own model, registered however they
choose) and tests it: adverse impact at the applied cutoff, per-feature
proxy association with the protected-class basis, and a less-discriminatory-
alternative search over cutoffs when the disparity threshold is breached.

Protected-class membership is likewise always an input, never estimated
here. `0072`'s own conventions already scope BISG-style estimation as a
named, caller-declared method with recorded limitations
(`param.fairness.protected_class_estimation_method`); implementing an
estimator would be separate, real, and separately-validated work, not a
detail to fold into a fairness harness.

Every disparity computation reuses `credit_risk_knowledge.adverse_impact_
ratio` rather than reimplementing it -- this module adds group-counting at a
cutoff, proxy-association measurement, and the alternative-cutoff search,
which is exactly what `G-0072-005` named as missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .credit_risk_knowledge import adverse_impact_ratio


ALLOWED_PROTECTED_CLASS_BASES = ("observed", "estimated")


class FairnessHarnessError(ValueError):
    """Raised when a fairness harness input is malformed."""


@dataclass(frozen=True)
class ScoredApplicant:
    """One scored applicant. The score itself always comes from the
    adopter's own model -- this module never produces one."""

    applicant_id: str
    score: float
    protected_class_member: bool
    feature_values: Mapping[str, float]


@dataclass(frozen=True)
class DisparityResult:
    cutoff: float
    overall_approval_rate: float
    protected_approval_rate: float
    reference_approval_rate: float
    adverse_impact_ratio: float
    threshold_breached: bool


@dataclass(frozen=True)
class ProxyAssociationResult:
    feature: str
    correlation_with_protected_class: float


@dataclass(frozen=True)
class AlternativeCutoffCandidate:
    cutoff: float
    disparity: DisparityResult
    approval_rate_delta: float


@dataclass(frozen=True)
class LessDiscriminatoryAlternativeSearch:
    baseline_cutoff: float
    max_approval_rate_delta: float
    candidates: tuple[AlternativeCutoffCandidate, ...]
    recommended_cutoff: float | None
    alternative_found: bool


@dataclass(frozen=True)
class FairnessHarnessReport:
    protected_class_basis: str
    baseline: DisparityResult
    proxy_associations: tuple[ProxyAssociationResult, ...]
    less_discriminatory_alternative: LessDiscriminatoryAlternativeSearch | None


def _approved(applicant: ScoredApplicant, cutoff: float) -> bool:
    return applicant.score >= cutoff


def _group_counts_at_cutoff(
    applicants: Sequence[ScoredApplicant], cutoff: float
) -> tuple[float, float, float, float]:
    protected = [a for a in applicants if a.protected_class_member]
    reference = [a for a in applicants if not a.protected_class_member]
    if not protected or not reference:
        raise FairnessHarnessError(
            "population must include both a protected-class group and a reference "
            "group -- adverse impact is undefined with only one"
        )
    approved_protected = sum(1 for a in protected if _approved(a, cutoff))
    approved_reference = sum(1 for a in reference if _approved(a, cutoff))
    return approved_protected, len(protected), approved_reference, len(reference)


def measure_disparity(
    applicants: Sequence[ScoredApplicant], cutoff: float, disparity_threshold: float
) -> DisparityResult:
    """Adverse impact at one cutoff, reusing `adverse_impact_ratio` unchanged."""

    if not applicants:
        raise FairnessHarnessError("measure_disparity requires at least one applicant")
    approved_protected, total_protected, approved_reference, total_reference = (
        _group_counts_at_cutoff(applicants, cutoff)
    )
    result = adverse_impact_ratio(
        approved_protected, total_protected, approved_reference, total_reference,
        disparity_threshold,
    )
    total_approved = approved_protected + approved_reference
    overall_rate = total_approved / len(applicants)
    return DisparityResult(
        cutoff=cutoff,
        overall_approval_rate=overall_rate,
        protected_approval_rate=result["selection_rate_protected"],
        reference_approval_rate=result["selection_rate_reference"],
        adverse_impact_ratio=result["adverse_impact_ratio"],
        threshold_breached=result["threshold_breached"],
    )


def measure_proxy_association(
    applicants: Sequence[ScoredApplicant], feature: str
) -> ProxyAssociationResult:
    """Pearson correlation between one feature and protected-class membership.

    Mathematically equivalent to the point-biserial correlation coefficient
    when one variable is binary (0/1). Pure Python, no numpy dependency --
    the same standard-library-only constraint every other 0072/0073/0077
    module holds to.

    A feature with zero variance across the population raises rather than
    returning a meaningless 0.0 or NaN -- an unmeasurable association is a
    defect to surface, not a silent pass.
    """

    if len(applicants) < 2:
        raise FairnessHarnessError("proxy association requires at least two applicants")

    xs = [float(a.feature_values[feature]) for a in applicants]
    ys = [1.0 if a.protected_class_member else 0.0 for a in applicants]
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0:
        raise FairnessHarnessError(f"feature {feature!r} has zero variance; correlation is undefined")
    if var_y == 0:
        raise FairnessHarnessError("protected-class membership has zero variance in this population")

    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    correlation = cov / (var_x ** 0.5 * var_y ** 0.5)
    return ProxyAssociationResult(feature=feature, correlation_with_protected_class=correlation)


def search_less_discriminatory_alternative(
    applicants: Sequence[ScoredApplicant],
    baseline_cutoff: float,
    disparity_threshold: float,
    candidate_cutoffs: Sequence[float],
    max_approval_rate_delta: float,
) -> LessDiscriminatoryAlternativeSearch:
    """Search caller-supplied candidate cutoffs for one that clears the
    disparity threshold within a bounded change in overall approval rate.

    `candidate_cutoffs` and `max_approval_rate_delta` are always supplied by
    the caller -- generating a default sweep would be inventing a policy
    parameter this module has no standing to set. Among candidates that
    clear the threshold within the allowed approval-rate change, the one
    closest to the baseline cutoff is recommended: the smallest policy
    change that fixes the disparity, not the most aggressive one.
    """

    if not candidate_cutoffs:
        raise FairnessHarnessError("candidate_cutoffs must be non-empty")

    baseline = measure_disparity(applicants, baseline_cutoff, disparity_threshold)
    candidates = []
    for cutoff in candidate_cutoffs:
        disparity = measure_disparity(applicants, cutoff, disparity_threshold)
        delta = disparity.overall_approval_rate - baseline.overall_approval_rate
        candidates.append(AlternativeCutoffCandidate(cutoff=cutoff, disparity=disparity, approval_rate_delta=delta))

    eligible = [
        c for c in candidates
        if not c.disparity.threshold_breached and abs(c.approval_rate_delta) <= max_approval_rate_delta
    ]
    recommended = None
    if eligible:
        recommended = min(eligible, key=lambda c: abs(c.cutoff - baseline_cutoff)).cutoff

    return LessDiscriminatoryAlternativeSearch(
        baseline_cutoff=baseline_cutoff,
        max_approval_rate_delta=max_approval_rate_delta,
        candidates=tuple(candidates),
        recommended_cutoff=recommended,
        alternative_found=recommended is not None,
    )


def run_fairness_harness(
    applicants: Sequence[ScoredApplicant],
    cutoff: float,
    disparity_threshold: float,
    features: Sequence[str],
    protected_class_basis: str = "observed",
    candidate_cutoffs: Sequence[float] | None = None,
    max_approval_rate_delta: float = 0.0,
) -> FairnessHarnessReport:
    """The full harness: this is what `hook.disparate_impact.*` in
    `decision_paths.json` resolves to.

    The less-discriminatory-alternative search runs only when the baseline
    breaches the threshold -- matching `0072` REQ-020's own conditional
    ("required when disparity_threshold_breached") exactly, rather than
    running a search nothing needs.
    """

    if protected_class_basis not in ALLOWED_PROTECTED_CLASS_BASES:
        raise FairnessHarnessError(f"unknown protected_class_basis {protected_class_basis!r}")

    baseline = measure_disparity(applicants, cutoff, disparity_threshold)
    proxies = tuple(measure_proxy_association(applicants, f) for f in features)

    lda = None
    if baseline.threshold_breached:
        if not candidate_cutoffs:
            raise FairnessHarnessError(
                "baseline breaches the disparity threshold; candidate_cutoffs and "
                "max_approval_rate_delta are required to search for a less "
                "discriminatory alternative -- REQ-020 does not permit skipping this"
            )
        lda = search_less_discriminatory_alternative(
            applicants, cutoff, disparity_threshold, candidate_cutoffs, max_approval_rate_delta,
        )

    return FairnessHarnessReport(
        protected_class_basis=protected_class_basis,
        baseline=baseline,
        proxy_associations=proxies,
        less_discriminatory_alternative=lda,
    )
