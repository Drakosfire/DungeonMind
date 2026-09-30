"""Durable receipt for one canonical empty KnowledgeSpace provisioning request."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ..base import DungeonMindModel
from .publication import KnowledgePublicationReceipt


class KnowledgeSpaceProvisioningReceipt(DungeonMindModel):
    schema_version: Literal["dm_knowledge_space_provisioning_receipt_v1"] = (
        "dm_knowledge_space_provisioning_receipt_v1"
    )
    allocation_id: str = Field(min_length=1)
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    space_id: str = Field(min_length=1)
    publication_receipt: KnowledgePublicationReceipt
    status: Literal["provisioned"] = "provisioned"

    @model_validator(mode="after")
    def _receipt_binding(self) -> KnowledgeSpaceProvisioningReceipt:
        if not self.allocation_id.strip() or not self.space_id.strip():
            raise ValueError("provisioning identity must not be blank")
        if self.publication_receipt.space_id != self.space_id:
            raise ValueError("provisioning receipt space mismatch")
        if self.publication_receipt.expected_parent_revision_id is not None:
            raise ValueError("empty-space genesis must not have a parent")
        return self
