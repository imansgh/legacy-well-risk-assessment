"""Assessment pipeline: the stable orchestration interface.

This module is the single seam every consumer of the Legacy Well Risk
Assessment Tool should call: the Streamlit dashboard, the FastAPI backend, the
JSON/PDF/Excel report generators, the PostgreSQL persistence layer, batch
portfolio screening, and future machine-learning feature extraction all go
through here rather than wiring the three engines together themselves.

It contains **no business logic** of its own. It composes, in order:

    WellData
        -> integrity_engine.assess_integrity[_traced]
        -> risk_engine.assess_risk[_traced]
        -> recommendation_engine.assess_recommendations[_traced]

and packages the three immutable result objects (plus an optional combined
trace) into a single frozen :class:`WellAssessment` aggregate.

Determinism
-----------
The only non-deterministic input anywhere in the stack is "today" (used to age a
non-abandoned well). The pipeline therefore takes an explicit ``as_of`` date and
threads it into the risk engine; passing it guarantees byte-for-byte
reproducible output for reports, tests, snapshots, and ML training sets. When
omitted it defaults to :func:`datetime.date.today`, recorded on the result.

Consistency
-----------
The integrity, risk, and recommendation results all carry the same ``well_id``
by construction (each engine copies it from its input). :class:`WellAssessment`
validates this invariant on construction, so a malformed assessment can never be
persisted or served.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lwra.integrity_engine import (
    assess_integrity,
    assess_integrity_traced,
    has_verified_secondary_barrier,
    primary_is_failed_or_unverified,
)
from lwra.models.results import (
    IntegrityResult,
    RecommendationResult,
    RiskResult,
)
from lwra.models.well import WellData
from lwra.recommendation_engine import assess_recommendations, assess_recommendations_traced
from lwra.risk_engine import assess_risk, assess_risk_traced

__all__ = [
    "WellAssessment",
    "assess_well",
    "assess_well_traced",
]


def _utcnow() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class WellAssessment(BaseModel):
    """The complete, immutable assessment of a single well.

    This is the one object every downstream consumer receives. It bundles the
    three engine results behind a stable, serialisable contract. It is
    ``frozen=True`` because, like the individual results, a completed assessment
    is a computed artefact that must not be mutated after the fact.

    The combined ``trace`` is optional: :func:`assess_well` omits it (lean object
    for dashboards, list views, and ML feature rows), while
    :func:`assess_well_traced` populates it (full derivation for audit,
    publication appendices, and detailed report drill-downs).

    Attributes:
        well_id: Identifier shared by the well and all three results.
        integrity: The integrity assessment result.
        risk: The risk assessment result.
        recommendation: The recommendation result.
        as_of: The assessment reference date used for age-dependent factors.
        assessed_at: UTC timestamp the assessment was assembled.
        trace: Optional combined calculation trace (present only for the traced
            entry point).

    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    well_id: str = Field(..., min_length=1, description="Assessed well identifier.")
    integrity: IntegrityResult = Field(..., description="Integrity assessment result.")
    risk: RiskResult = Field(..., description="Risk assessment result.")
    recommendation: RecommendationResult = Field(..., description="Recommendation result.")
    as_of: date = Field(..., description="Assessment reference date.")
    assessed_at: datetime = Field(default_factory=_utcnow, description="UTC timestamp of assembly.")
    trace: dict[str, Any] | None = Field(
        default=None, description="Optional combined calculation trace."
    )

    @model_validator(mode="after")
    def _validate_well_id_consistency(self) -> WellAssessment:
        """Ensure every bundled result refers to the same well."""
        ids = {
            self.well_id,
            self.integrity.well_id,
            self.risk.well_id,
            self.recommendation.well_id,
        }
        if len(ids) != 1:
            raise ValueError(
                "WellAssessment requires a single consistent well_id across all "
                f"results (got {sorted(ids)})."
            )
        return self

    @property
    def verdict(self) -> str:
        """Convenience accessor for the top-level recommendation verdict value."""
        return self.recommendation.verdict.value

    @property
    def overall_integrity_score(self) -> float:
        """Convenience accessor for the overall integrity score (0-100)."""
        return self.integrity.overall_integrity_score

    @property
    def risk_score(self) -> float:
        """Convenience accessor for the overall risk score (0-100)."""
        return self.risk.risk_score


