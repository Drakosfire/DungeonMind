"""A page region in one immutable PDF source revision."""

from datetime import datetime
from hashlib import sha256
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ..base import DungeonMindModel
from .common import NonBlankId, QualifiedTerm, Sha256Hex, VisibilityRequirement
from .source import SourceRevisionV2

UnitCoordinate = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class NativePdfRegionV1(DungeonMindModel):
    """Normalized edges in the default PDF.js page viewport.

    Use the effective visible page box (CropBox intersected with MediaBox,
    falling back to MediaBox when there is no nonempty intersection) and the
    page's intrinsic rotation. Coordinates start at the top left after that
    rotation. Viewer zoom, scrolling and additional rotation are excluded.
    """

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

    def validate_source(self, revision: SourceRevisionV2, *, body: bytes, page_count: int) -> None:
        """Check this region against the bytes of an authorized PDF revision."""
        if self.source_revision_id != revision.source_revision_id:
            raise ValueError("PDF region belongs to a different source revision")
        if self.content_sha256 != revision.content_sha256:
            raise ValueError("PDF region content hash does not match the source revision")
        if sha256(body).hexdigest() != revision.content_sha256:
            raise ValueError("PDF body digest does not match the source revision")
        if self.page > page_count:
            raise ValueError("PDF region page is outside the source revision")


class NativePdfSourceAdmissionV1(DungeonMindModel):
    """Identity and access policy for one immutable PDF upload."""

    schema_version: Literal["dm_native_pdf_source_admission_v1"] = (
        "dm_native_pdf_source_admission_v1"
    )
    space_id: NonBlankId
    admission_id: NonBlankId
    created_at: datetime
    source_classification: QualifiedTerm
    authority: Literal["primary", "derived", "reference"]
    content_sha256: Sha256Hex
    visibility: VisibilityRequirement = Field(discriminator="kind")

    @model_validator(mode="after")
    def _validate_timestamp(self) -> Self:
        if self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return self

    def validate_body(self, body: bytes) -> None:
        if not body.startswith(b"%PDF-"):
            raise ValueError("Source must begin with a PDF header")
        if sha256(body).hexdigest() != self.content_sha256:
            raise ValueError("PDF body digest does not match the admission request")
