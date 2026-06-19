"""Shared theming and helpers for the visualization layer.

Centralises the colour vocabulary, label formatting, and common layout defaults
used by every chart module (``gauges``, ``radar``, ``heatmap``, ``bars``) so the
figures are visually consistent and the styling lives in exactly one place.

This module contains **no business logic**. It maps the qualitative enums
produced by the engines onto colours and human-readable labels and applies a
neutral, export-friendly layout that renders identically in Streamlit, static
PNG/PDF export (via Kaleido), and embedded HTML.

All functions are pure: figure construction never mutates the result objects it
reads.
"""

from __future__ import annotations

from typing import Final

import plotly.graph_objects as go

from lwra.models.enums import IntegrityCategory, RiskCategory

__all__ = [
    "INTEGRITY_CATEGORY_COLORS",
    "RISK_CATEGORY_COLORS",
    "RISK_LEVEL_SCALE",
    "COMPONENT_LABELS",
    "FACTOR_LABELS",
    "PRETTY",
    "prettify_key",
    "base_layout",
    "apply_base_layout",
]

# -----------------------------------------------------------------------------
# Colour vocabulary
# -----------------------------------------------------------------------------
# Integrity: higher is better, so the palette runs green (good) -> red (failed).
INTEGRITY_CATEGORY_COLORS: Final[dict[IntegrityCategory, str]] = {
    IntegrityCategory.GOOD: "#1a9850",
    IntegrityCategory.MODERATE: "#a6d96a",
    IntegrityCategory.POOR: "#fdae61",
    IntegrityCategory.FAILED: "#d73027",
}

# Risk: higher is worse, so the palette runs green (low) -> dark red (critical).
RISK_CATEGORY_COLORS: Final[dict[RiskCategory, str]] = {
    RiskCategory.LOW: "#1a9850",
    RiskCategory.MEDIUM: "#fee08b",
    RiskCategory.HIGH: "#fc8d59",
    RiskCategory.CRITICAL: "#d73027",
}

# A 0-100 continuous scale used for the risk gauge steps and the matrix heatmap,
# expressed as (fraction, colour) stops from low to high risk.
RISK_LEVEL_SCALE: Final[tuple[tuple[float, str], ...]] = (
    (0.00, "#1a9850"),
    (0.25, "#d9ef8b"),
    (0.50, "#fee08b"),
    (0.75, "#fc8d59"),
    (1.00, "#d73027"),
)

# -----------------------------------------------------------------------------
# Label vocabulary
# -----------------------------------------------------------------------------
# Maps the integrity component keys (as found in
# IntegrityResult.component_breakdown) to display labels.
COMPONENT_LABELS: Final[dict[str, str]] = {
    "primary_barrier": "Primary Barrier",
    "secondary_barrier": "Secondary Barrier",
    "cement_quality": "Cement Quality",
    "mechanical_integrity": "Mechanical Integrity",
    "plugging": "Plugging",
}

# Maps the risk factor keys (as found in RiskResult.weighted_factors) to labels.
FACTOR_LABELS: Final[dict[str, str]] = {
    "integrity_score": "Integrity (inverse)",
    "well_age": "Well Age",
    "reservoir_pressure": "Reservoir Pressure",
    "temperature": "Temperature",
    "fluid_hazard": "Fluid Hazard",
    "proximity_to_receptors": "Proximity to Receptors",
    "data_uncertainty": "Data Uncertainty",
}

# Combined lookup for any known key.
PRETTY: Final[dict[str, str]] = {**COMPONENT_LABELS, **FACTOR_LABELS}


def prettify_key(key: str) -> str:
    """Return a human-readable label for a component or factor key.

    Falls back to a title-cased, underscore-stripped rendering when the key is
    not in the known vocabulary, so the function never fails on an unexpected
    key (e.g. a newly added factor).

    Args:
        key: A component or factor key (e.g. ``"cement_quality"``).

    Returns:
        A display label (e.g. ``"Cement Quality"``).
    """
    return PRETTY.get(key, key.replace("_", " ").title())


def base_layout(title: str, *, height: int = 400, width: int | None = None) -> go.Layout:
    """Build the shared base layout for a figure.

    Uses a transparent background and generous margins so figures embed cleanly
    in Streamlit, HTML, and paginated PDF reports, and export crisply to PNG.

    Args:
        title: The figure title.
        height: Figure height in pixels.
        width: Optional fixed width in pixels. Left unset for responsive
            containers (Streamlit) unless a report needs a fixed canvas.

    Returns:
        A configured :class:`plotly.graph_objects.Layout`.
    """
    layout = go.Layout(
        title={"text": title, "x": 0.5, "xanchor": "center"},
        height=height,
        margin={"l": 60, "r": 40, "t": 70, "b": 60},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Helvetica, Arial, sans-serif", "size": 13},
        template="plotly_white",
    )
    if width is not None:
        layout.width = width
    return layout


def apply_base_layout(
    fig: go.Figure,
    title: str,
    *,
    height: int = 400,
    width: int | None = None,
) -> go.Figure:
    """Apply the shared base layout to an existing figure in place.

    Args:
        fig: The figure to style.
        title: The figure title.
        height: Figure height in pixels.
        width: Optional fixed width in pixels.

    Returns:
        The same figure, restyled (returned for fluent chaining).
    """
    fig.update_layout(base_layout(title, height=height, width=width))
    return fig
