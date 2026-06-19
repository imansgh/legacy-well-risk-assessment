"""Plugging condition assessment.

Scores the abandonment plugs that provide the controlling long-term barrier in
a permanently abandoned well. For abandoned wells, plug competence frequently
governs whether the well can be trusted decades after operations cease, which
is why plugging is scored as its own component.

The component blends:

* **Condition** -- verification-discounted, length-weighted mean condition of
  the plug elements (0-100), and
* **Length adequacy** -- a modifier rewarding plugs whose combined length meets
  an adequacy reference, since a competent cement plug needs sufficient set
  length to seal reliably.

Context handling:

* A well **with** a recorded abandonment date but **no** plug elements is a
  serious finding: the score is 0.0 (the abandonment cannot be credited).
* A well that is **not** abandoned and has no plugs is scored at a neutral
  ``not-applicable`` baseline rather than penalised, because plugging is simply
  not yet expected. The aggregator down-weights/flags as appropriate.
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
from lwra.models.enums import BarrierElement

__all__ = ["evaluate_plugging"]

# Reference combined plug length (m) at/above which length is fully adequate.
# Inspired by typical abandonment plug-length practice; tunable in future
# config. The modifier scales linearly from a floor up to 1.0 at this length.
_ADEQUATE_PLUG_LENGTH_M: float = 30.0

# Floor of the length-adequacy modifier (so a short plug is penalised but a
# present plug never scores zero on length alone).
_LENGTH_MODIFIER_FLOOR: float = 0.5

# Neutral baseline for a non-abandoned well with no plugs (plugging not yet
# expected). Down-weighted to reflect "not applicable / not yet performed".
_NOT_APPLICABLE_BASELINE: float = 60.0


def evaluate_plugging(
    barriers: tuple[BarrierData, ...],
    total_depth_m: float,
    *,
    is_abandoned: bool,
) -> tuple[float, dict[str, Any]]:
    """Evaluate the plugging condition component.

    Args:
        barriers: All barriers observed in the well; plug elements are selected
            via ``element == BarrierElement.PLUG``.
        total_depth_m: Total measured depth of the well (m).
        is_abandoned: Whether the well has a recorded abandonment date. Drives
            the no-plug handling (penalise vs. treat as not-yet-applicable).

    Returns:
        ``(plugging_score, trace)`` on a 0-100 scale.
    """
    overrides = integrity_overrides()
    low_conf = overrides["low_confidence_condition_threshold"]

    plugs = [b for b in barriers if b.element is BarrierElement.PLUG]

    if not plugs:
        if is_abandoned:
            return 0.0, {
                "component": "plugging",
                "plug_count": 0,
                "is_abandoned": True,
                "note": (
                    "well recorded as abandoned but no plug elements present "
                    "-> abandonment cannot be credited -> score 0.0"
                ),
                "plugging_score": 0.0,
                "total_depth_m": total_depth_m,
            }
        return round_score(_NOT_APPLICABLE_BASELINE), {
            "component": "plugging",
            "plug_count": 0,
            "is_abandoned": False,
            "note": (
                "well not abandoned and no plugs -> plugging not yet expected "
                f"-> neutral baseline {_NOT_APPLICABLE_BASELINE}"
            ),
            "plugging_score": round_score(_NOT_APPLICABLE_BASELINE),
            "total_depth_m": total_depth_m,
        }

    fragments: list[dict[str, Any]] = []
    for b in plugs:
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
        condition_component = clamp(
            sum(f["element_score"] * f["interval_length_m"] for f in fragments)
            / total_length
        )
    else:  # pragma: no cover - guarded by model validation
        condition_component = clamp(
            sum(f["element_score"] for f in fragments) / len(fragments)
        )

    # Length adequacy modifier in [floor, 1.0].
    length_ratio = clamp(total_length / _ADEQUATE_PLUG_LENGTH_M, 0.0, 1.0)
    length_modifier = _LENGTH_MODIFIER_FLOOR + (1.0 - _LENGTH_MODIFIER_FLOOR) * length_ratio
    plugging_score = clamp(condition_component * length_modifier)

    trace: dict[str, Any] = {
        "component": "plugging",
        "plug_count": len(plugs),
        "is_abandoned": is_abandoned,
        "elements": fragments,
        "total_plug_length_m": round_score(total_length),
        "condition_component": round_score(condition_component),
        "adequate_plug_length_m": _ADEQUATE_PLUG_LENGTH_M,
        "length_ratio": round_score(length_ratio),
        "length_modifier": round_score(length_modifier),
        "formula": "condition_component * length_modifier",
        "plugging_score": round_score(plugging_score),
        "total_depth_m": total_depth_m,
    }
    return round_score(plugging_score), trace
