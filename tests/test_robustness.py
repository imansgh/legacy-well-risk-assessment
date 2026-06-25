"""Tests for risk-category robustness under score uncertainty."""

from __future__ import annotations

from datetime import date

import pytest

from lwra.models.enums import RiskCategory
from lwra.risk_engine.robustness import (
    category_robustness,
    risk_category_robustness,
)
from lwra.services.pipeline import assess_well_traced

AS_OF = date(2025, 1, 1)


# ── Pure analytic core ───────────────────────────────────────────────────────


def test_interior_score_is_robust() -> None:
    r = category_robustness(10.0, score_uncertainty=5.0)
    assert r.risk_category is RiskCategory.LOW
    assert r.is_robust
    assert r.category_low is RiskCategory.LOW
    assert r.category_high is RiskCategory.LOW
    # Nearest interior boundary is 26.
    assert r.boundary_margin == 16.0


def test_score_near_boundary_is_fragile() -> None:
    # 50.5 is MEDIUM; +/-1 straddles the 51 HIGH boundary.
    r = category_robustness(50.5, score_uncertainty=1.0)
    assert r.risk_category is RiskCategory.MEDIUM
    assert not r.is_robust
    assert r.category_high is RiskCategory.HIGH
    assert r.boundary_margin == 0.5


def test_zero_band_is_always_robust() -> None:
    r = category_robustness(51.0, score_uncertainty=0.0)
    assert r.is_robust
    assert r.category_low is r.category_high is r.risk_category


def test_negative_uncertainty_raises() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        category_robustness(50.0, score_uncertainty=-1.0)


# ── Well-level convenience (band from data uncertainty) ──────────────────────


def test_well_level_matches_nominal_score(well_excellent) -> None:  # type: ignore[no-untyped-def]
    a = assess_well_traced(well_excellent, as_of=AS_OF)
    r = risk_category_robustness(well_excellent, a.integrity, as_of=AS_OF, risk=a.risk)
    assert r.well_id == well_excellent.well_id
    assert r.risk_score == a.risk.risk_score
    assert r.risk_category is a.risk.risk_category
    assert 0.0 <= r.score_uncertainty <= 15.0


def test_sparse_well_has_wider_band(well_data_poor, well_excellent) -> None:  # type: ignore[no-untyped-def]
    a_poor = assess_well_traced(well_data_poor, as_of=AS_OF)
    a_good = assess_well_traced(well_excellent, as_of=AS_OF)
    r_poor = risk_category_robustness(
        well_data_poor, a_poor.integrity, as_of=AS_OF, risk=a_poor.risk
    )
    r_good = risk_category_robustness(
        well_excellent, a_good.integrity, as_of=AS_OF, risk=a_good.risk
    )
    # More missing data -> at least as wide an uncertainty band.
    assert r_poor.score_uncertainty >= r_good.score_uncertainty
    assert r_poor.score_uncertainty > 0.0
