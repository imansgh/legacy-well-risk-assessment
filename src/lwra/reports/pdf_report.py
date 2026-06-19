"""Professional PDF report generation (ReportLab).

Produces a formal, publication-quality assessment report for a single well:

* title block and well summary,
* integrity results (component + overall scores, category, flags),
* risk results (scores, category, dominant drivers, weighted factors),
* recommendation (verdict, suitability, confidence, rationale, required
  actions),
* embedded Plotly figures (gauges, radar, risk matrix, contribution bars),
* a standing non-compliance disclaimer.

Figures are rendered to PNG via Plotly/Kaleido and embedded. Static image export
requires a Chrome/Chromium runtime (Kaleido's dependency); when it is
unavailable the report is still produced with a short note in place of the
figure gallery, so PDF generation never hard-fails in a headless environment.

Pure, deterministic function returning the written file path.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from lwra.models.well import WellData
from lwra.reports._common import (
    DISCLAIMER,
    check_consistency,
    fmt,
    resolve_output_path,
)
from lwra.services.pipeline import WellAssessment
from lwra.visualizations.bars import weighted_risk_contributions_from_assessment
from lwra.visualizations.gauges import (
    integrity_gauge_from_assessment,
    risk_gauge_from_assessment,
)
from lwra.visualizations.heatmap import risk_matrix_heatmap_from_assessment
from lwra.visualizations.radar import component_radar_from_assessment

__all__ = ["write_pdf_report", "DEFAULT_OUTPUT_DIR"]

DEFAULT_OUTPUT_DIR: str = "reports_out"

_BRAND = colors.HexColor("#1F4E79")
_HEADER_BG = colors.HexColor("#1F4E79")
_HEADER_FG = colors.white
_ROW_ALT = colors.HexColor("#EEF3F8")


def _styles() -> dict[str, ParagraphStyle]:
    """Build the paragraph styles used throughout the report.

    Returns:
        A mapping of style name -> :class:`ParagraphStyle`.
    """
    base = getSampleStyleSheet()
    styles: dict[str, ParagraphStyle] = {}
    styles["title"] = ParagraphStyle(
        "LWRATitle", parent=base["Title"], textColor=_BRAND, fontSize=20, spaceAfter=4
    )
    styles["subtitle"] = ParagraphStyle(
        "LWRASubtitle", parent=base["Normal"], fontSize=10, textColor=colors.grey,
        spaceAfter=12,
    )
    styles["h2"] = ParagraphStyle(
        "LWRAH2", parent=base["Heading2"], textColor=_BRAND, fontSize=13,
        spaceBefore=12, spaceAfter=6,
    )
    styles["body"] = ParagraphStyle(
        "LWRABody", parent=base["Normal"], fontSize=10, leading=14
    )
    styles["small"] = ParagraphStyle(
        "LWRASmall", parent=base["Normal"], fontSize=8, textColor=colors.grey,
        leading=11,
    )
    styles["disclaimer"] = ParagraphStyle(
        "LWRADisclaimer", parent=base["Normal"], fontSize=8,
        textColor=colors.HexColor("#7A1F1F"), leading=11, spaceBefore=6,
    )
    return styles


def _kv_table(rows: list[tuple[str, str]], *, col_widths: tuple[float, float]) -> Table:
    """Build a two-column key/value table with the house style.

    Args:
        rows: ``(label, value)`` pairs.
        col_widths: Width of the two columns.

    Returns:
        A styled :class:`reportlab.platypus.Table`.
    """
    table = Table([list(r) for r in rows], colWidths=list(col_widths), hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 0), (0, -1), _BRAND),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, _ROW_ALT]),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _header_table(
    header: list[str],
    data_rows: list[list[str]],
    *,
    col_widths: list[float],
) -> Table:
    """Build a column-headed data table with the house style.

    Args:
        header: Column header labels.
        data_rows: Row data as lists of strings.
        col_widths: Per-column widths.

    Returns:
        A styled :class:`reportlab.platypus.Table`.
    """
    table = Table([header, *data_rows], colWidths=col_widths, hAlign="LEFT", repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), _HEADER_FG),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _ROW_ALT]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _render_figures_png(
    assessment: WellAssessment,
    *,
    scale: float,
) -> tuple[list[tuple[str, bytes]], str | None]:
    """Render the report figures to PNG bytes.

    Args:
        assessment: The assessment to visualise.
        scale: Image scale factor passed to the figure exporter.

    Returns:
        ``(images, error)`` where ``images`` is a list of ``(caption, png_bytes)``
        and ``error`` is ``None`` on success or a short message describing why
        figure export was skipped (e.g. missing Chrome runtime for Kaleido).
    """
    builders = [
        ("Overall integrity", integrity_gauge_from_assessment(assessment)),
        ("Overall risk", risk_gauge_from_assessment(assessment)),
        ("Integrity components", component_radar_from_assessment(assessment)),
        ("Risk matrix", risk_matrix_heatmap_from_assessment(assessment)),
        ("Weighted risk contributions", weighted_risk_contributions_from_assessment(assessment)),
    ]
    images: list[tuple[str, bytes]] = []
    try:
        for caption, fig in builders:
            png = fig.to_image(format="png", scale=scale)
            images.append((caption, png))
    except Exception as exc:  # noqa: BLE001 - degrade gracefully, report reason
        return [], (
            "Figures were omitted because static image export is unavailable in "
            f"this environment ({type(exc).__name__}). Install a Chrome/Chromium "
            "runtime for Kaleido to embed figures."
        )
    return images, None


def _figure_flowables(
    images: list[tuple[str, bytes]],
    styles: dict[str, ParagraphStyle],
    *,
    img_width: float,
) -> list[Any]:
    """Convert rendered PNGs into ReportLab flowables with captions.

    Args:
        images: ``(caption, png_bytes)`` pairs.
        styles: The report paragraph styles.
        img_width: Target image width on the page.

    Returns:
        A list of platypus flowables (images + captions).
    """
    import io

    flowables: list[Any] = []
    for caption, png in images:
        bio = io.BytesIO(png)
        img = Image(bio)
        # Preserve aspect ratio against the target width.
        aspect = img.imageHeight / float(img.imageWidth)
        img.drawWidth = img_width
        img.drawHeight = img_width * aspect
        img.hAlign = "CENTER"
        flowables.append(img)
        flowables.append(Paragraph(caption, styles["small"]))
        flowables.append(Spacer(1, 6 * mm))
    return flowables


def write_pdf_report(
    well: WellData,
    assessment: WellAssessment,
    output_path: str | Path | None = None,
    *,
    include_figures: bool = True,
    figure_scale: float = 2.0,
) -> Path:
    """Write a professional PDF report and return its path.

    Args:
        well: The source well data (for the well-summary section).
        assessment: The completed assessment to report.
        output_path: Destination file or directory, or ``None`` to use a
            generated filename under :data:`DEFAULT_OUTPUT_DIR`.
        include_figures: Whether to embed the Plotly figure gallery. When
            ``True`` but static export is unavailable, a short note replaces the
            gallery and the report is still produced.
        figure_scale: Image scale factor for embedded figures (higher = crisper).

    Returns:
        The path to the written ``.pdf`` file.

    Raises:
        ValueError: If ``well`` and ``assessment`` refer to different wells.
    """
    check_consistency(well, assessment)
    styles = _styles()

    target = resolve_output_path(
        output_path,
        well_id=assessment.well_id,
        default_dir=DEFAULT_OUTPUT_DIR,
        suffix=".pdf",
    )

    doc = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"LWRA Assessment {assessment.well_id}",
        author="Legacy Well Risk Assessment Tool",
    )
    content_width = doc.width
    story: list[Any] = []

    integ = assessment.integrity
    risk = assessment.risk
    rec = assessment.recommendation

    # --- Title block ------------------------------------------------------
    story.append(Paragraph("Legacy Well Risk Assessment", styles["title"]))
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    story.append(
        Paragraph(
            f"Well <b>{well.well_id}</b> &mdash; {well.name}<br/>"
            f"Assessment date (as_of): {assessment.as_of.isoformat()} &middot; "
            f"Generated: {generated}",
            styles["subtitle"],
        )
    )

    # --- Headline verdict -------------------------------------------------
    story.append(
        _kv_table(
            [
                ("Verdict", fmt(rec.verdict).upper()),
                ("Overall integrity", f"{integ.overall_integrity_score:.1f} / 100 ({integ.integrity_category.value})"),
                ("Overall risk", f"{risk.risk_score:.1f} / 100 ({risk.risk_category.value})"),
                ("Confidence", f"{rec.confidence:.2f}"),
            ],
            col_widths=(55 * mm, content_width - 55 * mm),
        )
    )

    # --- Well summary -----------------------------------------------------
    story.append(Paragraph("1. Well Summary", styles["h2"]))
    story.append(
        _kv_table(
            [
                ("Location", f"{fmt(well.location.latitude)}, {fmt(well.location.longitude)}"),
                ("Spud / Abandonment", f"{fmt(well.spud_date)}  /  {fmt(well.abandonment_date)}"),
                ("Total depth (m)", fmt(well.total_depth_m)),
                ("Well type", fmt(well.well_type)),
                ("Formation", well.formation or "\u2013"),
                ("Reservoir fluid", fmt(well.reservoir_fluid)),
                ("Pressure (bar)", fmt(well.pressure_bar)),
                ("Temperature (deg C)", fmt(well.temperature_c)),
                ("Proximity to receptors (m)", fmt(well.proximity_to_receptors_m)),
                ("Casing strings", str(len(well.casing_strings))),
                ("Barriers recorded", str(len(well.barriers))),
            ],
            col_widths=(55 * mm, content_width - 55 * mm),
        )
    )

    # --- Integrity --------------------------------------------------------
    story.append(Paragraph("2. Integrity Results", styles["h2"]))
    story.append(
        _header_table(
            ["Component", "Score (0-100)"],
            [
                ["Primary barrier", fmt(integ.primary_barrier_score)],
                ["Secondary barrier", fmt(integ.secondary_barrier_score)],
                ["Cement quality", fmt(integ.cement_quality_score)],
                ["Mechanical integrity", fmt(integ.mechanical_integrity_score)],
                ["Plugging", fmt(integ.plugging_score)],
                ["Overall", fmt(integ.overall_integrity_score)],
                ["Category", integ.integrity_category.value],
            ],
            col_widths=[content_width * 0.6, content_width * 0.4],
        )
    )
    if integ.flags:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("Integrity flags:", styles["body"]))
        for flag in integ.flags:
            story.append(Paragraph(f"&bull; {flag}", styles["body"]))

    # --- Risk -------------------------------------------------------------
    story.append(Paragraph("3. Risk Results", styles["h2"]))
    coords = (risk.calculation_trace or {}).get("matrix_coordinates", {})
    matrix_cell = (
        f"L{coords.get('likelihood_bin')}-C{coords.get('consequence_bin')}"
        if coords
        else "\u2013"
    )
    story.append(
        _kv_table(
            [
                ("Risk score", f"{risk.risk_score:.1f} / 100 ({risk.risk_category.value})"),
                ("Likelihood", f"{risk.likelihood:.1f} / 100"),
                ("Consequence", f"{risk.consequence:.1f} / 100"),
                ("Risk-matrix cell", matrix_cell),
                ("Dominant drivers", ", ".join(d.replace("_", " ") for d in risk.dominant_risk_drivers) or "\u2013"),
            ],
            col_widths=(55 * mm, content_width - 55 * mm),
        )
    )
    if risk.weighted_factors:
        story.append(Spacer(1, 4 * mm))
        ranked = sorted(risk.weighted_factors.items(), key=lambda kv: kv[1], reverse=True)
        story.append(
            _header_table(
                ["Risk factor", "Weighted contribution"],
                [[f.replace("_", " "), fmt(v)] for f, v in ranked],
                col_widths=[content_width * 0.6, content_width * 0.4],
            )
        )

    # --- Recommendation ---------------------------------------------------
    story.append(Paragraph("4. Recommendation", styles["h2"]))
    story.append(
        _kv_table(
            [
                ("Verdict", fmt(rec.verdict).upper()),
                ("CO2 storage suitability", fmt(rec.co2_storage_suitability)),
                ("Geothermal suitability", fmt(rec.geothermal_suitability)),
                ("Confidence", f"{rec.confidence:.2f}"),
            ],
            col_widths=(55 * mm, content_width - 55 * mm),
        )
    )
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("Rationale", styles["body"]))
    story.append(Paragraph(rec.rationale, styles["body"]))

    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("Required actions", styles["body"]))
    if rec.required_actions:
        for index, action in enumerate(rec.required_actions, start=1):
            story.append(Paragraph(f"{index}. {action}", styles["body"]))
    else:
        story.append(Paragraph("None required.", styles["body"]))

    # --- Figures ----------------------------------------------------------
    if include_figures:
        images, error = _render_figures_png(assessment, scale=figure_scale)
        story.append(PageBreak())
        story.append(Paragraph("5. Figures", styles["h2"]))
        if error:
            story.append(Paragraph(error, styles["body"]))
        else:
            story.extend(
                _figure_flowables(images, styles, img_width=content_width * 0.75)
            )

    # --- Disclaimer -------------------------------------------------------
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(DISCLAIMER, styles["disclaimer"]))

    doc.build(story)
    return target
