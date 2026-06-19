"""Integrity aggregation and the public engine entry point.

Combines the five component scores into the overall integrity score, applies
the well-barrier-philosophy override caps, derives human-readable flags,
assigns the qualitative category, and assembles a fully auditable
:class:`~lwra.models.results.IntegrityResult`.

The public entry point is :func:`assess_integrity`. It is a pure function of a
:class:`~lwra.models.well.WellData` instance (plus the cached, deterministic
configuration); it returns a new immutable result and never mutates its input.

Aggregation pipeline
---------------------
1. Score each component (primary, secondary, cement, mechanical, plugging).
2. Weighted aggregate using ``integrity_component_weights`` from weights.yaml.
3. Apply override caps from ``integrity_overrides`` in thresholds.yaml:
     * no verified independent secondary barrier  -> cap at 59.0
     * failed/unverified primary barrier          -> cap at 39.0
   The lowest applicable cap wins.
4. Assign category via ``integrity_category_thresholds``.
5. Emit flags for every notable condition encountered.

The returned result carries ``component_breakdown`` (named scores) and the
full ``calculation_trace`` is exposed via :func:`assess_integrity_traced` for
callers (reports, dashboards) that need the complete derivation.
"""

from __future__ import annotations

from typing import Any

from lwra.config.enums import IntegrityComponent
from lwra.integrity_engine._scoring import (
    clamp,
    integrity_component_weights,
    integrity_overrides,
    load_thresholds,
    round_score,
)
from lwra.integrity_engine.barrier_eval import (
    evaluate_primary_barrier,
    evaluate_secondary_barrier,
    has_verified_secondary_barrier,
    primary_is_failed_or_unverified,
)
from lwra.integrity_engine.cement import evaluate_cement_quality
from lwra.integrity_engine.mechanical import evaluate_mechanical_integrity
from lwra.integrity_engine.plugging import evaluate_plugging
from lwra.models.enums import BarrierType, IntegrityCategory
from lwra.models.results import IntegrityResult
from lwra.models.well import WellData

__all__ = [
    "assess_integrity",
    "assess_integrity_traced",
    "aggregate_components",
    "apply_overrides",
    "assign_category",
    "generate_flags",
]


def aggregate_components(
    component_scores: dict[str, float],
) -> tuple[float, dict[str, Any]]:
    """Weighted aggregation of component scores using configured weights.

    Args:
        component_scores: Mapping of :class:`IntegrityComponent` value -> score
            (0-100). Must contain every component key.

    Returns:
        ``(weighted_score, trace)`` where ``trace`` records each component's
        score, weight, and weighted contribution.

    Raises:
        KeyError: If a required component score is missing.
    """
    weights = integrity_component_weights()
    contributions: dict[str, dict[str, float]] = {}
    weighted_total = 0.0
    for component, weight in weights.items():
        if component not in component_scores:
            raise KeyError(f"Missing component score for '{component}'.")
        score = component_scores[component]
        contribution = score * weight
        weighted_total += contribution
        contributions[component] = {
            "score": round_score(score),
            "weight": weight,
            "weighted_contribution": round_score(contribution),
        }
    weighted_total = clamp(weighted_total)
    trace = {
        "method": "weighted sum of component scores",
        "contributions": contributions,
        "weighted_score": round_score(weighted_total),
    }
    return round_score(weighted_total), trace


def apply_overrides(
    weighted_score: float,
    *,
    has_verified_secondary: bool,
    primary_failed_or_unverified: bool,
) -> tuple[float, dict[str, Any]]:
    """Apply well-barrier-philosophy hard caps to the weighted score.

    Two independent caps are read from ``integrity_overrides``:

    * missing verified independent secondary barrier -> cap (default 59.0),
    * failed/unverified primary barrier -> cap (default 39.0).

    The most restrictive applicable cap wins; a strong weighted score cannot
    mask a missing critical barrier.

    Args:
        weighted_score: The pre-override weighted aggregate (0-100).
        has_verified_secondary: Whether a verified secondary barrier exists.
        primary_failed_or_unverified: Whether the primary envelope is unreliable.

    Returns:
        ``(final_score, trace)`` after applying any caps.
    """
    overrides = integrity_overrides()
    secondary_cap = overrides["missing_verified_secondary_barrier_cap"]
    primary_cap = overrides["failed_or_unverified_primary_cap"]

    applied: list[dict[str, Any]] = []
    final_score = weighted_score

    if not has_verified_secondary:
        applied.append(
            {
                "rule": "missing_verified_secondary_barrier_cap",
                "cap": secondary_cap,
                "triggered": True,
            }
        )
        final_score = min(final_score, secondary_cap)

    if primary_failed_or_unverified:
        applied.append(
            {
                "rule": "failed_or_unverified_primary_cap",
                "cap": primary_cap,
                "triggered": True,
            }
        )
        final_score = min(final_score, primary_cap)

    trace = {
        "pre_override_score": round_score(weighted_score),
        "applied_overrides": applied,
        "post_override_score": round_score(clamp(final_score)),
    }
    return round_score(clamp(final_score)), trace


def assign_category(score: float) -> IntegrityCategory:
    """Map an overall integrity score to its qualitative category.

    Boundaries are inclusive lower bounds read from
    ``integrity_category_thresholds``.

    Args:
        score: Overall integrity score (0-100).

    Returns:
        The matching :class:`IntegrityCategory`.
    """
    thresholds = load_thresholds()["integrity_category_thresholds"]
    # Evaluate highest band first.
    ordered = sorted(
        thresholds.items(), key=lambda kv: kv[1]["min"], reverse=True
    )
    for name, band in ordered:
        if score >= band["min"]:
            return IntegrityCategory(name)
    return IntegrityCategory.FAILED  # pragma: no cover - failed.min is 0.0


