"""Additive contracts for prospective create-result publication."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, model_validator

from ..base import DungeonMindModel
from .common import DomainMetadataEntry, NonBlankId, QualifiedTerm, Sha256Hex
from .contribution import (
    ProposeAssertion,
    ProposeEntity,
    ProposeIdentityDecision,
    RetractAssertion,
    SupersedeAssertion,
)
from .domain import AssertionMetadata, LiteralValue, TermRefValue
from .publication import KnowledgePublicationReceipt


class DurableEntityRef(DungeonMindModel):
    kind: Literal["durable_entity"] = "durable_entity"
    entity_id: NonBlankId


class ProspectiveEntityRef(DungeonMindModel):
    kind: Literal["result_of"] = "result_of"
    client_op_id: NonBlankId


EntityOperand = Annotated[
    DurableEntityRef | ProspectiveEntityRef,
    Field(discriminator="kind"),
]


class ProspectiveEntityRefValue(DungeonMindModel):
    kind: Literal["entity_ref"] = "entity_ref"
    entity: EntityOperand


ProspectiveAssertionValue = Annotated[
    ProspectiveEntityRefValue | LiteralValue | TermRefValue,
    Field(discriminator="kind"),
]


class ProspectiveCreateEntity(DungeonMindModel):
    kind: Literal["create_entity"] = "create_entity"
    item_id: NonBlankId
    client_op_id: NonBlankId


class ProspectiveCreateAssertion(DungeonMindModel):
    kind: Literal["create_assertion"] = "create_assertion"
    item_id: NonBlankId
    client_op_id: NonBlankId
    subject: EntityOperand
    predicate: QualifiedTerm
    value: ProspectiveAssertionValue
    metadata: AssertionMetadata


ProspectiveContributionItem = Annotated[
    ProposeEntity
    | ProposeAssertion
    | RetractAssertion
    | SupersedeAssertion
    | ProposeIdentityDecision
    | ProspectiveCreateEntity
    | ProspectiveCreateAssertion,
    Field(discriminator="kind"),
]


class ProspectiveKnowledgeContribution(DungeonMindModel):
    schema_version: Literal["dm_prospective_knowledge_contribution_v1"] = (
        "dm_prospective_knowledge_contribution_v1"
    )
    contribution_id: NonBlankId
    space_id: NonBlankId
    producer: NonBlankId
    produced_at: datetime
    source_refs: list[NonBlankId] = Field(default_factory=list)
    status: NonBlankId
    supersedes_contribution_id: NonBlankId | None = None
    items: list[ProspectiveContributionItem] = Field(min_length=1)
    diagnostics: list[DomainMetadataEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_refs_and_items(self) -> ProspectiveKnowledgeContribution:
        if len(self.source_refs) != len(set(self.source_refs)):
            raise ValueError("source_refs must be unique")
        item_ids = [item.item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("item_id must be unique")
        return self


class ProspectiveResultBinding(DungeonMindModel):
    schema_version: Literal["dm_prospective_result_binding_v1"] = (
        "dm_prospective_result_binding_v1"
    )
    client_op_id: NonBlankId
    result_kind: Literal["entity", "assertion"]
    durable_id: NonBlankId

    @model_validator(mode="after")
    def _typed_id(self) -> ProspectiveResultBinding:
        prefix = "ent:" if self.result_kind == "entity" else "asrt:"
        if not self.durable_id.startswith(prefix):
            raise ValueError(f"{self.result_kind} durable_id must start with {prefix!r}")
        return self


class KnowledgeProspectivePublicationResult(DungeonMindModel):
    schema_version: Literal["dm_knowledge_prospective_publication_result_v1"] = (
        "dm_knowledge_prospective_publication_result_v1"
    )
    space_id: NonBlankId
    publication_id: NonBlankId
    prospective_request_sha256: Sha256Hex
    published_revision_id: NonBlankId
    results: list[ProspectiveResultBinding] = Field(default_factory=list)
    status: Literal["published"] = "published"

    @model_validator(mode="after")
    def _deterministic_bindings(self) -> KnowledgeProspectivePublicationResult:
        keys = [item.client_op_id for item in self.results]
        if len(keys) != len(set(keys)):
            raise ValueError("result client_op_id must be unique")
        if keys != sorted(keys):
            raise ValueError("results must be ordered by client_op_id")
        return self


class KnowledgeProspectivePublication(DungeonMindModel):
    publication_receipt: KnowledgePublicationReceipt
    prospective_result: KnowledgeProspectivePublicationResult

    @model_validator(mode="after")
    def _coherent_identity(self) -> KnowledgeProspectivePublication:
        receipt = self.publication_receipt
        result = self.prospective_result
        if (receipt.space_id, receipt.publication_id, receipt.published_revision_id) != (
            result.space_id,
            result.publication_id,
            result.published_revision_id,
        ):
            raise ValueError("prospective publication receipt/result identity mismatch")
        return self
