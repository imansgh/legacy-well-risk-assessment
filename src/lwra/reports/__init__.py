"""Report generation for the Legacy Well Risk Assessment Tool.

Pure, deterministic writers that turn a
:class:`~lwra.services.pipeline.WellAssessment` into shareable artefacts:

* :func:`write_pdf_report` -- a professional PDF (ReportLab) with embedded
  figures, for portfolios and publication appendices;
* :func:`write_excel_report` -- a multi-sheet workbook (OpenPyXL) with the full
  audit trail, for analysts;
* :func:`write_json_report` -- lean or traced JSON, for APIs, dashboards, and
  database archiving.

Each function returns the path to the written file.
"""

from lwra.reports.excel_report import write_excel_report
from lwra.reports.json_report import build_json_payload, write_json_report
from lwra.reports.pdf_report import write_pdf_report

__all__ = [
    "write_pdf_report",
    "write_excel_report",
    "write_json_report",
    "build_json_payload",
]
