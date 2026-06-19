"""Shared, deterministic helpers for the integrity engine.

This module centralises the small pieces of logic reused across the component
evaluators (``barrier_eval``, ``cement``, ``mechanical``, ``plugging``) and the
:mod:`~lwra.integrity_engine.aggregator`:

* loading and caching the externalised weights/thresholds (YAML),
* the canonical 0-1 -> 0-100 condition-to-score conversion,
* the verification/low-confidence penalty model,
* interval-coverage computation,
* deterministic rounding and clamping.

Every function here is a pure, stateless function of its arguments (the only
state is an LRU-cached read of the on-disk YAML, which is itself deterministic
for a given file). Keeping these primitives in one place guarantees that all
components share identical, auditable scoring semantics -- a prerequisite for a
publication-quality, reproducible methodology.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "CONFIG_DIR",
    "ROUNDING_DP",
    "load_weights",
    "load_thresholds",
    "integrity_component_weights",
    "integrity_overrides",
    "clamp",
    "round_score",
    "condition_to_score",
    "verification_factor",
    "interval_coverage_fraction",
    "merge_intervals",
]

# Location of the externalised configuration. The engine reads the *same* files
# documented in the config module; nothing is hard-coded in Python.
CONFIG_DIR: Path = Path(__file__).resolve().parent.parent / "config"

# All published scores are rounded to this many decimal places so that results
# are byte-for-byte reproducible across platforms and serialisation round-trips.
ROUNDING_DP: int = 2

# Verification model -------------------------------------------------------
# A barrier that has been independently verified is trusted at full weight; an
# unverified barrier is discounted by this factor. This is a deliberate,
# documented conservatism consistent with risk-based well-integrity philosophy
# (an unverified barrier is not a credited barrier).
_UNVERIFIED_DISCOUNT: float = 0.60

# A verified-but-low-confidence barrier (raw condition below the configured
# ``low_confidence_condition_threshold``) is further discounted, because a
# verification that returns a poor reading is itself evidence of degradation.
_LOW_CONFIDENCE_DISCOUNT: float = 0.80


@lru_cache(maxsize=1)
def load_weights() -> dict[str, Any]:
    """Load and cache ``weights.yaml``.

    Returns:
        The parsed weights document as a nested dictionary.

    Raises:
        FileNotFoundError: If the weights file is missing.
        ValueError: If the file does not parse to a mapping.
    """
    return _load_yaml(CONFIG_DIR / "weights.yaml")


@lru_cache(maxsize=1)
def load_thresholds() -> dict[str, Any]:
    """Load and cache ``thresholds.yaml``.

    Returns:
        The parsed thresholds document as a nested dictionary.

    Raises:
        FileNotFoundError: If the thresholds file is missing.
        ValueError: If the file does not parse to a mapping.
    """
    return _load_yaml(CONFIG_DIR / "thresholds.yaml")


def _load_yaml(path: Path) -> dict[str, Any]:
    """Parse a YAML file and assert it is a mapping."""
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Configuration root must be a mapping: {path}")
    return data


def integrity_component_weights() -> dict[str, float]:
    """Return the integrity component weight block from ``weights.yaml``.

    Returns:
        Mapping of component key -> weight. Validated to sum to 1.0 within a
        small tolerance so that the aggregate stays on a true 0-100 scale.

    Raises:
        KeyError: If the block is absent.
        ValueError: If the weights do not sum to 1.0 within tolerance.
    """
    weights = load_weights()
    try:
        block = {str(k): float(v) for k, v in weights["integrity_component_weights"].items()}
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError("'integrity_component_weights' missing from weights.yaml") from exc
    total = sum(block.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(
            f"integrity_component_weights must sum to 1.0 (got {total:.6f})."
        )
    return block


def integrity_overrides() -> dict[str, float]:
    """Return the integrity override rules from ``thresholds.yaml``.

    Returns:
        Mapping with the cap values and the low-confidence threshold.

    Raises:
        KeyError: If the override block is absent.
    """
    thresholds = load_thresholds()
    try:
        block = thresholds["integrity_overrides"]
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError("'integrity_overrides' missing from thresholds.yaml") from exc
    return {str(k): float(v) for k, v in block.items()}


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    """Clamp ``value`` into the inclusive ``[low, high]`` range.

    Args:
        value: The value to clamp.
        low: Inclusive lower bound.
        high: Inclusive upper bound.

    Returns:
        ``value`` constrained to ``[low, high]``.
    """
    return max(low, min(high, value))


def round_score(value: float) -> float:
    """Round a score to the engine's canonical precision.

    Args:
        value: The raw score.

    Returns:
        ``value`` rounded to :data:`ROUNDING_DP` decimal places.
    """
    return round(value, ROUNDING_DP)


def condition_to_score(condition: float) -> float:
    """Convert a raw [0, 1] condition observation to a 0-100 scale.

    The mapping is intentionally linear so the relationship between an observed
    condition and its contribution is transparent and easy to defend.

    Args:
        condition: Raw condition in [0, 1]; 1 is pristine.

    Returns:
        The condition expressed on a 0-100 scale.
    """
    return clamp(condition * 100.0)


def verification_factor(
    *,
    verified: bool,
    condition: float,
    low_confidence_threshold: float,
) -> float:
    """Return the multiplicative trust factor applied to a barrier's score.

    The factor encodes two documented conservatisms:

    * An **unverified** barrier is discounted to :data:`_UNVERIFIED_DISCOUNT`
      because, under risk-based philosophy, an unverified barrier cannot be
      fully credited.
    * A **verified but low-confidence** barrier (raw condition below
      ``low_confidence_threshold``) is discounted to
      :data:`_LOW_CONFIDENCE_DISCOUNT`, because a verification returning a poor
      reading is itself evidence of degradation.

    Args:
        verified: Whether the barrier was independently verified.
        condition: Raw condition in [0, 1].
        low_confidence_threshold: Threshold below which a verified barrier is
            treated as low confidence (from ``integrity_overrides``).

    Returns:
        A trust factor in (0, 1].
    """
    if not verified:
        return _UNVERIFIED_DISCOUNT
    if condition < low_confidence_threshold:
        return _LOW_CONFIDENCE_DISCOUNT
    return 1.0


def merge_intervals(
    intervals: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Merge overlapping/adjacent depth intervals into a disjoint set.

    Args:
        intervals: List of ``(top_m, bottom_m)`` pairs (top < bottom).

    Returns:
        A sorted list of non-overlapping ``(top_m, bottom_m)`` intervals.
    """
    if not intervals:
        return []
    ordered = sorted(intervals, key=lambda iv: iv[0])
    merged: list[tuple[float, float]] = [ordered[0]]
    for top, bottom in ordered[1:]:
        last_top, last_bottom = merged[-1]
        if top <= last_bottom:  # overlap or touch
            merged[-1] = (last_top, max(last_bottom, bottom))
        else:
            merged.append((top, bottom))
    return merged


def interval_coverage_fraction(
    intervals: list[tuple[float, float]],
    target_top_m: float,
    target_bottom_m: float,
) -> float:
    """Fraction of a target depth window covered by the given intervals.

    Used to reward barriers/cement that span the critical sealing interval and
    penalise partial coverage.

    Args:
        intervals: Covering ``(top_m, bottom_m)`` intervals.
        target_top_m: Top of the target window (m).
        target_bottom_m: Bottom of the target window (m).

    Returns:
        Covered fraction in [0, 1]. Returns 0.0 for a non-positive window.
    """
    window = target_bottom_m - target_top_m
    if window <= 0:
        return 0.0
    covered = 0.0
    for top, bottom in merge_intervals(intervals):
        lo = max(top, target_top_m)
        hi = min(bottom, target_bottom_m)
        if hi > lo:
            covered += hi - lo
    return clamp(covered / window, 0.0, 1.0)
