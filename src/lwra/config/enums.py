"""Configuration enumerations.

These enums name the *keys* used inside ``weights.yaml`` and
``thresholds.yaml``. They are deliberately distinct from the domain enums in
:mod:`lwra.models.enums` (which define well/barrier vocabulary). Keeping the
configuration keys in code prevents silent typos: a config loader can validate
that every required key is present and that no unknown keys appear.

Every member's value equals the exact string used as a YAML key, so the engines
can look up configuration with, e.g., ``weights[RiskFactor.WELL_AGE.value]``.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "RiskFactor",
    "IntegrityComponent",
    "ConfigSection",
]


class RiskFactor(StrEnum):
    """Named factors combined by the risk engine.

    The ``risk_factor_weights`` block of ``weights.yaml`` must define exactly
    these keys. Each factor is normalised to a 0-100 contribution before being
    multiplied by its weight.
    """

    INTEGRITY_SCORE = "integrity_score"
    WELL_AGE = "well_age"
    RESERVOIR_PRESSURE = "reservoir_pressure"
    TEMPERATURE = "temperature"
    FLUID_HAZARD = "fluid_hazard"
    PROXIMITY_TO_RECEPTORS = "proximity_to_receptors"
    DATA_UNCERTAINTY = "data_uncertainty"


class IntegrityComponent(StrEnum):
    """Named components combined by the integrity engine.

    The ``integrity_component_weights`` block of ``weights.yaml`` must define
    exactly these keys. Each component is scored 0-100 (higher is better).
    """

    PRIMARY_BARRIER = "primary_barrier"
    SECONDARY_BARRIER = "secondary_barrier"
    CEMENT_QUALITY = "cement_quality"
    MECHANICAL_INTEGRITY = "mechanical_integrity"
    PLUGGING = "plugging"


class ConfigSection(StrEnum):
    """Top-level sections expected in the YAML configuration files."""

    # weights.yaml
    INTEGRITY_COMPONENT_WEIGHTS = "integrity_component_weights"
    RISK_FACTOR_WEIGHTS = "risk_factor_weights"
    FLUID_HAZARD_SCORES = "fluid_hazard_scores"
    LIKELIHOOD_CONSEQUENCE = "likelihood_consequence"

    # thresholds.yaml
    INTEGRITY_CATEGORY_THRESHOLDS = "integrity_category_thresholds"
    RISK_CATEGORY_THRESHOLDS = "risk_category_thresholds"
    FACTOR_NORMALISATION = "factor_normalisation"
    INTEGRITY_OVERRIDES = "integrity_overrides"
    CO2_STORAGE = "co2_storage"
    GEOTHERMAL = "geothermal"
