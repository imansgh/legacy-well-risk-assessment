"""Bar charts for weighted risk contributions and portfolio comparisons.

Two families of bar chart:

* **Weighted risk contributions** -- a horizontal bar chart of each factor's
  weighted contribution to a well's scalar risk score, from
  ``RiskResult.weighted_factors``, with the dominant drivers highlighted.
* **Portfolio comparison** -- vertical bars ranking wells by risk or integrity
  score across a batch, for screening.

Pure functions returning :class:`plotly.graph_objects.Figure`; no business
logic. Values are taken verbatim from the result objects.
"""

from __future__ import annotations

from collections.abc import Sequence

import plotly.graph_objects as go

from lwra.models.results import RiskResult
from lwra.services.pipeline import WellAssessment
from lwra.visualizations._theme import (
    INTEGRITY_CATEGORY_COLORS,
    RISK_CATEGORY_COLORS,
    apply_base_layout,
    prettify_key,
)

__all__ = [
    "weighted_risk_contributions",
    "weighted_risk_contributions_from_assessment",
    "portfolio_risk_comparison",
    "portfolio_integrity_comparison",
]

# Colours for the contribution bars: dominant drivers stand out from the rest.
_DOMINANT_COLOR: str = "#d73027"
_OTHER_COLOR: str = "#4575b4"


def weighted_risk_contributions(
    risk: RiskResult,
    *,
    height: int = 420,
    width: int | None = None,
) -> go.Figure:
    """Build a horizontal bar chart of weighted risk-factor contributions.

    Each factor's weighted contribution to the scalar risk score is plotted,
    sorted ascending so the largest contributor sits at the top. Factors named
    in ``dominant_risk_drivers`` are highlighted.

    Args:
        risk: The risk result to visualise.
        height: Figure height in pixels.
        width: Optional fixed width in pixels.

    Returns:
        A horizontal bar figure of weighted contributions.
    """
    items = sorted(risk.weighted_factors.items(), key=lambda kv: kv[1])
    keys = [k for k, _ in items]
    values = [v for _, v in items]
    labels = [prettify_key(k) for k in keys]
    dominant = set(risk.dominant_risk_drivers)
    colors = [_DOMINANT_COLOR if k in dominant else _OTHER_COLOR for k in keys]

    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker={"color": colors},
            text=[f"{v:.1f}" for v in values],
            textposition="outside",
            hovertemplate="%{y}: %{x:.2f} weighted points<extra></extra>",
        )
    )
    fig.update_xaxes(title_text="Weighted contribution to risk score")
    fig.update_layout(showlegend=False)
    return apply_base_layout(
        fig,
        f"Weighted Risk Contributions: {risk.well_id}",
        height=height,
        width=width,
    )


def weighted_risk_contributions_from_assessment(
    assessment: WellAssessment,
    *,
    height: int = 420,
    width: int | None = None,
) -> go.Figure:
    """Build the weighted-contributions bar chart from a :class:`WellAssessment`.

    Args:
        assessment: The complete well assessment.
        height: Figure height in pixels.
        width: Optional fixed width in pixels.

    Returns:
        The weighted risk contributions figure for the assessment.
    """
    return weighted_risk_contributions(assessment.risk, height=height, width=width)


def portfolio_risk_comparison(
    assessments: Sequence[WellAssessment],
    *,
    descending: bool = True,
    height: int = 460,
    width: int | None = None,
) -> go.Figure:
    """Rank wells by overall risk score as a vertical bar chart.

    Bars are coloured by risk category, giving an at-a-glance triage view for
    portfolio screening.

    Args:
        assessments: The well assessments to compare.
        descending: When ``True`` (default), highest risk first.
        height: Figure height in pixels.
        width: Optional fixed width in pixels.

    Returns:
        A vertical bar figure ranking wells by risk score.

    Raises:
        ValueError: If ``assessments`` is empty.
    """
    if not assessments:
        raise ValueError("portfolio_risk_comparison requires at least one assessment.")

    ranked = sorted(
        assessments, key=lambda a: a.risk.risk_score, reverse=descending
    )
    well_ids = [a.well_id for a in ranked]
    scores = [a.risk.risk_score for a in ranked]
    colors = [RISK_CATEGORY_COLORS[a.risk.risk_category] for a in ranked]
    categories = [a.risk.risk_category.value for a in ranked]

    fig = go.Figure(
        go.Bar(
            x=well_ids,
            y=scores,
            marker={"color": colors},
            text=[f"{s:.0f}" for s in scores],
            textposition="outside",
            customdata=categories,
            hovertemplate="%{x}: risk %{y:.1f} (%{customdata})<extra></extra>",
        )
    )
    fig.update_yaxes(title_text="Risk score (0-100)", range=[0, 100])
    fig.update_xaxes(title_text="Well")
    fig.update_layout(showlegend=False)
    return apply_base_layout(
        fig, "Portfolio Risk Comparison", height=height, width=width
    )


def portfolio_integrity_comparison(
    assessments: Sequence[WellAssessment],
    *,
    descending: bool = False,
    height: int = 460,
    width: int | None = None,
) -> go.Figure:
    """Rank wells by overall integrity score as a vertical bar chart.

    Bars are coloured by integrity category. Defaults to ascending order so the
    weakest wells surface first for remediation triage.

    Args:
        assessments: The well assessments to compare.
        descending: When ``False`` (default), lowest integrity first.
        height: Figure height in pixels.
        width: Optional fixed width in pixels.

    Returns:
        A vertical bar figure ranking wells by integrity score.

    Raises:
        ValueError: If ``assessments`` is empty.
    """
    if not assessments:
        raise ValueError(
            "portfolio_integrity_comparison requires at least one assessment."
        )

    ranked = sorted(
        assessments,
        key=lambda a: a.integrity.overall_integrity_score,
        reverse=descending,
    )
    well_ids = [a.well_id for a in ranked]
    scores = [a.integrity.overall_integrity_score for a in ranked]
    colors = [INTEGRITY_CATEGORY_COLORS[a.integrity.integrity_category] for a in ranked]
    categories = [a.integrity.integrity_category.value for a in ranked]

    fig = go.Figure(
        go.Bar(
            x=well_ids,
            y=scores,
            marker={"color": colors},
            text=[f"{s:.0f}" for s in scores],
            textposition="outside",
            customdata=categories,
            hovertemplate="%{x}: integrity %{y:.1f} (%{customdata})<extra></extra>",
        )
    )
    fig.update_yaxes(title_text="Integrity score (0-100)", range=[0, 100])
    fig.update_xaxes(title_text="Well")
    fig.update_layout(showlegend=False)
    return apply_base_layout(
        fig, "Portfolio Integrity Comparison", height=height, width=width
    )
