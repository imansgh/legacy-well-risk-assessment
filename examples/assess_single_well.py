"""Example: assess a single legacy well end to end.

Runs the full pipeline on one sample well, prints a readable summary of the
integrity, risk, and recommendation results, and writes a JSON, Excel, and PDF
report to ``examples/output/``.

Run from the repository root::

    python examples/assess_single_well.py

(Or, if the package is installed: ``python -m examples.assess_single_well``.)
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from lwra.reports import write_excel_report, write_json_report, write_pdf_report
from lwra.sample_data import remediation_well
from lwra.services.pipeline import assess_well_traced

# Fixed assessment date keeps the example fully reproducible.
AS_OF = date(2025, 1, 1)
OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def main() -> None:
    """Assess one sample well, print a summary, and write all report formats."""
    well = remediation_well()
    assessment = assess_well_traced(well, as_of=AS_OF)

    integ = assessment.integrity
    risk = assessment.risk
    rec = assessment.recommendation

    print("=" * 70)
    print(f"Legacy Well Risk Assessment  --  {well.well_id} ({well.name})")
    print("=" * 70)
    print(f"Assessment date (as_of): {assessment.as_of.isoformat()}")
    print()

    print("INTEGRITY")
    print(f"  Overall: {integ.overall_integrity_score:.1f}/100 ({integ.integrity_category.value})")
    for key, score in integ.component_breakdown.items():
        print(f"    - {key:22s}: {score:5.1f}")
    if integ.flags:
        print("  Flags:")
        for flag in integ.flags:
            print(f"    ! {flag}")
    print()

    print("RISK")
    print(f"  Overall: {risk.risk_score:.1f}/100 ({risk.risk_category.value})")
    print(f"  Likelihood: {risk.likelihood:.1f} | Consequence: {risk.consequence:.1f}")
    print(f"  Dominant drivers: {', '.join(risk.dominant_risk_drivers) or '-'}")
    print()

    print("RECOMMENDATION")
    print(f"  Verdict: {rec.verdict.value.upper()}")
    print(f"  CO2 storage:  {rec.co2_storage_suitability.value}")
    print(f"  Geothermal:   {rec.geothermal_suitability.value}")
    print(f"  Confidence:   {rec.confidence:.2f}")
    if rec.required_actions:
        print("  Required actions:")
        for index, action in enumerate(rec.required_actions, start=1):
            print(f"    {index}. {action}")
    print()
    print("  Rationale:")
    print(f"    {rec.rationale}")
    print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = write_json_report(assessment, OUTPUT_DIR, traced=True)
    excel_path = write_excel_report(well, assessment, OUTPUT_DIR)
    # include_figures=False so the example runs without a Chrome/Kaleido runtime.
    pdf_path = write_pdf_report(well, assessment, OUTPUT_DIR, include_figures=False)

    print("Reports written:")
    print(f"  JSON : {json_path}")
    print(f"  Excel: {excel_path}")
    print(f"  PDF  : {pdf_path}")


if __name__ == "__main__":
    main()