def _resolve_as_of(as_of: date | None) -> date:
    """Resolve the assessment reference date, defaulting to today.

    Args:
        as_of: Caller-supplied reference date, or ``None``.

    Returns:
        ``as_of`` if provided, otherwise :func:`date.today`.

    """
    return as_of if as_of is not None else date.today()


def assess_well_traced(
    well: WellData,
    *,
    as_of: date | None = None,
) -> WellAssessment:
    """Run the full assessment workflow and return the result *with* its trace.

    Orchestrates the three engines in order and assembles a :class:`WellAssessment`
    whose ``trace`` contains the combined, nested derivation of all three
    engines. This is the entry point for audit, publication appendices, and
    report drill-downs.

    Args:
        well: The well to assess.
        as_of: Assessment reference date for age-dependent risk factors. Pass
            explicitly for fully deterministic output; defaults to today.

    Returns:
        A frozen :class:`WellAssessment` with a populated ``trace``.

    Raises:
        ValueError: If the engines produce results for inconsistent well IDs
            (guarded by :class:`WellAssessment`).

    """
    reference_date = _resolve_as_of(as_of)

    # 1. Integrity.
    integrity, integrity_trace = assess_integrity_traced(well)

    # 2. Risk (consumes the integrity result; aged against the reference date).
    risk, risk_trace = assess_risk_traced(well, integrity, as_of=reference_date)

    # 3. Recommendation (consumes both results plus the barrier predicates the
    #    integrity engine exposes, so no integrity logic is duplicated here).
    has_verified_secondary = has_verified_secondary_barrier(well.barriers)
    primary_unreliable = primary_is_failed_or_unverified(well.barriers)
    recommendation, recommendation_trace = assess_recommendations_traced(
        well,
        integrity,
        risk,
        has_verified_secondary=has_verified_secondary,
        primary_failed_or_unverified=primary_unreliable,
    )

    combined_trace: dict[str, Any] = {
        "well_id": well.well_id,
        "as_of": reference_date.isoformat(),
        "integrity": integrity_trace,
        "risk": risk_trace,
        "recommendation": recommendation_trace,
    }

    return WellAssessment(
        well_id=well.well_id,
        integrity=integrity,
        risk=risk,
        recommendation=recommendation,
        as_of=reference_date,
        trace=combined_trace,
    )


def assess_well(
    well: WellData,
    *,
    as_of: date | None = None,
) -> WellAssessment:
    """Run the full assessment workflow and return the result without a trace.

    Identical orchestration to :func:`assess_well_traced` but discards the
    per-engine traces, yielding a lean :class:`WellAssessment` (``trace`` is
    ``None``). This is the entry point for dashboards, list/portfolio views,
    API responses that do not need the full derivation, and ML feature rows.

    Args:
        well: The well to assess.
        as_of: Assessment reference date for age-dependent risk factors. Pass
            explicitly for fully deterministic output; defaults to today.

    Returns:
        A frozen :class:`WellAssessment` with ``trace`` set to ``None``.

    Raises:
        ValueError: If the engines produce results for inconsistent well IDs
            (guarded by :class:`WellAssessment`).

    """
    reference_date = _resolve_as_of(as_of)

    integrity = assess_integrity(well)
    risk = assess_risk(well, integrity, as_of=reference_date)
    has_verified_secondary = has_verified_secondary_barrier(well.barriers)
    primary_unreliable = primary_is_failed_or_unverified(well.barriers)
    recommendation = assess_recommendations(
        well,
        integrity,
        risk,
        has_verified_secondary=has_verified_secondary,
        primary_failed_or_unverified=primary_unreliable,
    )

    return WellAssessment(
        well_id=well.well_id,
        integrity=integrity,
        risk=risk,
        recommendation=recommendation,
        as_of=reference_date,
        trace=None,
    )
