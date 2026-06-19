"""Domain enumerations for the Legacy Well Risk Assessment Tool.

Defines the well and barrier vocabulary used as data-model field types across
the models, engines, and visualisations.  These are deliberately distinct from
the configuration-key enums in :mod:`lwra.config.enums`.
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "BarrierType",
    "BarrierElement",
    "FluidType",
    "WellType",
    "IntegrityCategory",
    "RiskCategory",
    "SuitabilityLevel",
    "Verdict",
]


class BarrierType(str, Enum):
    """Whether a barrier element is the primary or secondary envelope."""

    PRIMARY = "primary"
    SECONDARY = "secondary"


class BarrierElement(str, Enum):
    """Physical element constituting a well barrier."""

    CEMENT = "cement"
    CASING = "casing"
    PLUG = "plug"
    PACKER = "packer"
    TUBING = "tubing"
    WELLHEAD = "wellhead"


class FluidType(str, Enum):
    """Dominant reservoir or wellbore fluid.

    Values match the keys of ``fluid_hazard_scores`` in ``weights.yaml``, so
    the risk engine can look up the hazard score with ``fluid_hazard_scores[fluid.value]``.
    """

    H2S = "h2s"
    CO2 = "co2"
    GAS = "gas"
    CONDENSATE = "condensate"
    MULTIPHASE = "multiphase"
    OIL = "oil"
    WATER = "water"
    UNKNOWN = "unknown"


class WellType(str, Enum):
    """Functional classification of the well."""

    PRODUCTION = "production"
    INJECTION = "injection"
    APPRAISAL = "appraisal"
    EXPLORATION = "exploration"
    ABANDONED = "abandoned"
    UNKNOWN = "unknown"


class IntegrityCategory(str, Enum):
    """Qualitative band for the overall integrity score (higher is better).

    Values match the keys of ``integrity_category_thresholds`` in
    ``thresholds.yaml``.
    """

    GOOD = "good"
    MODERATE = "moderate"
    POOR = "poor"
    FAILED = "failed"


class RiskCategory(str, Enum):
    """Qualitative band for the overall risk score (higher is worse).

    Values match the keys of ``risk_category_thresholds`` in
    ``thresholds.yaml``.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SuitabilityLevel(str, Enum):
    """Suitability verdict for a specific reuse application (CO2 / geothermal)."""

    SUITABLE = "suitable"
    CONDITIONAL = "conditional"
    UNSUITABLE = "unsuitable"
    INSUFFICIENT_DATA = "insufficient_data"


class Verdict(str, Enum):
    """Top-level engineering recommendation for the well."""

    REUSE = "reuse"
    REMEDIATE = "remediate"
    MONITOR = "monitor"
    ABANDON = "abandon"
