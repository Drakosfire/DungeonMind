"""Immutable internal records for vNext parsed knowledge representation.

All records are defined as `@dataclass(frozen=True, slots=True)` with immutable
collections (tuples, FrozenDicts) to guarantee isolation against caller mutation.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from dungeonmind.contracts.vnext.common import KnowledgeStanding
from dungeonmind.contracts.vnext.knowledge import KnowledgeRevision
from dungeonmind.domain.canonical import canonical_json, canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError

from .frozen_json import FrozenJsonValue


@dataclass(frozen=True, slots=True)
class ParsedEntity:
    """Internal immutable record representing a graph entity."""

    entity_id: str


@dataclass(frozen=True, slots=True)
class ParsedScopeBinding:
    """Internal immutable record representing a scope binding."""

    axis: str
    value: str


@dataclass(frozen=True, slots=True)
class ParsedPublicVisibility:
    """Public visibility requirement."""

    kind: Literal["public"] = "public"


@dataclass(frozen=True, slots=True)
class ParsedLabelsAnyVisibility:
    """Any-of labels visibility requirement."""

    labels: tuple[str, ...]
    kind: Literal["labels_any"] = "labels_any"


@dataclass(frozen=True, slots=True)
class ParsedLabelsAllVisibility:
    """All-of labels visibility requirement."""

    labels: tuple[str, ...]
    kind: Literal["labels_all"] = "labels_all"


ParsedVisibility = ParsedPublicVisibility | ParsedLabelsAnyVisibility | ParsedLabelsAllVisibility


@dataclass(frozen=True, slots=True)
class ParsedTimelessTemporalScope:
    """Timeless temporal scope."""

    kind: Literal["timeless"] = "timeless"


@dataclass(frozen=True, slots=True)
class ParsedUnknownTemporalScope:
    """Unknown temporal scope."""

    kind: Literal["unknown"] = "unknown"


@dataclass(frozen=True, slots=True)
class ParsedUtcIntervalTemporalScope:
    """UTC interval temporal scope."""

    valid_from: datetime | None = None
    valid_until: datetime | None = None
    kind: Literal["utc_interval"] = "utc_interval"


@dataclass(frozen=True, slots=True)
class ParsedDomainTemporalScope:
    """Domain-extended temporal scope."""

    schema_term: str
    payload: FrozenJsonValue
    kind: Literal["domain_ref"] = "domain_ref"


ParsedTemporalScope = (
    ParsedTimelessTemporalScope
    | ParsedUnknownTemporalScope
    | ParsedUtcIntervalTemporalScope
    | ParsedDomainTemporalScope
)


@dataclass(frozen=True, slots=True)
class ParsedDomainMetadataEntry:
    """Internal immutable record representing a domain metadata entry."""

    schema_term: str
    payload: FrozenJsonValue


@dataclass(frozen=True, slots=True)
class ParsedEntityRefValue:
    """Assertion value pointing to another entity."""

    entity_id: str
    kind: Literal["entity_ref"] = "entity_ref"


@dataclass(frozen=True, slots=True)
class ParsedLiteralValue:
    """Assertion value containing arbitrary JSON literal data."""

    value: FrozenJsonValue
    canonical_json_text: str
    kind: Literal["literal"] = "literal"


@dataclass(frozen=True, slots=True)
class ParsedTermRefValue:
    """Assertion value referencing a qualified vocabulary term."""

    term: str
    kind: Literal["term_ref"] = "term_ref"


ParsedAssertionValue = ParsedEntityRefValue | ParsedLiteralValue | ParsedTermRefValue


@dataclass(frozen=True, slots=True)
class ParsedAssertionMetadata:
    """Internal immutable record representing assertion metadata."""

    scope: tuple[ParsedScopeBinding, ...]
    visibility: ParsedVisibility
    epistemic_basis: str
    claim_mode: str
    standing: KnowledgeStanding
    evidence_ref_ids: tuple[str, ...]
    temporal_scope: ParsedTemporalScope
    domain_metadata: tuple[ParsedDomainMetadataEntry, ...]


@dataclass(frozen=True, slots=True)
class ParsedAssertion:
    """Internal immutable record representing a knowledge assertion."""

    assertion_id: str
    subject_entity_id: str
    predicate: str
    value: ParsedAssertionValue
    metadata: ParsedAssertionMetadata


@dataclass(frozen=True, slots=True)
class ParsedIdentityAlias:
    """Internal immutable record representing an identity alias."""

    alias_id: str
    entity_id: str
    alias_text: str
    evidence_ref_ids: tuple[str, ...]
    standing: KnowledgeStanding


@dataclass(frozen=True, slots=True)
class ParsedEvidenceRef:
    """Internal immutable record representing an evidence reference."""

    evidence_ref_id: str
    source_artifact_id: str
    source_revision_id: str | None
    evidence_role: str
    can_open_source: bool
    can_highlight_span: bool
    locator: str | None
    uri: str | None
    source_locator: str | None
    line_ref: str | None
    source_span_ref_id: str | None
    domain_metadata: tuple[ParsedDomainMetadataEntry, ...]


@dataclass(frozen=True, slots=True)
class ParsedDomainContractRef:
    """Internal immutable record for pinned domain contract reference."""

    domain_id: str
    domain_revision: str
    descriptor_sha256: str


@dataclass(frozen=True, slots=True)
class ParsedSemanticProfileRef:
    """Internal immutable record for pinned semantic profile reference."""

    profile_id: str
    profile_revision: str
    descriptor_sha256: str


@dataclass(frozen=True, slots=True)
class ParsedMigrationOriginRef:
    """Internal immutable record for migration provenance."""

    source_system: str
    source_root_id: str
    source_revision_id: str
    source_payload_sha256: str
    migration_manifest_sha256: str


@dataclass(frozen=True, slots=True)
class ParsedKnowledgeRevisionIdentity:
    """Exact identity fields copied from KnowledgeRevision header."""

    space_id: str
    revision_id: str
    parent_revision_id: str | None
    created_at: datetime
    operation_ids: tuple[str, ...]
    graph_schema: str
    graph_payload_sha256: str
    domain_contract_ref: ParsedDomainContractRef
    semantic_profile_ref: ParsedSemanticProfileRef
    migration_origin_ref: ParsedMigrationOriginRef | None


@dataclass(frozen=True, slots=True)
class KnowledgeHeadEvent:
    """One native head transition. V5.2 writes ``publish`` only."""

    space_id: str
    event_kind: Literal["publish", "rollback"]
    previous_revision_id: str | None
    target_revision_id: str
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class StoredKnowledgeRevision:
    """Immutable revision plus an isolated canonical graph payload."""

    revision: KnowledgeRevision
    graph_payload_sha256: str
    _payload_json: str

    @staticmethod
    def seal(revision: KnowledgeRevision, payload: Mapping[str, Any]) -> StoredKnowledgeRevision:
        payload_json = canonical_json(dict(payload))
        digest = canonical_sha256(dict(payload))
        if digest != revision.graph_payload_sha256:
            raise PersistenceIntegrityError(
                "stored graph payload digest disagrees with the revision envelope"
            )
        return StoredKnowledgeRevision(
            revision=revision.model_copy(deep=True),
            graph_payload_sha256=digest,
            _payload_json=payload_json,
        )

    @property
    def graph_payload(self) -> dict[str, Any]:
        loaded = json.loads(self._payload_json)
        if not isinstance(loaded, dict):
            raise PersistenceIntegrityError("stored graph payload is not an object")
        if canonical_sha256(loaded) != self.graph_payload_sha256:
            raise PersistenceIntegrityError("stored graph payload digest drift")
        return loaded


@dataclass(frozen=True, slots=True)
class PublishedKnowledgeRevision:
    """Copy-on-read result of one successful native publication."""

    revision: KnowledgeRevision
    graph_payload_sha256: str
    _payload_json: str

    @staticmethod
    def from_stored(stored: StoredKnowledgeRevision) -> PublishedKnowledgeRevision:
        return PublishedKnowledgeRevision(
            revision=stored.revision.model_copy(deep=True),
            graph_payload_sha256=stored.graph_payload_sha256,
            _payload_json=stored._payload_json,
        )

    @property
    def graph_payload(self) -> dict[str, Any]:
        loaded = json.loads(self._payload_json)
        if not isinstance(loaded, dict):
            raise PersistenceIntegrityError("published graph payload is not an object")
        if canonical_sha256(loaded) != self.graph_payload_sha256:
            raise PersistenceIntegrityError("published graph payload digest drift")
        return loaded
