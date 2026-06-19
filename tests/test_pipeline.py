"""Tests for the services pipeline: orchestration and the aggregate object."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from lwra.services.pipeline import WellAssessment, assess_well, assess_well_traced

AS_OF = date(2025, 1, 1)


def test_assess_well_lean_has_no_trace(well_excellent) -> None:  # type: ignore[no-untyped-def]
    assessment = assess_well(well_excellent, as_of=AS_OF)
    assert isinstance(assessment, WellAssessment)
    assert assessment.trace is None


def test_assess_well_traced_has_trace(well_excellent) -> None:  # type: ignore[no-untyped-def]
    assessment = assess_well_traced(well_excellent, as_of=AS_OF)
    assert assessment.trace is not None
    assert set(assessment.trace) == {"well_id", "as_of", "integrity", "risk", "recommendation"}


def test_lean_and_traced_agree(well_excellent) -> None:  # type: ignore[no-untyped-def]
    lean = assess_well(well_excellent, as_of=AS_OF)
    traced = assess_well_traced(well_excellent, as_of=AS_OF)
    ex = {"assessed_at"}
    assert lean.integrity.model_dump(exclude=ex) == traced.integrity.model_dump(exclude=ex)
    assert lean.risk.model_dump(exclude=ex) == traced.risk.model_dump(exclude=ex)
    assert lean.recommendation.model_dump(exclude=ex) == traced.recommendation.model_dump(exclude=ex)


def test_convenience_accessors(well_excellent) -> None:  # type: ignore[no-untyped-def]
    a = assess_well(well_excellent, as_of=AS_OF)
    assert a.verdict == a.recommendation.verdict.value
    assert a.overall_integrity_score == a.integrity.overall_integrity_score
    assert a.risk_score == a.risk.risk_score


def test_as_of_threads_through(well_remediation) -> None:  # type: ignore[no-untyped-def]
    # Older as_of -> the spud->as_of span is the same since abandoned, but a
    # non-abandoned well ages with as_of. Use a non-abandoned copy.
    non_abandoned = well_remediation.model_copy(update={"abandonment_date": None})
    older = assess_well(non_abandoned, as_of=date(2005, 1, 1))
    newer = assess_well(non_abandoned, as_of=date(2025, 1, 1))
    assert newer.risk_score >= older.risk_score


def test_as_of_defaults_to_today(well_excellent) -> None:  # type: ignore[no-untyped-def]
    a = assess_well(well_excellent)
    assert a.as_of == date.today()


def test_immutable(well_excellent) -> None:  # type: ignore[no-untyped-def]
    a = assess_well(well_excellent, as_of=AS_OF)
    with pytest.raises(ValidationError):
        a.well_id = "X"  # type: ignore[misc]


def test_input_not_mutated(well_excellent) -> None:  # type: ignore[no-untyped-def]
    snapshot = well_excellent.model_dump()
    assess_well_traced(well_excellent, as_of=AS_OF)
    assert well_excellent.model_dump() == snapshot


def test_well_id_consistency_guard(assessment_excellent) -> None:  # type: ignore[no-untyped-def]
    bad_rec = assessment_excellent.recommendation.model_copy(update={"well_id": "OTHER"})
    with pytest.raises(ValidationError):
        WellAssessment(
            well_id=assessment_excellent.well_id,
            integrity=assessment_excellent.integrity,
            risk=assessment_excellent.risk,
            recommendation=bad_rec,
            as_of=AS_OF,
        )


def test_json_round_trip(assessment_excellent) -> None:  # type: ignore[no-untyped-def]
    restored = WellAssessment.model_validate_json(assessment_excellent.model_dump_json())
    assert restored.well_id == assessment_excellent.well_id


def test_portfolio_batch(well_excellent, well_abandon) -> None:  # type: ignore[no-untyped-def]
    portfolio = [assess_well(w, as_of=AS_OF) for w in (well_excellent, well_abandon)]
    ranked = sorted(portfolio, key=lambda a: a.risk_score, reverse=True)
    assert ranked[0].well_id == well_abandon.well_id
