"""Mechanical integrity assessment.

Scores the load-bearing/pressure-containing hardware of the well: casing,
tubing, packers, and the wellhead. These elements do not by themselves
constitute the zonal seal, but their failure (corrosion, parted casing, leaking
packer or wellhead) undermines every barrier that relies on them.

The component is the verification-discounted, length-weighted mean condition of
all mechanical elements. A supporting signal -- the fraction of casing strings
recorded as cemented -- nudges the score, since an uncemented annulus offers no
mechanical support or secondary seal. With no mechanical elements present, the
score falls back to a conservative neutral value and a flag is surfaced by the
aggregator (absence of casing/tubing data is itself a finding).
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
from lwra.models.barrier import BarrierData, CasingString
from lwra.models.enums import BarrierElement

__all__ = ["evaluate_mechanical_integrity", "MECHANICAL_ELEMENTS"]

# Barrier elements considered "mechanical" for this component.
MECHANICAL_ELEMENTS: frozenset[BarrierElement] = frozenset(
    {
        BarrierElement.CASING,
        BarrierElement.TUBING,
        BarrierElement.PACKER,
        BarrierElement.WELLHEAD,
    }
)

# Conservative score used when no mechanical barrier elements are recorded.
# Not zero (absence of data is not proof of failure) but clearly sub-adequate
# so that the gap is reflected and flagged.
_NO_DATA_NEUTRAL: float = 50.0

# Maximum bonus/penalty applied from casing cementing ratio, in score points.
_CEMENTING_SWING: float = 10.0


def evaluate_mechanical_integrity(
    barriers: tuple[BarrierData, ...],
    casing_strings: tuple[CasingString, ...],
    total_depth_m: float,
) -> tuple[float, dict[str, Any]]:
    """Evaluate the mechanical integrity component.

    Args:
        barriers: All barriers observed in the well; mechanical elements are
            selected via :data:`MECHANICAL_ELEMENTS`.
        casing_strings: Installed casing strings; their cementing ratio
            provides a supporting adjustment.
        total_depth_m: Total measured depth of the well (m).

    Returns:
        ``(mechanical_integrity_score, trace)`` on a 0-100 scale.

    """
    overrides = integrity_overrides()
    low_conf = overrides["low_confidence_condition_threshold"]

    mech = [b for b in barriers if b.element in MECHANICAL_ELEMENTS]

    # Casing cementing ratio (supporting signal, computed regardless).
    if casing_strings:
        cemented = sum(1 for s in casing_strings if s.cemented)
        cementing_ratio = cemented / len(casing_strings)
    else:
        cemented = 0
        cementing_ratio = 0.0
    # Map ratio in [0,1] to an adjustment in [-swing, +swing] centred at 0.5.
    cementing_adjustment = (cementing_ratio - 0.5) * 2.0 * _CEMENTING_SWING

    if not mech:
        base_component = _NO_DATA_NEUTRAL
        mechanical_score = clamp(base_component + cementing_adjustment)
        return round_score(mechanical_score), {
            "component": "mechanical_integrity",
            "mechanical_element_count": 0,
            "elements": [],
            "note": (
                "no mechanical barrier elements present -> conservative "
                f"neutral base {_NO_DATA_NEUTRAL}"
            ),
            "base_component": _NO_DATA_NEUTRAL,
            "casing_string_count": len(casing_strings),
            "cemented_casing_count": cemented,
            "cementing_ratio": round_score(cementing_ratio),
            "cementing_adjustment": round_score(cementing_adjustment),
            "mechanical_integrity_score": round_score(mechanical_score),
            "total_depth_m": total_depth_m,
        }

    fragments: list[dict[str, Any]] = []
    for b in mech:
        base = condition_to_score(b.condition_score)
        vfactor = verification_factor(
            verified=b.verified,
            condition=b.condition_score,
            low_confidence_threshold=low_conf,
        )
        element_score = clamp(base * vfactor)
        length_m = b.depth_bottom_m - b.depth_top_m
        fragments.append(
            {
                "barrier_id": b.barrier_id,
                "element": b.element.value,
                "raw_condition": b.condition_score,
                "verified": b.verified,
                "base_score": round_score(base),
                "verification_factor": round_score(vfactor),
                "interval_length_m": round_score(length_m),
                "element_score": round_score(element_score),
            }
        )

    total_length = sum(f["interval_length_m"] for f in fragments)
    if total_length > 0:
        base_component = clamp(
            sum(f["element_score"] * f["interval_length_m"] for f in fragments) / total_length
        )
    else:  # pragma: no cover - guarded by model validation
        base_component = clamp(sum(f["element_score"] for f in fragments) / len(fragments))

    mechanical_score = clamp(base_component + cementing_adjustment)

    trace: dict[str, Any] = {
        "component": "mechanical_integrity",
        "mechanical_element_count": len(mech),
        "elements": fragments,
        "total_interval_length_m": round_score(total_length),
        "base_component": round_score(base_component),
        "casing_string_count": len(casing_strings),
        "cemented_casing_count": cemented,
        "cementing_ratio": round_score(cementing_ratio),
        "cementing_adjustment": round_score(cementing_adjustment),
        "formula": "length_weighted_condition + cementing_adjustment",
        "mechanical_integrity_score": round_score(mechanical_score),
        "total_depth_m": total_depth_m,
    }
    return round_score(mechanical_score), trace
