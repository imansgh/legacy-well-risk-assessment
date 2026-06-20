"""Canonical sample wells for examples, demos, and tests.

Provides a small, deterministic catalogue of :class:`~lwra.models.well.WellData`
instances spanning the qualitative outcome space (a clean reuse candidate, a
remediation case, an abandon case, and a data-poor case). Centralising them here
means the examples, the test suite, and the dashboards all exercise the *same*
inputs, so behaviour stays consistent and reproducible.

These are illustrative, synthetic wells -- not real field data.
"""

from __future__ import annotations

from datetime import date

from lwra.models.barrier import BarrierData, CasingString
from lwra.models.enums import BarrierElement, BarrierType, FluidType, WellType
from lwra.models.well import GeoLocation, WellData

__all__ = [
    "excellent_well",
    "remediation_well",
    "abandon_well",
    "data_poor_well",
    "sample_portfolio",
]


def excellent_well() -> WellData:
    """Return a deep, hot, verified-redundant well with benign fluid (reuse candidate).

    Returns:
        A :class:`WellData` expected to score well on integrity and low on risk.

    """
    return WellData(
        well_id="WELL-EXCELLENT",
        name="North Sea Alpha",
        location=GeoLocation(latitude=59.20, longitude=2.10),
        spud_date=date(2008, 3, 1),
        abandonment_date=date(2020, 9, 1),
        total_depth_m=2800.0,
        well_type=WellType.PRODUCTION,
        formation="Brent",
        reservoir_fluid=FluidType.WATER,
        pressure_bar=180.0,
        temperature_c=135.0,
        proximity_to_receptors_m=4800.0,
        casing_strings=(
            CasingString(
                name="surface",
                outer_diameter_in=13.375,
                depth_top_m=0.0,
                depth_bottom_m=900.0,
                cemented=True,
            ),
            CasingString(
                name="production",
                outer_diameter_in=9.625,
                depth_top_m=0.0,
                depth_bottom_m=2750.0,
                cemented=True,
            ),
        ),
        barriers=(
            BarrierData(
                barrier_id="P-CEM",
                barrier_type=BarrierType.PRIMARY,
                element=BarrierElement.CEMENT,
                depth_top_m=2300.0,
                depth_bottom_m=2750.0,
                condition_score=0.95,
                verified=True,
                verification_method="CBL/USIT",
            ),
            BarrierData(
                barrier_id="P-CAS",
                barrier_type=BarrierType.PRIMARY,
                element=BarrierElement.CASING,
                depth_top_m=0.0,
                depth_bottom_m=2750.0,
                condition_score=0.90,
                verified=True,
                verification_method="multi-finger caliper",
            ),
            BarrierData(
                barrier_id="S-PLUG",
                barrier_type=BarrierType.SECONDARY,
                element=BarrierElement.PLUG,
                depth_top_m=1000.0,
                depth_bottom_m=1060.0,
                condition_score=0.92,
                verified=True,
                verification_method="tag + pressure test",
            ),
        ),
    )


