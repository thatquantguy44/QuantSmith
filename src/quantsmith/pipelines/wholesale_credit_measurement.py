"""Wholesale credit measurement and counterparty limit review for spec 0073.

Closes gap `G-0072-002` in `0072`'s gap register: PD/LGD/EAD measurement and
counterparty exposure/limit/concentration existed only as conventions and
golden cases, not as a runnable pipeline. This module is that pipeline.

Two capabilities, two different runtime boundaries — stated once here rather
than left implicit, because `0072`'s own workflow contracts already draw this
line and this module must not blur it:

- ``capability.wholesale_measurement`` (obligor/facility rating, PD/LGD/EAD)
  is `0072` REQ-013's ``adopter_plugin_via_0026`` for the rating/PD *model*
  itself — no SDK-shipped model assigns a rating or estimates a PD here, and
  none ever should without an approved spec of its own. What this module
  provides is the **measurement** half the capability actually claims: given
  an already-known PD, LGD, and risk weight (supplied by the caller, a
  plugin, or a rating agency feed — this module does not care which),
  compute expected loss, exposure at default from a credit conversion
  factor, and risk-weighted assets, with the same basis-compatibility
  checking `0072`'s validator already enforces on its golden cases.
- ``capability.counterparty_limits`` (exposure aggregation, limits,
  concentration) is a genuine ``in_sdk_reference_runtime`` — no institution-
  specific model is needed to aggregate exposure, compare it to a limit, or
  compute a concentration index, so this module implements it fully.

Every arithmetic primitive (`expected_loss`, `ead_from_ccf`,
`rwa_from_risk_weight`, `basis_compatible`, `migration_matrix_rows`) is
imported from `credit_risk_knowledge`, not reimplemented — the golden cases
that pin those functions are this module's own acceptance evidence, not a
separate claim to prove twice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Sequence

from .credit_risk_knowledge import (
    basis_compatible,
    ead_from_ccf,
    expected_loss,
    migration_matrix_rows,
    rwa_from_risk_weight,
)


class WholesaleMeasurementError(ValueError):
    """Raised when a wholesale measurement or limit input is malformed."""


@dataclass(frozen=True)
class FacilityInput:
    """One facility's inputs. PD, LGD, and risk weight are always supplied,
    never modeled here -- see the module docstring's runtime-boundary note."""

    facility_id: str
    obligor_id: str
    counterparty_id: str
    pd: Mapping[str, Any]
    lgd: Mapping[str, Any]
    currency: str = "USD"
    drawn_balance: float | None = None
    limit: float | None = None
    ccf: float | None = None
    ead_override: float | None = None
    risk_weight: float | None = None


@dataclass(frozen=True)
class FacilityMeasurement:
    """EL/EAD/RWA for one facility. `expected_loss` is None, with
    `violated_rules` populated, when the supplied PD and LGD are on
    incompatible bases -- the same rejection `0072`'s golden case
    `golden.el.basis_mismatch_rejected` pins, now reachable from real input."""

    facility_id: str
    obligor_id: str
    counterparty_id: str
    ead: float
    expected_loss: float | None
    rwa: float | None
    violated_rules: tuple[str, ...]
    currency: str


@dataclass(frozen=True)
class CounterpartyExposure:
    counterparty_id: str
    total_ead: float
    total_expected_loss: float
    facility_ids: tuple[str, ...]
    facilities_with_basis_violation: tuple[str, ...]


@dataclass(frozen=True)
class LimitCheckResult:
    counterparty_id: str
    exposure: float
    limit: float
    utilization: float
    status: str
    breach_amount: float


@dataclass(frozen=True)
class ConcentrationReport:
    total_portfolio_ead: float
    largest_counterparty_id: str
    largest_counterparty_share: float
    herfindahl_index: float
    concentration_threshold: float
    threshold_breached: bool


@dataclass(frozen=True)
class CounterpartyLimitReviewReport:
    facility_measurements: tuple[FacilityMeasurement, ...]
    exposures: tuple[CounterpartyExposure, ...]
    limit_checks: tuple[LimitCheckResult, ...]
    concentration: ConcentrationReport
    breached_counterparty_ids: tuple[str, ...]


def measure_facility(facility: FacilityInput) -> FacilityMeasurement:
    """Compute EAD, expected loss, and RWA for one facility.

    EAD comes from ``ead_override`` if supplied, else from
    ``drawn_balance``/``limit``/``ccf``. Exactly one path must be available --
    silently defaulting a missing EAD input would be the "unexplained global
    constant" failure `0072`'s AC-010 already tests against, applied to a
    runtime instead of a convention record.
    """

    if facility.ead_override is not None:
        ead = facility.ead_override
    elif None not in (facility.drawn_balance, facility.limit, facility.ccf):
        ead = ead_from_ccf(facility.drawn_balance, facility.limit, facility.ccf)  # type: ignore[arg-type]
    else:
        raise WholesaleMeasurementError(
            f"{facility.facility_id}: supply either ead_override or all of "
            "drawn_balance/limit/ccf -- EAD has no default"
        )

    violated = basis_compatible(facility.pd, facility.lgd)
    el = None if violated else expected_loss(facility.pd["value"], facility.lgd["value"], ead)
    rwa = None if facility.risk_weight is None else rwa_from_risk_weight(facility.risk_weight, ead)

    return FacilityMeasurement(
        facility_id=facility.facility_id,
        obligor_id=facility.obligor_id,
        counterparty_id=facility.counterparty_id,
        ead=ead,
        expected_loss=el,
        rwa=rwa,
        violated_rules=tuple(violated),
        currency=facility.currency,
    )


