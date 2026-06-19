"""Well-level data model.

Defines :class:`WellData`, the top-level input to the assessment pipeline. It
aggregates static well attributes, casing configuration, and the list of
observed barriers.

The model is immutable. ``location`` is stored as a validated
:class:`GeoLocation` rather than a bare tuple so that future GIS work
(GeoPandas / PostGIS) has a clean, typed anchor, while still serialising
predictably for FastAPI and JSONB storage.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lwra.models.barrier import BarrierData, CasingString
from lwra.models.enums import FluidType, WellType

__all__ = ["GeoLocation", "WellData"]


class GeoLocation(BaseModel):
    """A geographic coordinate in WGS84 decimal degrees.

    Attributes:
        latitude: Latitude in decimal degrees, range [-90, 90].
        longitude: Longitude in decimal degrees, range [-180, 180].
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    latitude: float = Field(
        ..., ge=-90.0, le=90.0, description="Latitude in decimal degrees."
    )
    longitude: float = Field(
        ..., ge=-180.0, le=180.0, description="Longitude in decimal degrees."
    )


class WellData(BaseModel):
    """Complete static description of a legacy well.

    This is the canonical input to :mod:`lwra.services.pipeline`. Result models
    are derived from it; it is never mutated in place.

    Attributes:
        well_id: Unique well identifier.
        name: Human-readable well name.
        location: Geographic coordinate of the wellhead.
        spud_date: Date drilling commenced, if known.
        abandonment_date: Date the well was abandoned, if known.
        total_depth_m: Total measured depth (m).
        well_type: Functional classification of the well.
        formation: Name of the target/reservoir formation.
        reservoir_fluid: Dominant reservoir fluid.
        casing_strings: Casing strings installed in the well.
        pressure_bar: Reservoir/well pressure in bar, if known.
        temperature_c: Reservoir/well temperature in degrees Celsius, if known.
        proximity_to_receptors_m: Distance to nearest sensitive receptor (m).
        barriers: Observed well barriers feeding the integrity engine.
        metadata: Arbitrary additional key/value metadata.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    well_id: str = Field(..., min_length=1, description="Unique well identifier.")
    name: str = Field(..., min_length=1, description="Human-readable well name.")
    location: GeoLocation = Field(..., description="Wellhead coordinate.")
    spud_date: date | None = Field(
        default=None, description="Date drilling commenced."
    )
    abandonment_date: date | None = Field(
        default=None, description="Date the well was abandoned."
    )
    total_depth_m: float = Field(
        ..., gt=0, description="Total measured depth (m)."
    )
    well_type: WellType = Field(
        default=WellType.UNKNOWN, description="Functional classification."
    )
    formation: str = Field(
        default="", description="Target/reservoir formation name."
    )
    reservoir_fluid: FluidType = Field(
        default=FluidType.UNKNOWN, description="Dominant reservoir fluid."
    )
    casing_strings: tuple[CasingString, ...] = Field(
        default_factory=tuple, description="Installed casing strings."
    )
    pressure_bar: float | None = Field(
        default=None, ge=0, description="Reservoir/well pressure (bar)."
    )
    temperature_c: float | None = Field(
        default=None, description="Reservoir/well temperature (deg C)."
    )
    proximity_to_receptors_m: float | None = Field(
        default=None, ge=0, description="Distance to nearest receptor (m)."
    )
    barriers: tuple[BarrierData, ...] = Field(
        default_factory=tuple, description="Observed well barriers."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional key/value metadata."
    )

    @model_validator(mode="after")
    def _validate_dates(self) -> "WellData":
        """Ensure abandonment does not precede spud."""
        if (
            self.spud_date is not None
            and self.abandonment_date is not None
            and self.abandonment_date < self.spud_date
        ):
            raise ValueError(
                "abandonment_date cannot be earlier than spud_date "
                f"(spud={self.spud_date}, abandonment={self.abandonment_date})."
            )
        return self

    @model_validator(mode="after")
    def _validate_barrier_depths(self) -> "WellData":
        """Ensure barriers and casing strings lie within total depth."""
        for barrier in self.barriers:
            if barrier.depth_bottom_m > self.total_depth_m:
                raise ValueError(
                    f"Barrier '{barrier.barrier_id}' extends beyond total depth "
                    f"({barrier.depth_bottom_m} > {self.total_depth_m})."
                )
        for string in self.casing_strings:
            if string.depth_bottom_m > self.total_depth_m:
                raise ValueError(
                    f"Casing string '{string.name}' extends beyond total depth "
                    f"({string.depth_bottom_m} > {self.total_depth_m})."
                )
        return self

    @model_validator(mode="after")
    def _validate_unique_barrier_ids(self) -> "WellData":
        """Ensure barrier identifiers are unique within the well."""
        ids = [barrier.barrier_id for barrier in self.barriers]
        if len(ids) != len(set(ids)):
            raise ValueError("Barrier identifiers must be unique within a well.")
        return self

    @property
    def is_abandoned(self) -> bool:
        """Whether the well has a recorded abandonment date."""
        return self.abandonment_date is not None
