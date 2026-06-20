"""Barrier-related data models.

Defines :class:`BarrierData`, the description of a single well barrier element,
and :class:`CasingString`, a supporting structure referenced by
:class:`~lwra.models.well.WellData`.

Both models are immutable (``frozen=True``) because they represent observed,
recorded facts about a well rather than mutable working state. The integrity
engine consumes them and produces *new* result objects without mutating inputs.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lwra.models.enums import BarrierElement, BarrierType

__all__ = ["CasingString", "BarrierData"]


class CasingString(BaseModel):
    """A single casing string installed in the well.

    Attributes:
        name: Human-readable string identifier (e.g. ``"production casing"``).
        outer_diameter_in: Nominal outer diameter in inches.
        depth_top_m: Measured depth to the top of the string, in metres.
        depth_bottom_m: Measured depth to the shoe of the string, in metres.
        cemented: Whether the annulus around this string is cemented.

    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., min_length=1, description="Casing string identifier.")
    outer_diameter_in: float = Field(..., gt=0, description="Nominal outer diameter in inches.")
    depth_top_m: float = Field(..., ge=0, description="Measured depth to top of string (m).")
    depth_bottom_m: float = Field(..., gt=0, description="Measured depth to shoe of string (m).")
    cemented: bool = Field(default=False, description="Whether the annulus is cemented.")

    @model_validator(mode="after")
    def _validate_depth_ordering(self) -> CasingString:
        """Ensure the shoe lies below the top of the string."""
        if self.depth_bottom_m <= self.depth_top_m:
            raise ValueError(
                "depth_bottom_m must be greater than depth_top_m "
                f"(got top={self.depth_top_m}, bottom={self.depth_bottom_m})."
            )
        return self


class BarrierData(BaseModel):
    """A single well barrier element and its observed condition.

    This is the atomic input to the integrity engine. ``condition_score`` is a
    normalised raw observation in the range [0, 1]; the integrity engine scales
    and weights it (alongside ``verified`` and interval coverage) into the
    0-100 component scores defined in the architecture document.

    Attributes:
        barrier_id: Unique identifier for the barrier within the well.
        barrier_type: Whether this is a primary or secondary barrier.
        element: The physical element constituting the barrier.
        depth_top_m: Measured depth to the top of the barrier (m).
        depth_bottom_m: Measured depth to the base of the barrier (m).
        condition_score: Normalised raw condition in [0, 1]; 1 is pristine.
        verification_method: Description of how the barrier was verified.
        verified: Whether the barrier condition has been independently verified.
        notes: Optional free-text observations.

    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    barrier_id: str = Field(..., min_length=1, description="Unique barrier identifier.")
    barrier_type: BarrierType = Field(..., description="Primary or secondary barrier role.")
    element: BarrierElement = Field(..., description="Physical element constituting the barrier.")
    depth_top_m: float = Field(..., ge=0, description="Measured depth to top of barrier (m).")
    depth_bottom_m: float = Field(..., gt=0, description="Measured depth to base of barrier (m).")
    condition_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalised raw condition in [0, 1]; 1 is pristine.",
    )
    verification_method: str = Field(default="", description="How the barrier was verified.")
    verified: bool = Field(
        default=False, description="Whether the barrier was independently verified."
    )
    notes: str | None = Field(default=None, description="Optional free-text observations.")

    @model_validator(mode="after")
    def _validate_depth_ordering(self) -> BarrierData:
        """Ensure the base of the barrier lies below its top."""
        if self.depth_bottom_m <= self.depth_top_m:
            raise ValueError(
                "depth_bottom_m must be greater than depth_top_m "
                f"(got top={self.depth_top_m}, bottom={self.depth_bottom_m})."
            )
        return self

    @model_validator(mode="after")
    def _validate_verification_consistency(self) -> BarrierData:
        """Ensure a verified barrier records how it was verified."""
        if self.verified and not self.verification_method.strip():
            raise ValueError("verification_method must be provided when verified is True.")
        return self
