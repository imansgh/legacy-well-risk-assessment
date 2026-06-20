"""Plotly-based visualisations for integrity gauges, radar, risk matrix, and bars."""

from lwra.visualizations import bars, gauges, heatmap, radar
from lwra.visualizations.bars import (
    portfolio_integrity_comparison,
    portfolio_risk_comparison,
    weighted_risk_contributions,
    weighted_risk_contributions_from_assessment,
)
from lwra.visualizations.gauges import (
    integrity_gauge,
    integrity_gauge_from_assessment,
    risk_gauge,
    risk_gauge_from_assessment,
)
from lwra.visualizations.heatmap import (
    portfolio_risk_matrix,
    risk_matrix_heatmap,
    risk_matrix_heatmap_from_assessment,
)
from lwra.visualizations.radar import (
    component_radar,
    component_radar_from_assessment,
    portfolio_radar,
)

__all__ = [
    # submodules
    "bars",
    "gauges",
    "heatmap",
    "radar",
    # gauges
    "integrity_gauge",
    "integrity_gauge_from_assessment",
    "risk_gauge",
    "risk_gauge_from_assessment",
    # bars
    "weighted_risk_contributions",
    "weighted_risk_contributions_from_assessment",
    "portfolio_risk_comparison",
    "portfolio_integrity_comparison",
    # heatmap
    "risk_matrix_heatmap",
    "risk_matrix_heatmap_from_assessment",
    "portfolio_risk_matrix",
    # radar
    "component_radar",
    "component_radar_from_assessment",
    "portfolio_radar",
]
