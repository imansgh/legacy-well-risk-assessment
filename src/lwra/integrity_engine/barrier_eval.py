"""Primary and secondary barrier evaluation.

Scores the two engineered envelopes of the well-barrier philosophy:

* the **primary** (source-facing) barrier, and
* the **secondary** (independent backup) barrier.

Both evaluators are pure functions: they take the well's barriers and the
well's total depth and return a 0-100 component score plus a fully expanded
calculation trace. They never mutate inputs and never read global state beyond
the cached, deterministic configuration.

Scoring model (identical shape for both roles):

    raw_condition (0-1)
        -> condition_to_score (0-100)
        -> x verification_factor (trust discount)
        -> x (0.5 + 0.5 * interval_coverage)   # coverage modifier
        -> weighted by each barrier's interval length within the role

When several barriers share a role, the role score is the
interval-length-weighted mean of the individual barrier scores, so a long,
well-characterised barrier counts for more than a short one. With no barriers
in a role the score is 0.0 and a flag is raised by the aggregator.
"""

from __future__ import annotations

from typing import Any

from lwra.integrity_engine._scoring import (
    clamp,
    condition_to_score,
    integrity_overrides,
    round_score,
    verification_factor,
)
from lwra.models.barrier import BarrierData
from lwra.models.enums import BarrierType

__all__ = [
    "evaluate_primary_barrier",
    "evaluate_secondary_barrier",
    "evaluate_barrier_role",
    "has_verified_secondary_barrier",
    "primary_is_failed_or_unverified",
]

# A primary barrier is considered "failed" when its raw condition is at or
# below this fraction; combined with verification, this drives the override.
_PRIMARY_FAILED_CONDITION: float = 0.40


def _barrier_score(
    barrier: BarrierData,
    *,
    low_confidence_threshold: float,
) -> dict[str, Any]:
    """Score a single barrier and return its trace fragment.

    Args:
        barrier: The barrier to score.
        low_confidence_threshold: Verified-but-low-confidence cutoff.

    Returns:
        A trace dict containing the inputs and every intermediate quantity.

    """
    base = condition_to_score(barrier.condition_score)
    vfactor = verification_factor(
        verified=barrier.verified,
        condition=barrier.condition_score,
        low_confidence_threshold=low_confidence_threshold,
    )
    # Coverage of the barrier's own interval is, by definition, complete; the
    # coverage modifier here rewards longer credited intervals indirectly via
    # length weighting in the role aggregation. We still expose the interval.
    length_m = barrier.depth_bottom_m - barrier.depth_top_m
    score = clamp(base * vfactor)
    return {
        "barrier_id": barrier.barrier_id,
        "element": barrier.element.value,
        "raw_condition": barrier.condition_score,
        "verified": barrier.verified,
        "base_score": round_score(base),
        "verification_factor": round_score(vfactor),
        "interval_top_m": barrier.depth_top_m,
        "interval_bottom_m": barrier.depth_bottom_m,
        "interval_length_m": round_score(length_m),
        "barrier_score": round_score(score),
    }


def evaluate_barrier_role(
    barriers: tuple[BarrierData, ...],
    role: BarrierType,
) -> tuple[float, dict[str, Any]]:
    """Evaluate all barriers of a given role into one 0-100 score.

    The role score is the interval-length-weighted mean of the individual
    barrier scores. Length weighting means a barrier sealing a long interval
    contributes proportionally more than a short one.

    Args:
        barriers: All barriers observed in the well.
        role: ``BarrierType.PRIMARY`` or ``BarrierType.SECONDARY``.

    Returns:
        A tuple of ``(role_score, trace)`` where ``trace`` records every
        per-barrier fragment and the aggregation arithmetic.

    """
    overrides = integrity_overrides()
    low_conf = overrides["low_confidence_condition_threshold"]

    role_barriers = [b for b in barriers if b.barrier_type is role]
    fragments = [_barrier_score(b, low_confidence_threshold=low_conf) for b in role_barriers]

    if not fragments:
        trace: dict[str, Any] = {
            "role": role.value,
            "barrier_count": 0,
            "barriers": [],
            "aggregation": "none (no barriers in role -> score 0.0)",
            "role_score": 0.0,
        }
        return 0.0, trace

    # Derive raw lengths from the source barriers (not from the rounded values
    # stored in the trace fragments) so very short intervals are not zeroed.
    raw_lengths = [b.depth_bottom_m - b.depth_top_m for b in role_barriers]
    total_length = sum(raw_lengths)
    if total_length > 0:
        weighted = sum(
            f["barrier_score"] * length for f, length in zip(fragments, raw_lengths, strict=False)
        )
        role_score = clamp(weighted / total_length)
        aggregation = "interval-length-weighted mean"
    else:  # pragma: no cover - guarded by model validation (bottom > top)
        role_score = clamp(sum(f["barrier_score"] for f in fragments) / len(fragments))
        aggregation = "arithmetic mean (zero total length fallback)"

    trace = {
        "role": role.value,
        "barrier_count": len(fragments),
        "barriers": fragments,
        "total_interval_length_m": round_score(total_length),
        "aggregation": aggregation,
        "role_score": round_score(role_score),
    }
    return round_score(role_score), trace


def evaluate_primary_barrier(
    barriers: tuple[BarrierData, ...],
    total_depth_m: float,
) -> tuple[float, dict[str, Any]]:
    """Evaluate the primary (source-facing) barrier component.

    Args:
        barriers: All barriers observed in the well.
        total_depth_m: Total measured depth of the well (m), retained in the
            trace for context and future depth-aware refinements.

    Returns:
        ``(primary_barrier_score, trace)`` on a 0-100 scale.

    """
    score, trace = evaluate_barrier_role(barriers, BarrierType.PRIMARY)
    trace["component"] = "primary_barrier"
    trace["total_depth_m"] = total_depth_m
    return score, trace


def evaluate_secondary_barrier(
    barriers: tuple[BarrierData, ...],
    total_depth_m: float,
) -> tuple[float, dict[str, Any]]:
    """Evaluate the secondary (independent backup) barrier component.

    Args:
        barriers: All barriers observed in the well.
        total_depth_m: Total measured depth of the well (m), retained in the
            trace for context.

    Returns:
        ``(secondary_barrier_score, trace)`` on a 0-100 scale.

    """
    score, trace = evaluate_barrier_role(barriers, BarrierType.SECONDARY)
    trace["component"] = "secondary_barrier"
    trace["total_depth_m"] = total_depth_m
    return score, trace


def has_verified_secondary_barrier(barriers: tuple[BarrierData, ...]) -> bool:
    """Whether at least one independently verified secondary barrier exists.

    This is the predicate behind the missing-secondary-barrier override.

    Args:
        barriers: All barriers observed in the well.

    Returns:
        ``True`` if any secondary barrier is marked verified.

    """
    return any(b.barrier_type is BarrierType.SECONDARY and b.verified for b in barriers)


def primary_is_failed_or_unverified(barriers: tuple[BarrierData, ...]) -> bool:
    """Whether the primary envelope cannot be relied upon.

    The primary barrier is treated as failed/unverified -- and thus triggers
    the hard cap -- when there is **no** primary barrier at all, or when **no**
    primary barrier is both verified and above the failed-condition threshold.

    Args:
        barriers: All barriers observed in the well.

    Returns:
        ``True`` if no credible, verified primary barrier exists.

    """
    primaries = [b for b in barriers if b.barrier_type is BarrierType.PRIMARY]
    if not primaries:
        return True
    return not any(b.verified and b.condition_score > _PRIMARY_FAILED_CONDITION for b in primaries)
