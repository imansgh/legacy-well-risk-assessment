"""FastAPI backend for the Legacy Well Risk Assessment Tool.

Exposes the assessment pipeline over HTTP. The service layer
(:mod:`lwra.services.pipeline`) does all the work; this module is a thin,
stateless transport boundary that validates requests with the existing Pydantic
models and serialises the existing result models straight back to JSON.

Endpoints
---------
* ``GET  /health``                 -- liveness probe.
* ``GET  /config``                 -- the active weights and thresholds.
* ``POST /assess``                 -- assess one well (lean or traced).
* ``POST /assess/batch``           -- assess a portfolio in one call.
* ``POST /report/{fmt}``           -- assess one well and download a report
  (``fmt`` in ``json`` | ``excel`` | ``pdf``).

Run locally::

    uvicorn lwra.api.main:app --reload

The request body for ``/assess`` is a :class:`~lwra.models.well.WellData`
document; because the models are shared, the OpenAPI schema at ``/docs`` is
always consistent with the engine contracts.
"""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from lwra.integrity_engine._scoring import (
    integrity_component_weights,
    integrity_overrides,
    load_thresholds,
)
from lwra.models.well import WellData
from lwra.reports import write_excel_report, write_json_report, write_pdf_report
from lwra.reports.json_report import build_json_payload
from lwra.risk_engine.weighting import risk_factor_weights
from lwra.services.pipeline import WellAssessment, assess_well, assess_well_traced

__all__ = ["app", "create_app"]


class AssessRequest(BaseModel):
    """Request body for a single-well assessment.

    Attributes:
        well: The well to assess.
        as_of: Optional reference date for age-dependent factors. When omitted,
            the server uses the current date.
        traced: Whether to include the full calculation trace in the response.
    """

    well: WellData = Field(..., description="The well to assess.")
    as_of: date | None = Field(default=None, description="Assessment reference date.")
    traced: bool = Field(default=False, description="Include the calculation trace.")


class BatchAssessRequest(BaseModel):
    """Request body for a batch (portfolio) assessment.

    Attributes:
        wells: The wells to assess.
        as_of: Optional shared reference date.
        traced: Whether to include calculation traces in each result.
    """

    wells: list[WellData] = Field(..., min_length=1, description="Wells to assess.")
    as_of: date | None = Field(default=None, description="Shared reference date.")
    traced: bool = Field(default=False, description="Include calculation traces.")


def _assess(well: WellData, *, as_of: date | None, traced: bool) -> WellAssessment:
    """Run the pipeline, choosing the traced or lean entry point.

    Args:
        well: The well to assess.
        as_of: Reference date, or ``None`` for today.
        traced: Whether to produce a traced assessment.

    Returns:
        The completed :class:`WellAssessment`.
    """
    if traced:
        return assess_well_traced(well, as_of=as_of)
    return assess_well(well, as_of=as_of)


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application.

    Returns:
        A configured :class:`fastapi.FastAPI` instance.
    """
    app = FastAPI(
        title="Legacy Well Risk Assessment API",
        version="0.1.0",
        description=(
            "HTTP interface to the LWRA assessment pipeline. Methodology is "
            "inspired by API RP 90, NORSOK D-010, and ISO 27914; it does not "
            "claim official compliance with any standard."
        ),
    )

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        """Liveness probe.

        Returns:
            A small status document.
        """
        return {"status": "ok"}

    @app.get("/config", tags=["meta"])
    def config() -> dict[str, Any]:
        """Return the active weights and thresholds driving the engines.

        Returns:
            The integrity/risk weights, overrides, and category thresholds.
        """
        thresholds = load_thresholds()
        return {
            "integrity_component_weights": integrity_component_weights(),
            "risk_factor_weights": risk_factor_weights(),
            "integrity_overrides": integrity_overrides(),
            "integrity_category_thresholds": thresholds["integrity_category_thresholds"],
            "risk_category_thresholds": thresholds["risk_category_thresholds"],
        }

    @app.post("/assess", tags=["assessment"])
    def assess(request: AssessRequest) -> JSONResponse:
        """Assess a single well.

        Args:
            request: The assessment request (well, as_of, traced).

        Returns:
            A JSON response wrapping the assessment in the standard report
            envelope (``schema``/``mode``/``disclaimer``/``assessment``).
        """
        assessment = _assess(request.well, as_of=request.as_of, traced=request.traced)
        payload = build_json_payload(assessment, traced=request.traced)
        return JSONResponse(content=payload)

    @app.post("/assess/batch", tags=["assessment"])
    def assess_batch(request: BatchAssessRequest) -> JSONResponse:
        """Assess a portfolio of wells in a single call.

        Args:
            request: The batch request (wells, as_of, traced).

        Returns:
            A JSON response with one envelope per well plus a ranked summary
            (highest risk first) for quick triage.

        Raises:
            HTTPException: 422 if any well id is duplicated in the batch.
        """
        ids = [w.well_id for w in request.wells]
        if len(ids) != len(set(ids)):
            raise HTTPException(status_code=422, detail="Duplicate well_id in batch.")

        assessments = [
            _assess(well, as_of=request.as_of, traced=request.traced)
            for well in request.wells
        ]
        results = [build_json_payload(a, traced=request.traced) for a in assessments]
        summary = sorted(
            (
                {
                    "well_id": a.well_id,
                    "integrity_score": a.overall_integrity_score,
                    "risk_score": a.risk_score,
                    "verdict": a.verdict,
                }
                for a in assessments
            ),
            key=lambda row: row["risk_score"],
            reverse=True,
        )
        return JSONResponse(content={"summary": summary, "results": results})

    @app.post("/report/{fmt}", tags=["report"])
    def report(
        request: AssessRequest,
        fmt: str,
        download_name: str | None = Query(
            default=None, description="Optional download filename override."
        ),
    ) -> FileResponse:
        """Assess a well and return a downloadable report file.

        Args:
            request: The assessment request.
            fmt: Report format -- one of ``json``, ``excel``, ``pdf``.
            download_name: Optional override for the suggested filename.

        Returns:
            A :class:`fastapi.responses.FileResponse` streaming the report.

        Raises:
            HTTPException: 400 if ``fmt`` is not a supported format.
        """
        fmt_lower = fmt.lower()
        if fmt_lower not in {"json", "excel", "pdf"}:
            raise HTTPException(
                status_code=400,
                detail="fmt must be one of: json, excel, pdf.",
            )

        # Traced output is forced for file reports so the artefact is complete.
        assessment = _assess(request.well, as_of=request.as_of, traced=True)
        tmp_dir = Path(tempfile.mkdtemp(prefix="lwra_report_"))

        if fmt_lower == "json":
            path = write_json_report(assessment, tmp_dir, traced=True)
            media_type = "application/json"
        elif fmt_lower == "excel":
            path = write_excel_report(request.well, assessment, tmp_dir)
            media_type = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:  # pdf
            path = write_pdf_report(request.well, assessment, tmp_dir)
            media_type = "application/pdf"

        return FileResponse(
            path=str(path),
            media_type=media_type,
            filename=download_name or path.name,
        )

    return app


# Module-level app for ``uvicorn lwra.api.main:app``.
app = create_app()
