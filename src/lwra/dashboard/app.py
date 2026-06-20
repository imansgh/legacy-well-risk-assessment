"""Streamlit dashboard for the Legacy Well Risk Assessment Tool.

A thin presentation layer over :mod:`lwra.services.pipeline`. It lets a user
pick (or load) a well, runs the assessment, and renders the gauges, radar, risk
matrix, and contribution bars alongside the recommendation and downloadable
reports. All computation happens in the engines; this module only collects
input and displays results.

Run from the repository root::

    streamlit run src/lwra/dashboard/app.py
"""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

import streamlit as st

import lwra.visualizations as viz
from lwra.models.well import WellData
from lwra.reports import write_excel_report, write_json_report, write_pdf_report
from lwra.sample_data import (
    abandon_well,
    data_poor_well,
    excellent_well,
    remediation_well,
    sample_portfolio,
)
from lwra.services.pipeline import WellAssessment, assess_well_traced

_SAMPLES = {
    "Excellent (reuse candidate)": excellent_well,
    "Remediation case": remediation_well,
    "Abandon case": abandon_well,
    "Data-poor case": data_poor_well,
}


def _verdict_badge(verdict: str) -> str:
    """Return an emoji-prefixed label for a verdict.

    Args:
        verdict: The verdict value string.

    Returns:
        A short display label.

    """
    icons = {
        "reuse": "\u2705",
        "remediate": "\U0001f527",
        "monitor": "\U0001f441",
        "abandon": "\u26d4",
    }
    return f"{icons.get(verdict, '')} {verdict.upper()}"


def _render_single(assessment: WellAssessment, well: WellData) -> None:
    """Render the full single-well view.

    Args:
        assessment: The completed assessment.
        well: The source well (needed for report writers).

    """
    rec = assessment.recommendation

    st.subheader(f"Verdict: {_verdict_badge(rec.verdict)}")
    col1, col2, col3 = st.columns(3)
    col1.metric(
        "Integrity",
        f"{assessment.overall_integrity_score:.1f}/100",
        assessment.integrity.integrity_category.value,
    )
    col2.metric(
        "Risk",
        f"{assessment.risk_score:.1f}/100",
        assessment.risk.risk_category.value,
        delta_color="inverse",
    )
    col3.metric("Confidence", f"{rec.confidence:.2f}")

    gauge_l, gauge_r = st.columns(2)
    gauge_l.plotly_chart(viz.integrity_gauge_from_assessment(assessment), use_container_width=True)
    gauge_r.plotly_chart(viz.risk_gauge_from_assessment(assessment), use_container_width=True)

    chart_l, chart_r = st.columns(2)
    chart_l.plotly_chart(viz.component_radar_from_assessment(assessment), use_container_width=True)
    chart_r.plotly_chart(
        viz.risk_matrix_heatmap_from_assessment(assessment), use_container_width=True
    )

    st.plotly_chart(
        viz.weighted_risk_contributions_from_assessment(assessment), use_container_width=True
    )

    st.markdown("### Recommendation")
    st.write(rec.rationale)
    rc1, rc2 = st.columns(2)
    rc1.info(f"**CO\u2082 storage:** {rec.co2_storage_suitability.value}")
    rc2.info(f"**Geothermal:** {rec.geothermal_suitability.value}")

    if rec.required_actions:
        st.markdown("**Required actions**")
        for index, action in enumerate(rec.required_actions, start=1):
            st.markdown(f"{index}. {action}")
    else:
        st.success("No remedial actions required.")

    if assessment.integrity.flags:
        with st.expander("Integrity flags"):
            for flag in assessment.integrity.flags:
                st.markdown(f"- {flag}")

    _render_downloads(assessment, well)

    with st.expander("Calculation trace (JSON)"):
        st.json(assessment.trace)


def _render_downloads(assessment: WellAssessment, well: WellData) -> None:
    """Render JSON/Excel/PDF download buttons.

    Args:
        assessment: The completed (traced) assessment.
        well: The source well.

    """
    st.markdown("### Download reports")
    tmp = Path(tempfile.mkdtemp(prefix="lwra_dash_"))
    json_path = write_json_report(assessment, tmp, traced=True)
    excel_path = write_excel_report(well, assessment, tmp)

    d1, d2, d3 = st.columns(3)
    d1.download_button(
        "JSON", json_path.read_bytes(), file_name=json_path.name, mime="application/json"
    )
    d2.download_button(
        "Excel",
        excel_path.read_bytes(),
        file_name=excel_path.name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    try:
        pdf_path = write_pdf_report(well, assessment, tmp)
        d3.download_button(
            "PDF", pdf_path.read_bytes(), file_name=pdf_path.name, mime="application/pdf"
        )
    except Exception as exc:  # noqa: BLE001 - PDF figures need a Chrome runtime
        d3.caption(f"PDF unavailable: {type(exc).__name__}")


def _render_portfolio(assessments: list[WellAssessment]) -> None:
    """Render the portfolio comparison view.

    Args:
        assessments: Assessments for every well in the portfolio.

    """
    st.subheader("Portfolio screening")
    table = [
        {
            "Well": a.well_id,
            "Integrity": round(a.overall_integrity_score, 1),
            "Risk": round(a.risk_score, 1),
            "Verdict": a.verdict,
            "CO2": a.recommendation.co2_storage_suitability.value,
            "Geothermal": a.recommendation.geothermal_suitability.value,
        }
        for a in sorted(assessments, key=lambda a: a.risk_score, reverse=True)
    ]
    st.dataframe(table, use_container_width=True)

    c1, c2 = st.columns(2)
    c1.plotly_chart(viz.portfolio_risk_comparison(assessments), use_container_width=True)
    c2.plotly_chart(viz.portfolio_integrity_comparison(assessments), use_container_width=True)
    st.plotly_chart(viz.portfolio_risk_matrix(assessments), use_container_width=True)
    st.plotly_chart(viz.portfolio_radar(assessments), use_container_width=True)


def main() -> None:
    """Streamlit entry point: build the sidebar controls and render the view."""
    st.set_page_config(page_title="Legacy Well Risk Assessment", layout="wide")
    st.title("Legacy Well Risk Assessment Tool")
    st.caption(
        "Methodology inspired by API RP 90, NORSOK D-010, ISO 27914. "
        "Not an official-compliance tool; results are advisory."
    )

    mode = st.sidebar.radio("Mode", ["Single well", "Portfolio"])
    as_of = st.sidebar.date_input("Assessment date (as_of)", value=date(2025, 1, 1))

    if mode == "Single well":
        source = st.sidebar.radio("Well source", ["Sample", "Upload JSON"])
        if source == "Sample":
            name = st.sidebar.selectbox("Sample well", list(_SAMPLES))
            well = _SAMPLES[name]()
        else:
            uploaded = st.sidebar.file_uploader("WellData JSON", type="json")
            if uploaded is None:
                st.info("Upload a WellData JSON document to assess.")
                return
            well = WellData.model_validate_json(uploaded.getvalue())

        assessment = assess_well_traced(well, as_of=as_of)
        st.markdown(f"#### {well.well_id} \u2014 {well.name}")
        _render_single(assessment, well)
    else:
        assessments = [assess_well_traced(w, as_of=as_of) for w in sample_portfolio()]
        _render_portfolio(assessments)


if __name__ == "__main__":
    main()
