"""Receipt contract for atomic legacy source-pair admission."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import field_validator

from .base import DungeonMindModel

SOURCE_ADMISSION_RECEIPT_SCHEMA = "dm_source_admission_receipt_v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class SourceAdmissionReceiptV1(DungeonMindModel):
    """Durable proof that one exact immutable source pair was admitted."""

    schema_version: Literal["dm_source_admission_receipt_v1"] = (
        SOURCE_ADMISSION_RECEIPT_SCHEMA
    )
    admission_id: str
    world_id: str
    expected_head_revision_id: str
    source_artifact_id: str
    source_revision_id: str
    content_sha256: str
    command_sha256: str
    admitted_at: datetime

    @field_validator(
        "admission_id",
        "world_id",
        "expected_head_revision_id",
        "source_artifact_id",
        "source_revision_id",
    )
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source admission identity fields must be non-blank")
        return value

    @field_validator("content_sha256", "command_sha256")
    @classmethod
    def _sha256(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("source admission digests must be lowercase SHA-256 hex")
        return value

    @field_validator("admitted_at")
    @classmethod
    def _timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("admitted_at must be timezone-aware")
        return value
