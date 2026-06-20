"""Cement quality assessment.

Scores the annular cement that creates the zonal seal across the caprock and
formation contacts. Under well-barrier philosophy, continuity of the annular
seal is second only to the source-facing barrier itself, which is why cement
carries the second-largest integrity weight.

The cement score blends two ideas:

* **Condition** -- the (verification-discounted) mean condition of the cement
  barrier elements, on a 0-100 scale.
* **Coverage** -- how much of the credited sealing interval is actually spanned
  by cement. Partial coverage is penalised because a gap in the annular seal is
  a direct leakage pathway regardless of how good the cement is elsewhere.

The two are combined multiplicatively via a coverage modifier
``(0.5 + 0.5 * coverage)`` so that perfect coverage preserves the condition
score, while zero coverage halves it. The sealing interval is taken as the span
of the cement elements themselves when no explicit caprock window is supplied;
this keeps the function self-contained while remaining auditable.
"""

from __future__ import annotations

from typing import Any

from lwra.integrity_engine._scoring import (
    clamp,
    condition_to_score,
    integrity_overrides,
    interval_coverage_fraction,
    round_score,
    verification_factor,
)
from lwra.models.barrier import BarrierData
from lwra.models.enums import BarrierElement

__all__ = ["evaluate_cement_quality"]


def evaluate_cement_quality(
    barriers: tuple[BarrierData, ...],
    total_depth_m: float,
    *,
    caprock_top_m: float | None = None,
    caprock_bottom_m: float | None = None,
) -> tuple[float, dict[str, Any]]:
    """Evaluate the cement quality component.

    Args:
        barriers: All barriers observed in the well. Cement elements are
            selected by ``element == BarrierElement.CEMENT``.
        total_depth_m: Total measured depth of the well (m).
        caprock_top_m: Optional top of the critical sealing window (m). When
            omitted, the span of the cement elements is used as the target.
        caprock_bottom_m: Optional bottom of the critical sealing window (m).

    Returns:
        ``(cement_quality_score, trace)`` on a 0-100 scale. With no cement
        elements the score is 0.0 and the trace records the absence.
    """
    overrides = integrity_overrides()
    low_conf = overrides["low_confidence_condition_threshold"]

    cement = [b for b in barriers if b.element is BarrierElement.CEMENT]

    if not cement:
        return 0.0, {
            "component": "cement_quality",
            "cement_element_count": 0,
            "elements": [],
            "note": "no cement barrier elements present -> score 0.0",
            "cement_quality_score": 0.0,
            "total_depth_m": total_depth_m,
        }

    # Per-element condition scores with verification discount.
    fragments: list[dict[str, Any]] = []
    raw_lengths: list[float] = []          # unrounded, used for the weighted mean
    intervals: list[tuple[float, float]] = []
    for b in cement:
        base = condition_to_score(b.condition_score)
        vfactor = verification_factor(
            verified=b.verified,
            condition=b.condition_score,
            low_confidence_threshold=low_conf,
        )
        element_score = clamp(base * vfactor)
        length_m = b.depth_bottom_m - b.depth_top_m
        raw_lengths.append(length_m)
        intervals.append((b.depth_top_m, b.depth_bottom_m))
        fragments.append(
            {
                "barrier_id": b.barrier_id,
                "raw_condition": b.condition_score,
                "verified": b.verified,
                "base_score": round_score(base),
                "verification_factor": round_score(vfactor),
                "interval_top_m": b.depth_top_m,
                "interval_bottom_m": b.depth_bottom_m,
                "interval_length_m": round_score(length_m),
                "element_score": round_score(element_score),
            }
        )

    # Length-weighted mean condition — use raw (unrounded) lengths so that
    # very short intervals are not zeroed by rounding before the sum.
    total_length = sum(raw_lengths)
    if total_length > 0:
        condition_component = clamp(
            sum(f["element_score"] * l for f, l in zip(fragments, raw_lengths))
            / total_length
        )
    else:  # pragma: no cover - guarded by model validation
        condition_component = clamp(
            sum(f["element_score"] for f in fragments) / len(fragments)
        )

    # Determine the target sealing window.
    if caprock_top_m is not None and caprock_bottom_m is not None:
        target_top, target_bottom = caprock_top_m, caprock_bottom_m
        window_source = "explicit caprock window"
    else:
        target_top = min(b.depth_top_m for b in cement)
        target_bottom = max(b.depth_bottom_m for b in cement)
        window_source = "span of cement elements (no explicit caprock window)"

    coverage = interval_coverage_fraction(intervals, target_top, target_bottom)
    coverage_modifier = 0.5 + 0.5 * coverage
    cement_score = clamp(condition_component * coverage_modifier)

    trace: dict[str, Any] = {
        "component": "cement_quality",
        "cement_element_count": len(cement),
        "elements": fragments,
        "total_interval_length_m": round_score(total_length),
        "condition_component": round_score(condition_component),
        "sealing_window_top_m": target_top,
        "sealing_window_bottom_m": target_bottom,
        "sealing_window_source": window_source,
        "coverage_fraction": round_score(coverage),
        "coverage_modifier": round_score(coverage_modifier),
        "formula": "condition_component * (0.5 + 0.5 * coverage_fraction)",
        "cement_quality_score": round_score(cement_score),
        "total_depth_m": total_depth_m,
    }
    return round_score(cement_score), trace