def generate_flags(
    well: WellData,
    component_scores: dict[str, float],
    *,
    has_verified_secondary: bool,
    primary_failed_or_unverified: bool,
) -> tuple[str, ...]:
    """Derive human-readable flags for notable integrity findings.

    Args:
        well: The assessed well.
        component_scores: Final component scores (0-100).
        has_verified_secondary: Whether a verified secondary barrier exists.
        primary_failed_or_unverified: Whether the primary envelope is unreliable.

    Returns:
        An ordered, de-duplicated tuple of flag strings.
    """
    flags: list[str] = []

    primaries = [b for b in well.barriers if b.barrier_type is BarrierType.PRIMARY]
    secondaries = [b for b in well.barriers if b.barrier_type is BarrierType.SECONDARY]

    if not primaries:
        flags.append("No primary barrier recorded.")
    if not secondaries:
        flags.append("No secondary barrier recorded.")
    if secondaries and not has_verified_secondary:
        flags.append("Secondary barrier present but not independently verified.")
    if primary_failed_or_unverified and primaries:
        flags.append("Primary barrier failed or unverified.")

    if not has_verified_secondary:
        flags.append(
            "Overall integrity capped: no verified independent secondary barrier."
        )
    if primary_failed_or_unverified:
        flags.append("Overall integrity capped: primary envelope unreliable.")

    if well.is_abandoned and component_scores[IntegrityComponent.PLUGGING.value] == 0.0:
        flags.append("Abandoned well with no creditable plugging.")

    if not well.casing_strings:
        flags.append("No casing strings recorded; mechanical integrity uncertain.")

    # Low component scores worth surfacing individually.
    if component_scores[IntegrityComponent.CEMENT_QUALITY.value] < 40.0:
        flags.append("Cement quality below adequate threshold.")
    if component_scores[IntegrityComponent.MECHANICAL_INTEGRITY.value] < 40.0:
        flags.append("Mechanical integrity below adequate threshold.")

    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for f in flags:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return tuple(unique)


def assess_integrity_traced(well: WellData) -> tuple[IntegrityResult, dict[str, Any]]:
    """Assess integrity and return both the result and its full trace.

    Args:
        well: The well to assess.

    Returns:
        ``(result, trace)``. The ``trace`` is the complete, nested derivation
        suitable for audit, publication appendices, and report generation.
    """
    primary_score, primary_trace = evaluate_primary_barrier(
        well.barriers, well.total_depth_m
    )
    secondary_score, secondary_trace = evaluate_secondary_barrier(
        well.barriers, well.total_depth_m
    )
    cement_score, cement_trace = evaluate_cement_quality(
        well.barriers, well.total_depth_m
    )
    mechanical_score, mechanical_trace = evaluate_mechanical_integrity(
        well.barriers, well.casing_strings, well.total_depth_m
    )
    plugging_score, plugging_trace = evaluate_plugging(
        well.barriers, well.total_depth_m, is_abandoned=well.is_abandoned
    )

    component_scores: dict[str, float] = {
        IntegrityComponent.PRIMARY_BARRIER.value: primary_score,
        IntegrityComponent.SECONDARY_BARRIER.value: secondary_score,
        IntegrityComponent.CEMENT_QUALITY.value: cement_score,
        IntegrityComponent.MECHANICAL_INTEGRITY.value: mechanical_score,
        IntegrityComponent.PLUGGING.value: plugging_score,
    }

    weighted_score, aggregate_trace = aggregate_components(component_scores)

    has_verified_secondary = has_verified_secondary_barrier(well.barriers)
    primary_unreliable = primary_is_failed_or_unverified(well.barriers)

    final_score, override_trace = apply_overrides(
        weighted_score,
        has_verified_secondary=has_verified_secondary,
        primary_failed_or_unverified=primary_unreliable,
    )

    category = assign_category(final_score)
    flags = generate_flags(
        well,
        component_scores,
        has_verified_secondary=has_verified_secondary,
        primary_failed_or_unverified=primary_unreliable,
    )

    result = IntegrityResult(
        well_id=well.well_id,
        primary_barrier_score=primary_score,
        secondary_barrier_score=secondary_score,
        cement_quality_score=cement_score,
        mechanical_integrity_score=mechanical_score,
        plugging_score=plugging_score,
        overall_integrity_score=final_score,
        integrity_category=category,
        flags=flags,
        component_breakdown=dict(component_scores),
    )

    trace: dict[str, Any] = {
        "well_id": well.well_id,
        "components": {
            IntegrityComponent.PRIMARY_BARRIER.value: primary_trace,
            IntegrityComponent.SECONDARY_BARRIER.value: secondary_trace,
            IntegrityComponent.CEMENT_QUALITY.value: cement_trace,
            IntegrityComponent.MECHANICAL_INTEGRITY.value: mechanical_trace,
            IntegrityComponent.PLUGGING.value: plugging_trace,
        },
        "aggregation": aggregate_trace,
        "overrides": override_trace,
        "predicates": {
            "has_verified_secondary_barrier": has_verified_secondary,
            "primary_failed_or_unverified": primary_unreliable,
        },
        "category": category.value,
        "flags": list(flags),
        "overall_integrity_score": final_score,
    }
    return result, trace


def assess_integrity(well: WellData) -> IntegrityResult:
    """Assess the integrity of a single well.

    This is the primary public entry point of the integrity engine. It is a
    pure, deterministic function of ``well`` and the externalised configuration.

    Args:
        well: The well to assess.

    Returns:
        A fully populated, immutable :class:`IntegrityResult`.
    """
    result, _ = assess_integrity_traced(well)
    return result
