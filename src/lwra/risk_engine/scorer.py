"""Risk scoring orchestration and the public engine entry point.

Combines the well's static attributes and its :class:`IntegrityResult` into a
scalar 0-100 risk score, the likelihood/consequence pair behind the risk
matrix, the dominant risk drivers, and a fully auditable
:class:`~lwra.models.results.RiskResult`.

The public entry points are :func:`assess_risk` (result only) and
:func:`assess_risk_traced` (result plus the complete calculation trace). Both
are pure, deterministic functions of their inputs plus the cached, externalised
configuration; neither mutates its inputs.

Scoring pipeline
----------------
1. Extract a raw value per risk factor from ``WellData`` + ``IntegrityResult``
   (integrity is taken as the overall integrity score and inverted during
   normalisation; well age is derived from dates; data uncertainty is the
   fraction of key fields missing).
2. Normalise each factor to a 0-100 contribution (``weighting.normalise_factor``).
3. Scalar risk score = weighted sum using ``risk_factor_weights``.
4. Likelihood and consequence axes via the per-factor split.
5. Identify dominant drivers by weighted contribution to the scalar score.
6. Assign category and risk-matrix coordinates.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from lwra.config.enums import RiskFactor
from lwra.models.enums import FluidType
from lwra.models.results import IntegrityResult, RiskResult
from lwra.models.well import WellData
from lwra.risk_engine.categories import assign_category, matrix_coordinates
from lwra.risk_engine.weighting import (
    clamp,
    likelihood_consequence_split,
    normalise_factor,
    risk_factor_weights,
    round_score,
    weighted_axis_score,
)

__all__ = [
    "assess_risk",
    "assess_risk_traced",
    "extract_factor_values",
    "compute_well_age_years",
    "compute_data_uncertainty",
    "dominant_drivers",
]

# Number of dominant drivers surfaced by default.
_DEFAULT_TOP_DRIVERS: int = 3

# Fields whose absence contributes to the data-uncertainty factor. These are
# the inputs that most affect the risk calculation; missing any of them makes
# the assessment less certain and is conservatively penalised.
_UNCERTAINTY_FIELDS: tuple[str, ...] = (
    "spud_date",
    "abandonment_date",
    "pressure_bar",
    "temperature_c",
    "proximity_to_receptors_m",
    "reservoir_fluid",  # counts as missing when UNKNOWN
)


def compute_well_age_years(
    well: WellData,
    *,
    as_of: date | None = None,
) -> float | None:
    """Derive the well's age in years for the age risk factor.

    Age is measured from the spud date to the abandonment date when both are
    known (the in-service life), otherwise from spud to ``as_of`` (today), as a
    proxy for elapsed degradation time.

    Args:
        well: The well under assessment.
        as_of: Reference date for a non-abandoned well. Defaults to
            ``date.today()``. Passing this explicitly keeps the calculation
            deterministic in tests and reports.

    Returns:
        Age in years (float), or ``None`` if the spud date is unknown.
    """
    if well.spud_date is None:
        return None
    end = well.abandonment_date or (as_of or date.today())
    delta_days = (end - well.spud_date).days
    return max(0.0, delta_days / 365.25)


def compute_data_uncertainty(well: WellData) -> tuple[float, dict[str, bool]]:
    """Compute the data-uncertainty factor as the fraction of key fields missing.

    Args:
        well: The well under assessment.

    Returns:
        ``(fraction_missing, presence_map)`` where ``fraction_missing`` is in
        [0, 1] and ``presence_map`` records which fields were considered
        missing (``True`` == missing).
    """
    missing: dict[str, bool] = {}
    for field in _UNCERTAINTY_FIELDS:
        value = getattr(well, field)
        if field == "reservoir_fluid":
            missing[field] = value is FluidType.UNKNOWN
        else:
            missing[field] = value is None
    fraction = sum(missing.values()) / len(missing)
    return fraction, missing


def extract_factor_values(
    well: WellData,
    integrity: IntegrityResult,
    *,
    as_of: date | None = None,
) -> tuple[dict[str, float | None], dict[str, Any]]:
    """Extract the raw input value for every risk factor.

    Args:
        well: The well under assessment.
        integrity: The integrity result feeding the inverted likelihood driver.
        as_of: Reference date for well-age derivation (see
            :func:`compute_well_age_years`).

    Returns:
        ``(raw_values, extraction_trace)`` where ``raw_values`` maps each
        :class:`RiskFactor` value to its raw input (or ``None`` if unavailable)
        and ``extraction_trace`` records how each was derived.
    """
    age_years = compute_well_age_years(well, as_of=as_of)
    uncertainty_fraction, presence_map = compute_data_uncertainty(well)

    raw_values: dict[str, float | None] = {
        RiskFactor.INTEGRITY_SCORE.value: integrity.overall_integrity_score,
        RiskFactor.WELL_AGE.value: age_years,
        RiskFactor.RESERVOIR_PRESSURE.value: well.pressure_bar,
        RiskFactor.TEMPERATURE.value: well.temperature_c,
        # fluid_hazard is resolved via fluid_key, not a numeric raw value.
        RiskFactor.FLUID_HAZARD.value: None,
        RiskFactor.PROXIMITY_TO_RECEPTORS.value: well.proximity_to_receptors_m,
        RiskFactor.DATA_UNCERTAINTY.value: uncertainty_fraction,
    }

    extraction_trace: dict[str, Any] = {
        "integrity_score": integrity.overall_integrity_score,
        "well_age_years": (round_score(age_years) if age_years is not None else None),
        "well_age_basis": (
            "spud->abandonment" if well.abandonment_date else "spud->as_of"
        ),
        "reservoir_pressure_bar": well.pressure_bar,
        "temperature_c": well.temperature_c,
        "reservoir_fluid": well.reservoir_fluid.value,
        "proximity_to_receptors_m": well.proximity_to_receptors_m,
        "data_uncertainty_fraction": round_score(uncertainty_fraction),
        "data_uncertainty_missing_fields": presence_map,
    }
    return raw_values, extraction_trace


def dominant_drivers(
    weighted_factors: dict[str, float],
    *,
    top_n: int = _DEFAULT_TOP_DRIVERS,
) -> tuple[str, ...]:
    """Identify the factors contributing most to the scalar risk score.

    Args:
        weighted_factors: Factor key -> weighted contribution to the score.
        top_n: Maximum number of drivers to surface.

    Returns:
        An ordered tuple of factor keys, highest weighted contribution first.
        Factors contributing zero are excluded.
    """
    ranked = sorted(weighted_factors.items(), key=lambda kv: kv[1], reverse=True)
    return tuple(name for name, contribution in ranked[:top_n] if contribution > 0.0)


def assess_risk_traced(
    well: WellData,
    integrity: IntegrityResult,
    *,
    as_of: date | None = None,
) -> tuple[RiskResult, dict[str, Any]]:
    """Assess risk and return both the result and its full trace.

    Args:
        well: The well under assessment.
        integrity: The integrity result for the same well.
        as_of: Reference date for well-age derivation; pass explicitly for
            fully deterministic output (reports, tests, snapshots).

    Returns:
        ``(result, trace)``. The ``trace`` is the complete, nested derivation
        suitable for audit, publication appendices, and report generation.

    Raises:
        ValueError: If ``well`` and ``integrity`` refer to different wells.
    """
    if well.well_id != integrity.well_id:
        raise ValueError(
            "well and integrity refer to different wells "
            f"({well.well_id!r} != {integrity.well_id!r})."
        )

    weights = risk_factor_weights()
    split = likelihood_consequence_split()
    raw_values, extraction_trace = extract_factor_values(well, integrity, as_of=as_of)

    # 1. Normalise every factor to a 0-100 contribution.
    contributions: dict[str, float] = {}
    normalisation_trace: dict[str, Any] = {}
    for factor in RiskFactor:
        key = factor.value
        if factor is RiskFactor.FLUID_HAZARD:
            contribution, frag = normalise_factor(
                factor, None, fluid_key=well.reservoir_fluid.value
            )
        else:
            contribution, frag = normalise_factor(factor, raw_values[key])
        contributions[key] = contribution
        normalisation_trace[key] = frag

    # 2. Scalar risk score = weighted sum of contributions.
    weighted_factors: dict[str, float] = {}
    scalar_total = 0.0
    weighting_trace: dict[str, dict[str, float]] = {}
    for key, contribution in contributions.items():
        weight = weights[key]
        weighted_contribution = contribution * weight
        weighted_factors[key] = round_score(weighted_contribution)
        scalar_total += weighted_contribution
        weighting_trace[key] = {
            "contribution": round_score(contribution),
            "weight": weight,
            "weighted_contribution": round_score(weighted_contribution),
        }
    risk_score = round_score(clamp(scalar_total))

    # 3. Likelihood / consequence axes for the risk matrix.
    likelihood, likelihood_factors = weighted_axis_score(
        contributions, weights, split, "likelihood"
    )
    consequence, consequence_factors = weighted_axis_score(
        contributions, weights, split, "consequence"
    )

    # 4. Category and matrix placement.
    category = assign_category(risk_score)
    l_bin, c_bin, matrix_trace = matrix_coordinates(likelihood, consequence)

    # 5. Dominant drivers.
    drivers = dominant_drivers(weighted_factors)

    result = RiskResult(
        well_id=well.well_id,
        risk_score=risk_score,
        risk_category=category,
        likelihood=likelihood,
        consequence=consequence,
        weighted_factors=weighted_factors,
        dominant_risk_drivers=drivers,
        calculation_trace={
            "matrix_cell": matrix_trace["cell"],
            "matrix_coordinates": {"likelihood_bin": l_bin, "consequence_bin": c_bin},
        },
    )

    trace: dict[str, Any] = {
        "well_id": well.well_id,
        "factor_extraction": extraction_trace,
        "normalisation": normalisation_trace,
        "weighting": {
            "method": "weighted sum of normalised factor contributions",
            "factors": weighting_trace,
            "risk_score": risk_score,
        },
        "axes": {
            "likelihood": {"score": likelihood, "factors": likelihood_factors},
            "consequence": {"score": consequence, "factors": consequence_factors},
        },
        "matrix": matrix_trace,
        "category": category.value,
        "dominant_risk_drivers": list(drivers),
        "risk_score": risk_score,
    }
    return result, trace


def assess_risk(
    well: WellData,
    integrity: IntegrityResult,
    *,
    as_of: date | None = None,
) -> RiskResult:
    """Assess the risk of a single well.

    This is the primary public entry point of the risk engine. It is a pure,
    deterministic function of its inputs and the externalised configuration.

    Args:
        well: The well under assessment.
        integrity: The integrity result for the same well.
        as_of: Reference date for well-age derivation; pass explicitly for
            fully deterministic output.

    Returns:
        A fully populated, immutable :class:`RiskResult`.
    """
    result, _ = assess_risk_traced(well, integrity, as_of=as_of)
    return result
