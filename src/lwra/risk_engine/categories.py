"""Risk category assignment and risk-matrix cell mapping.

Maps the scalar risk score to a qualitative :class:`RiskCategory` band, and
maps the (likelihood, consequence) pair onto discrete risk-matrix coordinates
suitable for the heatmap visualisation described in the architecture document.

Both functions are pure and deterministic, reading their boundaries from
``thresholds.yaml: risk_category_thresholds``.
"""

from __future__ import annotations

from typing import Any

from lwra.models.enums import RiskCategory
from lwra.risk_engine.weighting import clamp, load_thresholds

__all__ = [
    "assign_category",
    "matrix_coordinates",
    "MATRIX_SIZE",
]

# The risk matrix is a square grid. A 5x5 matrix is the de-facto standard in
# risk-based well-integrity practice (likelihood 1-5 vs consequence 1-5).
MATRIX_SIZE: int = 5


def assign_category(risk_score: float) -> RiskCategory:
    """Map an overall risk score to its qualitative category.

    Boundaries are inclusive lower bounds read from
    ``risk_category_thresholds``; the highest band whose ``min`` the score meets
    or exceeds wins.

    Args:
        risk_score: Overall risk score (0-100, higher is worse).

    Returns:
        The matching :class:`RiskCategory`.

    """
    thresholds = load_thresholds()["risk_category_thresholds"]
    ordered = sorted(thresholds.items(), key=lambda kv: kv[1]["min"], reverse=True)
    for name, band in ordered:
        if risk_score >= band["min"]:
            return RiskCategory(name)
    return RiskCategory.LOW  # pragma: no cover - low.min is 0.0


def _axis_bin(value: float, size: int = MATRIX_SIZE) -> int:
    """Bin a 0-100 axis value onto a 1..size integer matrix coordinate.

    Args:
        value: Axis value in [0, 100].
        size: Number of bins (matrix dimension).

    Returns:
        An integer in [1, size]. 100 maps to ``size`` (not ``size + 1``).

    """
    v = clamp(value)
    # Bin width is 100/size; floor into a bin then shift to 1-based, capping
    # the top edge (value == 100) into the highest bin.
    bin_index = int(v // (100.0 / size)) + 1
    return min(bin_index, size)


def matrix_coordinates(
    likelihood: float,
    consequence: float,
    *,
    size: int = MATRIX_SIZE,
) -> tuple[int, int, dict[str, Any]]:
    """Map (likelihood, consequence) onto discrete risk-matrix coordinates.

    The coordinates index a ``size x size`` heatmap cell, with 1 = lowest and
    ``size`` = highest on each axis. The trace records the continuous inputs and
    the binning so the placement is auditable.

    Args:
        likelihood: Likelihood axis value (0-100).
        consequence: Consequence axis value (0-100).
        size: Matrix dimension (defaults to :data:`MATRIX_SIZE`).

    Returns:
        ``(likelihood_bin, consequence_bin, trace)`` with 1-based bins.

    """
    l_bin = _axis_bin(likelihood, size)
    c_bin = _axis_bin(consequence, size)
    trace = {
        "matrix_size": size,
        "likelihood_value": likelihood,
        "consequence_value": consequence,
        "likelihood_bin": l_bin,
        "consequence_bin": c_bin,
        "cell": f"L{l_bin}-C{c_bin}",
        "bin_width": round(100.0 / size, 4),
    }
    return l_bin, c_bin, trace