def aggregate_counterparty_exposure(
    measurements: Sequence[FacilityMeasurement],
) -> tuple[CounterpartyExposure, ...]:
    """Aggregate facility-level measurements by counterparty.

    A facility whose EL could not be computed (basis violation) contributes
    its EAD to the total but is named in `facilities_with_basis_violation`
    rather than silently treated as zero expected loss -- a missing EL is a
    known unknown, not a computed fact.
    """

    by_counterparty: Dict[str, list[FacilityMeasurement]] = {}
    for m in measurements:
        by_counterparty.setdefault(m.counterparty_id, []).append(m)

    exposures = []
    for counterparty_id, facility_measurements in by_counterparty.items():
        total_ead = sum(m.ead for m in facility_measurements)
        total_el = sum(m.expected_loss for m in facility_measurements if m.expected_loss is not None)
        violations = tuple(m.facility_id for m in facility_measurements if m.violated_rules)
        exposures.append(
            CounterpartyExposure(
                counterparty_id=counterparty_id,
                total_ead=total_ead,
                total_expected_loss=total_el,
                facility_ids=tuple(m.facility_id for m in facility_measurements),
                facilities_with_basis_violation=violations,
            )
        )
    return tuple(exposures)


def check_counterparty_limits(
    exposures: Sequence[CounterpartyExposure], limits: Mapping[str, float]
) -> tuple[LimitCheckResult, ...]:
    """Compare aggregated exposure to a supplied limit registry.

    A counterparty with exposure but no registered limit raises rather than
    passing silently -- an unregistered limit is not the same as "no limit",
    and treating it as such would hide exactly the concentration this
    function exists to surface.
    """

    results = []
    for exposure in exposures:
        if exposure.counterparty_id not in limits:
            raise WholesaleMeasurementError(
                f"{exposure.counterparty_id}: has exposure but no registered limit; "
                "supply one rather than letting it pass unchecked"
            )
        limit = limits[exposure.counterparty_id]
        utilization = exposure.total_ead / limit if limit else float("inf")
        breach_amount = max(0.0, exposure.total_ead - limit)
        results.append(
            LimitCheckResult(
                counterparty_id=exposure.counterparty_id,
                exposure=exposure.total_ead,
                limit=limit,
                utilization=utilization,
                status="breached" if breach_amount > 0 else "within_limit",
                breach_amount=breach_amount,
            )
        )
    return tuple(results)


def compute_concentration(
    exposures: Sequence[CounterpartyExposure], concentration_threshold: float
) -> ConcentrationReport:
    """Herfindahl-style concentration across counterparties.

    ``concentration_threshold`` is a required argument, not a default this
    module supplies -- the same pattern `0072`'s own conventions use for the
    IRB risk weight and the disparity threshold: a policy-specific number is
    an input the caller must state, never an SDK constant.
    """

    if not exposures:
        raise WholesaleMeasurementError("compute_concentration requires at least one exposure")

    total = sum(e.total_ead for e in exposures)
    if total <= 0:
        raise WholesaleMeasurementError("total portfolio EAD must be positive")

    shares = {e.counterparty_id: e.total_ead / total for e in exposures}
    largest_id = max(shares, key=lambda cid: shares[cid])
    hhi = sum(share ** 2 for share in shares.values())

    return ConcentrationReport(
        total_portfolio_ead=total,
        largest_counterparty_id=largest_id,
        largest_counterparty_share=shares[largest_id],
        herfindahl_index=hhi,
        concentration_threshold=concentration_threshold,
        threshold_breached=shares[largest_id] > concentration_threshold,
    )


def grade_transition_probabilities(
    migration_matrix_record: Mapping[str, Any], from_grade: str
) -> Dict[str, float]:
    """Return one row of a validated migration matrix as a grade->probability map.

    Validates row-stochasticity via `credit_risk_knowledge.migration_matrix_rows`
    before returning anything -- a matrix that fails that check is a defect to
    surface, not a row to hand back anyway.
    """

    grades = migration_matrix_record["grades"]
    matrix = migration_matrix_record["matrix"]
    absorbing = migration_matrix_record.get("absorbing_state")
    result = migration_matrix_rows(grades, matrix, absorbing)
    if not result["rows_stochastic"]:
        raise WholesaleMeasurementError("migration matrix rows are not stochastic; refusing to use it")
    if from_grade not in grades:
        raise WholesaleMeasurementError(f"unknown starting grade {from_grade!r}")
    row = matrix[grades.index(from_grade)]
    return dict(zip(grades, row))


def run_counterparty_limit_review(
    facilities: Sequence[FacilityInput],
    limits: Mapping[str, float],
    concentration_threshold: float,
) -> CounterpartyLimitReviewReport:
    """The counterparty limit and concentration review workflow, end to end.

    This is `0072`'s `workflow.counterparty_limit_review` as a real,
    deterministic function: measure each facility, aggregate by
    counterparty, check limits, and compute concentration -- all in-SDK
    reference runtime, no adopter plugin required.
    """

    measurements = tuple(measure_facility(f) for f in facilities)
    exposures = aggregate_counterparty_exposure(measurements)
    limit_checks = check_counterparty_limits(exposures, limits)
    concentration = compute_concentration(exposures, concentration_threshold)
    breached = tuple(lc.counterparty_id for lc in limit_checks if lc.status == "breached")

    return CounterpartyLimitReviewReport(
        facility_measurements=measurements,
        exposures=exposures,
        limit_checks=limit_checks,
        concentration=concentration,
        breached_counterparty_ids=breached,
    )
