"""Example: batch-screen a portfolio of legacy wells.

Assesses every sample well, prints a ranked screening table (highest risk
first), and writes one lean JSON report per well plus a combined CSV-style
summary to ``examples/output/portfolio/``.

Run from the repository root::

    python examples/screen_portfolio.py
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from lwra.reports import write_json_report
from lwra.sample_data import sample_portfolio
from lwra.services.pipeline import WellAssessment, assess_well

AS_OF = date(2025, 1, 1)
OUTPUT_DIR = Path(__file__).resolve().parent / "output" / "portfolio"


def _screen() -> list[WellAssessment]:
    """Assess every sample well at the fixed date.

    Returns:
        A list of assessments, one per sample well.
    """
    return [assess_well(well, as_of=AS_OF) for well in sample_portfolio()]


def main() -> None:
    """Screen the sample portfolio, print a ranked table, and write outputs."""
    assessments = _screen()
    ranked = sorted(assessments, key=lambda a: a.risk_score, reverse=True)

    header = f"{'Well':18s} {'Integrity':>10s} {'Risk':>7s} {'Verdict':>11s}  {'CO2':>14s} {'Geothermal':>14s}"
    print("=" * len(header))
    print("Portfolio Risk Screening (highest risk first)")
    print("=" * len(header))
    print(header)
    print("-" * len(header))
    for a in ranked:
        print(
            f"{a.well_id:18s} "
            f"{a.overall_integrity_score:10.1f} "
            f"{a.risk_score:7.1f} "
            f"{a.verdict:>11s}  "
            f"{a.recommendation.co2_storage_suitability.value:>14s} "
            f"{a.recommendation.geothermal_suitability.value:>14s}"
        )
    print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # One lean JSON per well (database-archiving / API-payload shape).
    for a in assessments:
        write_json_report(a, OUTPUT_DIR, traced=False)

    # Combined summary table for quick triage.
    summary_path = OUTPUT_DIR / "portfolio_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["well_id", "integrity_score", "integrity_category", "risk_score",
             "risk_category", "verdict", "co2_suitability", "geothermal_suitability",
             "confidence"]
        )
        for a in ranked:
            writer.writerow(
                [
                    a.well_id,
                    f"{a.overall_integrity_score:.1f}",
                    a.integrity.integrity_category.value,
                    f"{a.risk_score:.1f}",
                    a.risk.risk_category.value,
                    a.verdict,
                    a.recommendation.co2_storage_suitability.value,
                    a.recommendation.geothermal_suitability.value,
                    f"{a.recommendation.confidence:.2f}",
                ]
            )

    print(f"Wrote {len(assessments)} per-well JSON reports and a summary to:")
    print(f"  {OUTPUT_DIR}")
    print(f"  {summary_path}")


if __name__ == "__main__":
    main()
