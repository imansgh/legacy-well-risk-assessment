"""Shared pytest fixtures for the LWRA test suite.

A fixed ``as_of`` date keeps every age-dependent calculation deterministic, so
score assertions are stable regardless of when the suite runs.
"""

from __future__ import annotations

from datetime import date

import pytest

from lwra.models.well import WellData
from lwra.sample_data import (
    abandon_well,
    data_poor_well,
    excellent_well,
    remediation_well,
)
from lwra.services.pipeline import WellAssessment, assess_well_traced

# Fixed reference date for deterministic, reproducible age-based scoring.
AS_OF: date = date(2025, 1, 1)


@pytest.fixture(scope="session")
def as_of() -> date:
    """The fixed assessment reference date used across the suite."""
    return AS_OF


@pytest.fixture()
def well_excellent() -> WellData:
    """A clean reuse-candidate well."""
    return excellent_well()


@pytest.fixture()
def well_remediation() -> WellData:
    """A moderate remediation-case well."""
    return remediation_well()


@pytest.fixture()
def well_abandon() -> WellData:
    """A critical abandon-case well."""
    return abandon_well()


@pytest.fixture()
def well_data_poor() -> WellData:
    """A sparsely characterised well."""
    return data_poor_well()


@pytest.fixture()
def assessment_excellent(well_excellent: WellData) -> WellAssessment:
    """A traced assessment of the excellent well at the fixed date."""
    return assess_well_traced(well_excellent, as_of=AS_OF)


@pytest.fixture()
def assessment_abandon(well_abandon: WellData) -> WellAssessment:
    """A traced assessment of the abandon-case well at the fixed date."""
    return assess_well_traced(well_abandon, as_of=AS_OF)
