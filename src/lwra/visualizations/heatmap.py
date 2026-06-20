"""Risk-matrix heatmap (likelihood x consequence).

Renders the standard 5x5 risk matrix as a colour-graded heatmap and places the
well(s) in their cell(s). The matrix cell is read from
``RiskResult.calculation_trace`` (where the risk engine records it); if a trace
is unavailable the cell is reconstructed by binning the continuous likelihood
and consequence axes, so the function works on any result object.

Pure functions returning :class:`plotly.graph_objects.Figure`. No business
logic: the cell mapping mirrors the risk engine's binning but performs no
scoring.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import plotly.graph_objects as go

from lwra.models.results import RiskResult
from lwra.services.pipeline import WellAssessment
from lwra.visualizations._theme import apply_base_layout

__all__ = [
    "risk_matrix_heatmap",
    "risk_matrix_heatmap_from_assessment",
    "portfolio_risk_matrix",
]

# Matrix dimension. Mirrors lwra.risk_engine.categories.MATRIX_SIZE (the
# de-facto 5x5 standard); kept as a local constant so the visualization layer
# has no import-time dependency on engine internals.
_MATRIX_SIZE: int = 5


def _axis_bin(value: float, size: int = _MATRIX_SIZE) -> int:
    """Bin a 0-100 axis value onto a 1..size coordinate (matches the engine).

    Args:
        value: Axis value in [0, 100].
        size: Matrix dimension.

    Returns:
        An integer bin in [1, size].

    """
    v = max(0.0, min(100.0, value))
    return min(int(v // (100.0 / size)) + 1, size)


def _cell_from_risk(risk: RiskResult, size: int = _MATRIX_SIZE) -> tuple[int, int]:
    """Resolve the (likelihood_bin, consequence_bin) cell for a risk result.

    Prefers the bins recorded in ``calculation_trace`` (authoritative, produced
    by the engine); falls back to binning the continuous axes.

    Args:
        risk: The risk result.
        size: Matrix dimension.

    Returns:
        ``(likelihood_bin, consequence_bin)`` with 1-based coordinates.

    """
    trace: dict[str, Any] = risk.calculation_trace or {}
    coords = trace.get("matrix_coordinates")
    if isinstance(coords, dict) and "likelihood_bin" in coords and "consequence_bin" in coords:
        return int(coords["likelihood_bin"]), int(coords["consequence_bin"])
    return _axis_bin(risk.likelihood, size), _axis_bin(risk.consequence, size)


def _matrix_background(size: int = _MATRIX_SIZE) -> go.Heatmap:
    """Build the colour-graded matrix backdrop.

    Each cell's value is a normalised severity = (likelihood + consequence)
    product proxy, so the corner (high/high) is hottest. Returns a heatmap trace
    with the standard low->critical colour ramp.

    Args:
        size: Matrix dimension.

    Returns:
        A :class:`plotly.graph_objects.Heatmap` backdrop trace.

    """
    # Severity grid: combine the two 1..size axes into a 0-1 severity used only
    # for the backdrop colour. Product captures "both high" as the hot corner.
    z = [[(lv * c) / (size * size) for lv in range(1, size + 1)] for c in range(1, size + 1)]
    ticks = list(range(1, size + 1))
    return go.Heatmap(
        z=z,
        x=ticks,
        y=ticks,
        colorscale=[
            [0.00, "#1a9850"],
            [0.25, "#d9ef8b"],
            [0.50, "#fee08b"],
            [0.75, "#fc8d59"],
            [1.00, "#d73027"],
        ],
        showscale=False,
        hoverinfo="skip",
        xgap=2,
        ygap=2,
    )


def _axis_layout(fig: go.Figure, size: int = _MATRIX_SIZE) -> None:
    """Apply the shared matrix axis styling (1..size, labelled, square).

    Args:
        fig: The figure to style.
        size: Matrix dimension.

    """
    ticks = list(range(1, size + 1))
    fig.update_xaxes(
        title_text="Likelihood",
        tickmode="array",
        tickvals=ticks,
        range=[0.5, size + 0.5],
        constrain="domain",
    )
    fig.update_yaxes(
        title_text="Consequence",
        tickmode="array",
        tickvals=ticks,
        range=[0.5, size + 0.5],
        scaleanchor="x",
        scaleratio=1,
        constrain="domain",
    )


def risk_matrix_heatmap(
    risk: RiskResult,
    *,
    height: int = 480,
    width: int | None = 480,
) -> go.Figure:
    """Build the risk matrix with a single well plotted in its cell.

    Args:
        risk: The risk result to place on the matrix.
        height: Figure height in pixels.
        width: Optional fixed width in pixels (defaults to a square canvas).

    Returns:
        A heatmap figure with a labelled marker at the well's matrix cell.

    """
    l_bin, c_bin = _cell_from_risk(risk)

    fig = go.Figure(_matrix_background())
    fig.add_trace(
        go.Scatter(
            x=[l_bin],
            y=[c_bin],
            mode="markers+text",
            marker={
                "size": 26,
                "color": "#222222",
                "symbol": "circle",
                "line": {"color": "white", "width": 2},
            },
            text=[risk.well_id],
            textposition="top center",
            textfont={"color": "#222222", "size": 12},
            hovertemplate=(
                f"{risk.well_id}<br>Likelihood bin %{{x}}<br>Consequence bin %{{y}}"
                f"<br>Risk {risk.risk_score:.1f} ({risk.risk_category.value})<extra></extra>"
            ),
            name=risk.well_id,
        )
    )
    _axis_layout(fig)
    fig.update_layout(showlegend=False)
    return apply_base_layout(
        fig,
        f"Risk Matrix: {risk.well_id} (cell L{l_bin}-C{c_bin})",
        height=height,
        width=width,
    )


def risk_matrix_heatmap_from_assessment(
    assessment: WellAssessment,
    *,
    height: int = 480,
    width: int | None = 480,
) -> go.Figure:
    """Build the risk matrix directly from a :class:`WellAssessment`.

    Args:
        assessment: The complete well assessment.
        height: Figure height in pixels.
        width: Optional fixed width in pixels.

    Returns:
        The single-well risk matrix figure.

    """
    return risk_matrix_heatmap(assessment.risk, height=height, width=width)


def portfolio_risk_matrix(
    assessments: Sequence[WellAssessment],
    *,
    height: int = 560,
    width: int | None = 560,
) -> go.Figure:
    """Plot multiple wells on a shared risk matrix for portfolio screening.

    Wells that fall in the same cell are jittered slightly so overlapping
    markers remain distinguishable. Markers are coloured by risk category.

    Args:
        assessments: The well assessments to plot.
        height: Figure height in pixels.
        width: Optional fixed width in pixels.

    Returns:
        A heatmap figure with one labelled marker per well.

    Raises:
        ValueError: If ``assessments`` is empty.

    """
    if not assessments:
        raise ValueError("portfolio_risk_matrix requires at least one assessment.")

    from lwra.visualizations._theme import RISK_CATEGORY_COLORS

    fig = go.Figure(_matrix_background())

    # Deterministic intra-cell jitter so co-located wells don't overlap exactly.
    cell_counts: dict[tuple[int, int], int] = {}
    xs: list[float] = []
    ys: list[float] = []
    texts: list[str] = []
    colors: list[str] = []
    hovers: list[str] = []
    for assessment in assessments:
        risk = assessment.risk
        l_bin, c_bin = _cell_from_risk(risk)
        n = cell_counts.get((l_bin, c_bin), 0)
        cell_counts[(l_bin, c_bin)] = n + 1
        # Spiral-ish deterministic offset within the cell.
        offset = 0.12 * n
        xs.append(l_bin + (offset if n % 2 == 0 else -offset))
        ys.append(c_bin + (offset if n % 2 == 1 else -offset))
        texts.append(assessment.well_id)
        colors.append(RISK_CATEGORY_COLORS[risk.risk_category])
        hovers.append(
            f"{assessment.well_id}<br>Risk {risk.risk_score:.1f} ({risk.risk_category.value})"
        )

    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="markers+text",
            marker={"size": 20, "color": colors, "line": {"color": "white", "width": 2}},
            text=texts,
            textposition="top center",
            textfont={"size": 10, "color": "#222222"},
            hovertext=hovers,
            hovertemplate="%{hovertext}<extra></extra>",
            name="wells",
        )
    )
    _axis_layout(fig)
    fig.update_layout(showlegend=False)
    return apply_base_layout(fig, "Portfolio Risk Matrix", height=height, width=width)
