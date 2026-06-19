"""Radar (spider) chart of the integrity component scores.

Plots the five integrity components on a common 0-100 radial axis so the
weakest link in a well's barrier system is obvious at a glance, and supports
overlaying several wells for side-by-side portfolio comparison.

Pure functions: they read immutable result objects and return a new
:class:`plotly.graph_objects.Figure`. No business logic; component scores are
taken verbatim from ``IntegrityResult.component_breakdown``.
"""

from __future__ import annotations

from collections.abc import Sequence

import plotly.graph_objects as go

from lwra.models.results import IntegrityResult
from lwra.services.pipeline import WellAssessment
from lwra.visualizations._theme import (
    COMPONENT_LABELS,
    INTEGRITY_CATEGORY_COLORS,
    apply_base_layout,
    prettify_key,
)

__all__ = [
    "component_radar",
    "component_radar_from_assessment",
    "portfolio_radar",
]

# Canonical component order around the radar (clockwise from the top). Fixing
# the order keeps the shape comparable across wells.
_COMPONENT_ORDER: tuple[str, ...] = (
    "primary_barrier",
    "secondary_barrier",
    "cement_quality",
    "mechanical_integrity",
    "plugging",
)


def _ordered_scores(integrity: IntegrityResult) -> tuple[list[str], list[float]]:
    """Extract component labels and scores in the canonical radar order.

    Args:
        integrity: The integrity result.

    Returns:
        ``(labels, values)`` aligned to :data:`_COMPONENT_ORDER`. Components
        absent from the breakdown default to 0.0 so the trace stays closed.
    """
    breakdown = integrity.component_breakdown
    labels = [COMPONENT_LABELS.get(k, prettify_key(k)) for k in _COMPONENT_ORDER]
    values = [float(breakdown.get(k, 0.0)) for k in _COMPONENT_ORDER]
    return labels, values


def _close_loop(labels: list[str], values: list[float]) -> tuple[list[str], list[float]]:
    """Repeat the first point at the end so the radar polygon closes.

    Args:
        labels: Axis category labels.
        values: Radial values.

    Returns:
        ``(labels, values)`` with the first element appended to each.
    """
    return labels + labels[:1], values + values[:1]


def component_radar(
    integrity: IntegrityResult,
    *,
    name: str | None = None,
    height: int = 460,
    width: int | None = None,
) -> go.Figure:
    """Build a single-well integrity component radar.

    Args:
        integrity: The integrity result to visualise.
        name: Optional trace/legend name; defaults to the well id.
        height: Figure height in pixels.
        width: Optional fixed width in pixels.

    Returns:
        A radar figure with the five components on a 0-100 radial axis, filled
        and coloured by the well's integrity category.
    """
    labels, values = _ordered_scores(integrity)
    theta, r = _close_loop(labels, values)
    color = INTEGRITY_CATEGORY_COLORS[integrity.integrity_category]

    fig = go.Figure(
        go.Scatterpolar(
            r=r,
            theta=theta,
            fill="toself",
            name=name or integrity.well_id,
            line={"color": color},
            fillcolor=color,
            opacity=0.55,
            hovertemplate="%{theta}: %{r:.1f}/100<extra></extra>",
        )
    )
    fig.update_polars(radialaxis={"range": [0, 100], "tickvals": [0, 25, 50, 75, 100]})
    return apply_base_layout(
        fig, f"Integrity Components: {integrity.well_id}", height=height, width=width
    )


def component_radar_from_assessment(
    assessment: WellAssessment,
    *,
    height: int = 460,
    width: int | None = None,
) -> go.Figure:
    """Build the component radar directly from a :class:`WellAssessment`.

    Args:
        assessment: The complete well assessment.
        height: Figure height in pixels.
        width: Optional fixed width in pixels.

    Returns:
        The integrity component radar for the assessment.
    """
    return component_radar(assessment.integrity, height=height, width=width)


def portfolio_radar(
    assessments: Sequence[WellAssessment],
    *,
    height: int = 520,
    width: int | None = None,
    max_wells: int = 12,
) -> go.Figure:
    """Overlay integrity component radars for several wells.

    Each well becomes one filled, semi-transparent trace so their barrier
    profiles can be compared directly. Intended for batch portfolio screening.

    Args:
        assessments: The well assessments to overlay.
        height: Figure height in pixels.
        width: Optional fixed width in pixels.
        max_wells: Soft cap on the number of overlaid traces to keep the chart
            legible; wells beyond this count are not plotted.

    Returns:
        A radar figure overlaying one trace per well (up to ``max_wells``).

    Raises:
        ValueError: If ``assessments`` is empty.
    """
    if not assessments:
        raise ValueError("portfolio_radar requires at least one assessment.")

    fig = go.Figure()
    for assessment in list(assessments)[:max_wells]:
        labels, values = _ordered_scores(assessment.integrity)
        theta, r = _close_loop(labels, values)
        fig.add_trace(
            go.Scatterpolar(
                r=r,
                theta=theta,
                fill="toself",
                name=assessment.well_id,
                opacity=0.40,
                hovertemplate=(
                    f"{assessment.well_id}<br>%{{theta}}: %{{r:.1f}}/100<extra></extra>"
                ),
            )
        )
    fig.update_polars(radialaxis={"range": [0, 100], "tickvals": [0, 25, 50, 75, 100]})
    fig.update_layout(showlegend=True)
    return apply_base_layout(
        fig, "Portfolio Integrity Components", height=height, width=width
    )
