"""A page region in one immutable PDF source revision."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ..base import DungeonMindModel
from .common import NonBlankId, Sha256Hex

UnitCoordinate = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class NativePdfRegionV1(DungeonMindModel):
    """Normalized edges relative to the displayed page, with a top-left origin."""

    schema_version: Literal["dm_native_pdf_region_v1"] = "dm_native_pdf_region_v1"
    source_revision_id: NonBlankId
    content_sha256: Sha256Hex
    page: int = Field(strict=True, ge=1)
    left: UnitCoordinate
    top: UnitCoordinate
    right: UnitCoordinate
    bottom: UnitCoordinate

    @model_validator(mode="after")
    def _validate_nonempty(self) -> Self:
        if self.left >= self.right or self.top >= self.bottom:
            raise ValueError("PDF region must have positive width and height")
        return self
