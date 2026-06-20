"""JSON report generation.

Serialises a :class:`~lwra.services.pipeline.WellAssessment` to a JSON file in
two modes:

* **lean** -- the three result objects, scores, categories, recommendation, and
  metadata, but no calculation trace; compact and ideal for API payloads,
  dashboards, and database rows;
* **traced** -- the lean content plus the full nested calculation trace, for
  audit, publication appendices, and reproducibility archives.

Pure, deterministic functions. The JSON is produced via Pydantic's own
serialisation so it is guaranteed consistent with the FastAPI response schema
and round-trips losslessly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lwra.reports._common import DISCLAIMER, resolve_output_path
from lwra.services.pipeline import WellAssessment

__all__ = [
    "build_json_payload",
    "write_json_report",
    "DEFAULT_OUTPUT_DIR",
]

DEFAULT_OUTPUT_DIR: str = "reports_out"


def build_json_payload(
    assessment: WellAssessment,
    *,
    traced: bool = False,
) -> dict[str, Any]:
    """Build the JSON-serialisable payload for an assessment.

    Args:
        assessment: The completed assessment to serialise.
        traced: When ``True``, include the combined calculation trace (if the
            assessment carries one). When ``False``, the trace is omitted even
            if present, yielding the lean payload.

    Returns:
        A JSON-ready dictionary with a stable top-level shape::

            {
              "schema": "lwra.report.v1",
              "mode": "lean" | "traced",
              "disclaimer": "...",
              "assessment": { ... full WellAssessment dump ... }
            }

    """
    dump = assessment.model_dump(mode="json")
    if not traced:
        dump.pop("trace", None)

    return {
        "schema": "lwra.report.v1",
        "mode": "traced" if traced else "lean",
        "disclaimer": DISCLAIMER,
        "assessment": dump,
    }


def write_json_report(
    assessment: WellAssessment,
    output_path: str | Path | None = None,
    *,
    traced: bool = False,
    indent: int = 2,
) -> Path:
    """Write a JSON report for an assessment and return its path.

    Args:
        assessment: The completed assessment to serialise.
        output_path: Destination file or directory, or ``None`` to use a
            generated filename under :data:`DEFAULT_OUTPUT_DIR`.
        traced: Whether to include the full calculation trace.
        indent: JSON indentation; set to a small value or 0 for compact output.

    Returns:
        The path to the written ``.json`` file.

    """
    payload = build_json_payload(assessment, traced=traced)
    target = resolve_output_path(
        output_path,
        well_id=assessment.well_id,
        default_dir=DEFAULT_OUTPUT_DIR,
        suffix=".traced.json" if traced else ".json",
    )
    target.write_text(
        json.dumps(payload, indent=indent, ensure_ascii=False, sort_keys=False),
        encoding="utf-8",
    )
    return target
