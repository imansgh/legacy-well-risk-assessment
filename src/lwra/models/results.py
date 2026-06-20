"""Result data models produced by the assessment engines.

Defines the output contracts of the three engines described in the
architecture document:

* :class:`IntegrityResult`  -- produced by ``integrity_engine``
* :class:`RiskResult`       -- produced by ``risk_engine``
* :class:`RecommendationResult` -- produced by ``recommendation_engine``

Unlike the input models, results are mutable by default is *not* desirable:
they are computed artefacts that should be treated as read-only once produced,
so they are also ``frozen=True``. Every result carries enough breakdown/trace
detail to be fully auditable, which serves both scientific publication and the
JSON report / PostgreSQL JSONB persistence paths.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from lwra.models.enums import (
    IntegrityCategory,
    RiskCategory,
    SuitabilityLevel,
    Verdict,
)

__all__ = ["IntegrityResult", "RiskResult", "RecommendationResult"]


def _utcnow() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class IntegrityResult(BaseModel):
    """Outcome of the integrity assessment for a single well.

    All component scores are on a 0-100 scale, where higher is better
    integrity. ``component_breakdown`` mirrors the named component scores in a
    single dict for convenient tabular export.

    Attributes:
        well_id: Identifier of the assessed well.
        primary_barrier_score: Primary barrier score (0-100).
        secondary_barrier_score: Secondary barrier score (0-100).
        cement_quality_score: Cement quality score (0-100).
        mechanical_integrity_score: Mechanical integrity score (0-100).
        plugging_score: Plugging condition score (0-100).
        overall_integrity_score: Aggregated overall score (0-100).
        integrity_category: Qualitative band for the overall score.
        flags: Notable findings (e.g. unverified secondary barrier).
        component_breakdown: Named component scores as a dict.
        assessed_at: UTC timestamp the result was produced.

    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    well_id: str = Field(..., min_length=1, description="Assessed well identifier.")
    primary_barrier_score: float = Field(
        ..., ge=0, le=100, description="Primary barrier score (0-100)."
    )
    secondary_barrier_score: float = Field(
        ..., ge=0, le=100, description="Secondary barrier score (0-100)."
    )
    cement_quality_score: float = Field(
        ..., ge=0, le=100, description="Cement quality score (0-100)."
    )
    mechanical_integrity_score: float = Field(
        ..., ge=0, le=100, description="Mechanical integrity score (0-100)."
    )
    plugging_score: float = Field(
        ..., ge=0, le=100, description="Plugging condition score (0-100)."
    )
    overall_integrity_score: float = Field(
        ..., ge=0, le=100, description="Aggregated overall score (0-100)."
    )
    integrity_category: IntegrityCategory = Field(
        ..., description="Qualitative band for the overall score."
    )
    flags: tuple[str, ...] = Field(default_factory=tuple, description="Notable integrity findings.")
    component_breakdown: dict[str, float] = Field(
        default_factory=dict, description="Named component scores as a dict."
    )
    assessed_at: datetime = Field(
        default_factory=_utcnow, description="UTC timestamp of assessment."
    )


class RiskResult(BaseModel):
    """Outcome of the risk assessment for a single well.

    The risk score is on a 0-100 scale where higher means greater risk. The
    ``calculation_trace`` provides a per-factor, fully transparent record of how
    the score was derived, satisfying the auditability requirement in the
    architecture document.

    Attributes:
        well_id: Identifier of the assessed well.
        risk_score: Aggregated risk score (0-100).
        risk_category: Qualitative band for the risk score.
        likelihood: Likelihood component (0-100).
        consequence: Consequence component (0-100).
        weighted_factors: Per-factor weighted contributions to the score.
        dominant_risk_drivers: Names of the factors driving the risk.
        calculation_trace: Full transparency record of the calculation.
        assessed_at: UTC timestamp the result was produced.

    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    well_id: str = Field(..., min_length=1, description="Assessed well identifier.")
    risk_score: float = Field(..., ge=0, le=100, description="Aggregated risk score (0-100).")
    risk_category: RiskCategory = Field(..., description="Qualitative band for the risk score.")
    likelihood: float = Field(..., ge=0, le=100, description="Likelihood component (0-100).")
    consequence: float = Field(..., ge=0, le=100, description="Consequence component (0-100).")
    weighted_factors: dict[str, float] = Field(
        default_factory=dict, description="Per-factor weighted contributions."
    )
    dominant_risk_drivers: tuple[str, ...] = Field(
        default_factory=tuple, description="Factors driving the risk."
    )
    calculation_trace: dict[str, Any] = Field(
        default_factory=dict, description="Full transparency record."
    )
    assessed_at: datetime = Field(
        default_factory=_utcnow, description="UTC timestamp of assessment."
    )


class RecommendationResult(BaseModel):
    """Actionable recommendation derived from integrity and risk results.

    Attributes:
        well_id: Identifier of the assessed well.
        verdict: Top-level recommendation verdict.
        co2_storage_suitability: Suitability for CO2 storage reuse.
        geothermal_suitability: Suitability for geothermal reuse.
        required_actions: Concrete actions required before/for reuse.
        confidence: Confidence in the recommendation, in [0, 1].
        rationale: Human-readable justification for the verdict.
        assessed_at: UTC timestamp the result was produced.

    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    well_id: str = Field(..., min_length=1, description="Assessed well identifier.")
    verdict: Verdict = Field(..., description="Top-level recommendation verdict.")
    co2_storage_suitability: SuitabilityLevel = Field(
        ..., description="Suitability for CO2 storage reuse."
    )
    geothermal_suitability: SuitabilityLevel = Field(
        ..., description="Suitability for geothermal reuse."
    )
    required_actions: tuple[str, ...] = Field(
        default_factory=tuple, description="Actions required for reuse."
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the recommendation [0, 1]."
    )
    rationale: str = Field(default="", description="Justification for the verdict.")
    assessed_at: datetime = Field(
        default_factory=_utcnow, description="UTC timestamp of assessment."
    )
