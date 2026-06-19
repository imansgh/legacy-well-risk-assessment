"""Gauge charts for the overall integrity and risk scores.

Two single-value dials, colour-banded by qualitative category, suitable for the
headline figures on a Streamlit dashboard or the summary page of a PDF report.

Both functions are pure: they read an immutable result object (or the
:class:`~lwra.services.pipeline.WellAssessment` that wraps it) and return a new
:class:`plotly.graph_objects.Figure`. They contain no business logic -- the
score and category are taken verbatim from the result.
"""

from __future__ import annotations

import plotly.graph_objects as go

from lwra.models.results import IntegrityResult, RiskResult
from lwra.services.pipeline import WellAssessment
from lwra.visualizations._theme import (
    INTEGRITY_CATEGORY_COLORS,
    RISK_CATEGORY_COLORS,
    apply_base_layout,
)

__all__ = [
    "integrity_gauge",
    "risk_gauge",
    "integrity_gauge_from_assessment",
    "risk_gauge_from_assessment",
]

# Integrity band edges (0-100, higher better) mirroring
# integrity_category_thresholds; used only to colour the gauge backdrop.
_INTEGRITY_STEPS: tuple[tuple[float, float, str], ...] = (
    (0.0, 40.0, "#d73027"),    # failed
    (40.0, 60.0, "#fdae61"),   # poor
    (60.0, 80.0, "#a6d96a"),   # moderate
    (80.0, 100.0, "#1a9850"),  # good
)

# Risk band edges (0-100, higher worse) mirroring risk_category_thresholds.
_RISK_STEPS: tuple[tuple[float, float, str], ...] = (
    (0.0, 25.0, "#1a9850"),     # low
    (25.0, 50.0, "#fee08b"),    # medium
    (50.0, 75.0, "#fc8d59"),    # high
    (75.0, 100.0, "#d73027"),   # critical
)


def _gauge(
    *,
    value: float,
    title: str,
    bar_color: str,
    steps: tuple[tuple[float, float, str], ...],
    height: int,
    width: int | None,
) -> go.Figure:
    """Build a generic 0-100 gauge with coloured qualitative bands.

    Args:
        value: The score to display (0-100).
        title: The gauge title.
        bar_color: Colour of the value bar (the category colour).
        steps: ``(low, high, colour)`` band definitions for the backdrop.
        height: Figure height in pixels.
        width: Optional fixed width in pixels.

    Returns:
        A configured gauge :class:`plotly.graph_objects.Figure`.
    """
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={"suffix": " / 100", "font": {"size": 28}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1},
                "bar": {"color": bar_color, "thickness": 0.30},
                "steps": [
                    {"range": [lo, hi], "color": color} for lo, hi, color in steps
                ],
                "threshold": {
                    "line": {"color": "#222222", "width": 3},
                    "thickness": 0.80,
                    "value": value,
                },
            },
        )
    )
    return apply_base_layout(fig, title, height=height, width=width)


def integrity_gauge(
    integrity: IntegrityResult,
    *,
    height: int = 320,
    width: int | None = None,
) -> go.Figure:
    """Build the overall integrity gauge.

    Args:
        integrity: The integrity result to visualise.
        height: Figure height in pixels.
        width: Optional fixed width in pixels.

    Returns:
        A gauge figure for ``overall_integrity_score``, banded by category and
        with the value bar coloured by ``integrity_category``.
    """
    bar = INTEGRITY_CATEGORY_COLORS[integrity.integrity_category]
    title = (
        f"Integrity: {integrity.overall_integrity_score:.1f} "
        f"({integrity.integrity_category.value})"
    )
    return _gauge(
        value=integrity.overall_integrity_score,
        title=title,
        bar_color=bar,
        steps=_INTEGRITY_STEPS,
        height=height,
        width=width,
    )


def risk_gauge(
    risk: RiskResult,
    *,
    height: int = 320,
    width: int | None = None,
) -> go.Figure:
    """Build the overall risk gauge.

    Args:
        risk: The risk result to visualise.
        height: Figure height in pixels.
        width: Optional fixed width in pixels.

    Returns:
        A gauge figure for ``risk_score``, banded by category and with the value
        bar coloured by ``risk_category``.
    """
    bar = RISK_CATEGORY_COLORS[risk.risk_category]
    title = f"Risk: {risk.risk_score:.1f} ({risk.risk_category.value})"
    return _gauge(
        value=risk.risk_score,
        title=title,
        bar_color=bar,
        steps=_RISK_STEPS,
        height=height,
        width=width,
    )


def integrity_gauge_from_assessment(
    assessment: WellAssessment,
    *,
    height: int = 320,
    width: int | None = None,
) -> go.Figure:
    """Build the integrity gauge directly from a :class:`WellAssessment`.

    Args:
        assessment: The complete well assessment.
        height: Figure height in pixels.
        width: Optional fixed width in pixels.

    Returns:
        The integrity gauge figure for the assessment's integrity result.
    """
    return integrity_gauge(assessment.integrity, height=height, width=width)


def risk_gauge_from_assessment(
    assessment: WellAssessment,
    *,
    height: int = 320,
    width: int | None = None,
) -> go.Figure:
    """Build the risk gauge directly from a :class:`WellAssessment`.

    Args:
        assessment: The complete well assessment.
        height: Figure height in pixels.
        width: Optional fixed width in pixels.

    Returns:
        The risk gauge figure for the assessment's risk result.
    """
    return risk_gauge(assessment.risk, height=height, width=width)