def remediation_well() -> WellData:
    """Return a moderate well with an unverified secondary barrier (remediation case).

    Returns:
        A :class:`WellData` expected to land in the remediate band.

    """
    return WellData(
        well_id="WELL-REMEDIATE",
        name="Central Graben Bravo",
        location=GeoLocation(latitude=57.05, longitude=2.85),
        spud_date=date(1995, 6, 1),
        abandonment_date=date(2009, 1, 1),
        total_depth_m=2500.0,
        well_type=WellType.PRODUCTION,
        formation="Forties",
        reservoir_fluid=FluidType.OIL,
        pressure_bar=300.0,
        temperature_c=95.0,
        proximity_to_receptors_m=1500.0,
        casing_strings=(
            CasingString(
                name="surface",
                outer_diameter_in=13.375,
                depth_top_m=0.0,
                depth_bottom_m=800.0,
                cemented=True,
            ),
            CasingString(
                name="production",
                outer_diameter_in=9.625,
                depth_top_m=0.0,
                depth_bottom_m=2400.0,
                cemented=False,
            ),
        ),
        barriers=(
            BarrierData(
                barrier_id="P-CEM",
                barrier_type=BarrierType.PRIMARY,
                element=BarrierElement.CEMENT,
                depth_top_m=1900.0,
                depth_bottom_m=2400.0,
                condition_score=0.72,
                verified=True,
                verification_method="CBL",
            ),
            BarrierData(
                barrier_id="P-CAS",
                barrier_type=BarrierType.PRIMARY,
                element=BarrierElement.CASING,
                depth_top_m=0.0,
                depth_bottom_m=2400.0,
                condition_score=0.65,
                verified=False,
            ),
            BarrierData(
                barrier_id="S-PLUG",
                barrier_type=BarrierType.SECONDARY,
                element=BarrierElement.PLUG,
                depth_top_m=850.0,
                depth_bottom_m=920.0,
                condition_score=0.60,
                verified=True,
                verification_method="tag",
            ),
        ),
    )


def abandon_well() -> WellData:
    """Return a shallow, failed-primary, H2S well close to receptors (abandon case).

    Returns:
        A :class:`WellData` expected to score critically and verdict to abandon.

    """
    return WellData(
        well_id="WELL-ABANDON",
        name="Legacy Onshore Charlie",
        location=GeoLocation(latitude=53.40, longitude=-1.20),
        spud_date=date(1961, 4, 1),
        abandonment_date=date(1978, 11, 1),
        total_depth_m=900.0,
        well_type=WellType.EXPLORATION,
        formation="Unknown",
        reservoir_fluid=FluidType.H2S,
        pressure_bar=480.0,
        temperature_c=40.0,
        proximity_to_receptors_m=90.0,
        casing_strings=(
            CasingString(
                name="production",
                outer_diameter_in=7.0,
                depth_top_m=0.0,
                depth_bottom_m=820.0,
                cemented=False,
            ),
        ),
        barriers=(
            BarrierData(
                barrier_id="P-CEM",
                barrier_type=BarrierType.PRIMARY,
                element=BarrierElement.CEMENT,
                depth_top_m=600.0,
                depth_bottom_m=820.0,
                condition_score=0.20,
                verified=False,
            ),
        ),
    )


def data_poor_well() -> WellData:
    """Return a sparsely characterised well (insufficient-data screening case).

    Returns:
        A :class:`WellData` with missing dates, pressure, temperature, proximity,
        and an unknown fluid, exercising the conservative data-uncertainty path.

    """
    return WellData(
        well_id="WELL-DATAPOOR",
        name="Archive Delta",
        location=GeoLocation(latitude=56.00, longitude=3.00),
        total_depth_m=2500.0,
        well_type=WellType.UNKNOWN,
        reservoir_fluid=FluidType.UNKNOWN,
        casing_strings=(
            CasingString(
                name="production",
                outer_diameter_in=9.625,
                depth_top_m=0.0,
                depth_bottom_m=2400.0,
                cemented=True,
            ),
        ),
        barriers=(
            BarrierData(
                barrier_id="P-CAS",
                barrier_type=BarrierType.PRIMARY,
                element=BarrierElement.CASING,
                depth_top_m=0.0,
                depth_bottom_m=2400.0,
                condition_score=0.80,
                verified=True,
                verification_method="caliper",
            ),
            BarrierData(
                barrier_id="S-PLUG",
                barrier_type=BarrierType.SECONDARY,
                element=BarrierElement.PLUG,
                depth_top_m=900.0,
                depth_bottom_m=950.0,
                condition_score=0.80,
                verified=True,
                verification_method="tag",
            ),
        ),
    )


def sample_portfolio() -> tuple[WellData, ...]:
    """Return the full catalogue of sample wells as a portfolio.

    Returns:
        A tuple of all sample wells, suitable for batch-screening demos.

    """
    return (excellent_well(), remediation_well(), abandon_well(), data_poor_well())
