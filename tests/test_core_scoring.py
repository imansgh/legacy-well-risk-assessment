"""Unit tests for the deterministic scoring primitives.

These exercise the computational core that the engines build on: linear
normalisation (monotonicity, bounds, inversion, degenerate ramp), the barrier
verification-trust model, and interval-coverage arithmetic. They pin behaviour
the higher-level pipeline tests only exercise indirectly.
"""

from __future__ import annotations

import pytest

from lwra.integrity_engine._scoring import (
    condition_to_score,
    interval_coverage_fraction,
    merge_intervals,
    verification_factor,
)
from lwra.risk_engine.weighting import clamp, normalise_linear

# ── normalise_linear ─────────────────────────────────────────────────────────


def test_normalise_linear_monotonic_increasing() -> None:
    xs = [i * 6.0 for i in range(0, 11)]  # 0..60
    ys = [normalise_linear(x, 0.0, 60.0) for x in xs]
    assert ys[0] == 0.0
    assert ys[-1] == 100.0
    for a, b in zip(ys, ys[1:], strict=False):
        assert b >= a


def test_normalise_linear_inverted_is_decreasing() -> None:
    xs = [i * 500.0 for i in range(0, 11)]
    ys = [normalise_linear(x, 100.0, 5000.0, invert=True) for x in xs]
    for a, b in zip(ys, ys[1:], strict=False):
        assert b <= a


def test_normalise_linear_clamps_outside_range() -> None:
    assert normalise_linear(-10.0, 0.0, 60.0) == 0.0
    assert normalise_linear(999.0, 0.0, 60.0) == 100.0


def test_normalise_linear_degenerate_raises() -> None:
    with pytest.raises(ValueError, match="high != low"):
        normalise_linear(1.0, 5.0, 5.0)


def test_clamp_bounds() -> None:
    assert clamp(-1.0) == 0.0
    assert clamp(150.0) == 100.0
    assert clamp(42.0) == 42.0


def test_condition_to_score_is_linear() -> None:
    assert condition_to_score(0.0) == 0.0
    assert condition_to_score(0.5) == 50.0
    assert condition_to_score(1.0) == 100.0


# ── verification_factor ──────────────────────────────────────────────────────


def test_verification_factor_unverified_discounted() -> None:
    f = verification_factor(verified=False, condition=0.9, low_confidence_threshold=0.4)
    assert f == 0.60


def test_verification_factor_verified_low_confidence() -> None:
    f = verification_factor(verified=True, condition=0.3, low_confidence_threshold=0.4)
    assert f == 0.80


def test_verification_factor_verified_full_trust() -> None:
    f = verification_factor(verified=True, condition=0.9, low_confidence_threshold=0.4)
    assert f == 1.0


def test_verification_factor_ordering() -> None:
    unver = verification_factor(verified=False, condition=0.9, low_confidence_threshold=0.4)
    lowc = verification_factor(verified=True, condition=0.1, low_confidence_threshold=0.4)
    full = verification_factor(verified=True, condition=0.9, low_confidence_threshold=0.4)
    assert unver < lowc < full


# ── interval geometry ────────────────────────────────────────────────────────


def test_merge_intervals_overlapping() -> None:
    assert merge_intervals([(0.0, 10.0), (5.0, 15.0)]) == [(0.0, 15.0)]


def test_merge_intervals_disjoint_preserved() -> None:
    assert merge_intervals([(20.0, 30.0), (0.0, 10.0)]) == [(0.0, 10.0), (20.0, 30.0)]


def test_merge_intervals_empty() -> None:
    assert merge_intervals([]) == []


def test_coverage_full_partial_none() -> None:
    assert interval_coverage_fraction([(0.0, 100.0)], 0.0, 100.0) == 1.0
    assert interval_coverage_fraction([(0.0, 50.0)], 0.0, 100.0) == 0.5
    assert interval_coverage_fraction([(200.0, 300.0)], 0.0, 100.0) == 0.0


def test_coverage_non_positive_window_is_zero() -> None:
    assert interval_coverage_fraction([(0.0, 100.0)], 100.0, 100.0) == 0.0


def test_coverage_overlapping_intervals_not_double_counted() -> None:
    # Two overlapping intervals covering 0-60 of a 0-100 window -> 0.6, not >1.
    frac = interval_coverage_fraction([(0.0, 40.0), (30.0, 60.0)], 0.0, 100.0)
    assert frac == pytest.approx(0.6)
