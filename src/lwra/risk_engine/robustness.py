"""Robustness of the risk category to score uncertainty.

A single 0-100 risk score collapses a well into one of four categories (LOW /
MEDIUM / HIGH / CRITICAL) at fixed boundaries (26, 51, 76). A well scoring 50.5
is MEDIUM; one scoring 51.5 is HIGH — yet the inputs behind that half-point are
themselves uncertain, especially when key fields are missing. Reporting the bare
category without its fragility would imply more precision than the data support
and could mis-prioritise a remediation/P&A queue.

This module makes that fragility explicit and **deterministic**, without
changing the nominal score or category. The risk score is bracketed by a
symmetric band and re-categorised at each edge; the category is ``robust`` only
if it is unchanged across the whole band. The band width is derived from the
well's own *data-uncertainty fraction* (the share of key inputs missing) scaled
by a configured maximum, so a fully characterised well has a zero band and a
sparsely characterised one is widely bracketed — the band is a property of how
well the input is known, not random noise.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from lwra.models.enums import RiskCategory
from lwra.models.results import IntegrityResult, RiskResult
from lwra.models.well import WellData
from lwra.risk_engine.categories import assign_category
from lwra.risk_engine.scorer import assess_risk, compute_data_uncertainty
from lwra.risk_engine.weighting import clamp, load_thresholds, round_score

__all__ = [
    "CategoryRobustness",
    "category_robustness",
    "risk_category_robustness",
]


@dataclass(frozen=True)
class CategoryRobustness:
    """Fragility of a risk category under score uncertainty.

    Attributes:
        well_id: Well identifier (empty when scored from a bare value).
        risk_score: Nominal risk score (0-100).
        risk_category: Nominal category at ``risk_score``.
        category_low: Category at ``risk_score - score_uncertainty``.
        category_high: Category at ``risk_score + score_uncertainty``.
        score_uncertainty: Half-width of the symmetric band (score points).
        boundary_margin: Distance (score points, non-negative) from
            ``risk_score`` to the nearest category boundary. ``inf`` when no
            interior boundary applies.
        is_robust: True iff the category is unchanged across the full band.

    """

    well_id: str
    risk_score: float
    risk_category: RiskCategory
    category_low: RiskCategory
    category_high: RiskCategory
    score_uncertainty: float
    boundary_margin: float
    is_robust: bool


def _interior_boundaries(thresholds: dict[str, Any]) -> list[float]:
    """Category lower bounds excluding the 0.0 floor (the splitting points)."""
    bands = thresholds["risk_category_thresholds"]
    return sorted(float(b["min"]) for b in bands.values() if float(b["min"]) > 0.0)


def category_robustness(
    risk_score: float,
    *,
    score_uncertainty: float,
    thresholds: dict[str, Any] | None = None,
    well_id: str = "",
) -> CategoryRobustness:
    """Assess how fragile a risk category is to a given score band.

    Args:
        risk_score: Nominal risk score (0-100, higher worse).
        score_uncertainty: Half-width of the symmetric uncertainty band, in
            score points (must be non-negative).
        thresholds: Optional pre-loaded thresholds (defaults to the config).
        well_id: Optional identifier to carry into the result.

    Returns:
        A :class:`CategoryRobustness` for the score.

    Raises:
        ValueError: If ``score_uncertainty`` is negative.

    """
    if score_uncertainty < 0.0:
        raise ValueError("score_uncertainty must be non-negative")

    cfg = thresholds or load_thresholds()
    nominal = assign_category(risk_score)
    low = assign_category(clamp(risk_score - score_uncertainty))
    high = assign_category(clamp(risk_score + score_uncertainty))

    boundaries = _interior_boundaries(cfg)
    margin = min((abs(risk_score - b) for b in boundaries), default=float("inf"))

    return CategoryRobustness(
        well_id=well_id,
        risk_score=round_score(risk_score),
        risk_category=nominal,
        category_low=low,
        category_high=high,
        score_uncertainty=round_score(score_uncertainty),
        boundary_margin=round_score(margin) if margin != float("inf") else margin,
        is_robust=(low == nominal == high),
    )


def risk_category_robustness(
    well: WellData,
    integrity: IntegrityResult,
    *,
    as_of: date | None = None,
    risk: RiskResult | None = None,
    thresholds: dict[str, Any] | None = None,
) -> CategoryRobustness:
    """Risk-category robustness for a well, band derived from data uncertainty.

    The uncertainty band is ``data_uncertainty_fraction * max_score_uncertainty``
    (the configured maximum), so the category's reported trustworthiness scales
    with how completely the well is characterised.

    Args:
        well: The well under assessment.
        integrity: The integrity result for the same well.
        as_of: Reference date for the risk scoring (passed through for
            determinism).
        risk: Optional pre-computed risk result to avoid re-scoring; recomputed
            from ``well``/``integrity`` when not supplied.
        thresholds: Optional pre-loaded thresholds (defaults to the config).

    Returns:
        A :class:`CategoryRobustness` for the well.

    """
    cfg = thresholds or load_thresholds()
    result = risk or assess_risk(well, integrity, as_of=as_of)
    fraction, _ = compute_data_uncertainty(well)
    max_band = float(cfg["risk_category_robustness"]["max_score_uncertainty"])
    score_uncertainty = fraction * max_band

    return category_robustness(
        result.risk_score,
        score_uncertainty=score_uncertainty,
        thresholds=cfg,
        well_id=well.well_id,
    )
