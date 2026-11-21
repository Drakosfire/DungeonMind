"""Exact-pin search and claim reads over sealed PostgreSQL projections."""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from psycopg import Connection

from dungeonmind.application.vnext._read_artifact import _parse_authenticated_fact_rows
from dungeonmind.application.vnext._selective_read_proof import (
    SelectiveReadProof,
    open_selective_read_proof,
    verify_selective_buckets,
    verify_selective_records,
)
from dungeonmind.application.vnext.admission import DomainAdmissionPolicy
from dungeonmind.application.vnext.builder import _parse_revision_identity
from dungeonmind.application.vnext.entity_reads import CompleteEntityLookupResult, EntityReadService
from dungeonmind.application.vnext.evidence_reads import (
    AssertionEvidenceResult,
    EvidenceReadService,
)
from dungeonmind.application.vnext.native_source_access import NativeTextSourceAccessContext
from dungeonmind.application.vnext.read_context import KnowledgeReadContext
from dungeonmind.application.vnext.search import SearchReadService, SearchResult, _require_query
from dungeonmind.application.vnext.search_normalize import tokenize_search_text
from dungeonmind.contracts.vnext.domain import DomainContractDescriptor, SemanticProfileDescriptorV2
from dungeonmind.contracts.vnext.knowledge import KnowledgeRevision
from dungeonmind.contracts.vnext.projection import ProjectionRequest
from dungeonmind.domain.errors import PersistenceIntegrityError, PersistenceUnavailableError

from ._selective_revision import _fetch, _load_activation
from .database import PostgresDatabase


class SelectiveQueryRead:
    """Scoped operations on one verified projection and coherent source view."""

    def __init__(
        self,
        connection: Connection[Any],
        revision: KnowledgeRevision,
        proof: SelectiveReadProof,
        request: ProjectionRequest,
        domain_contract: DomainContractDescriptor,
        semantic_profile: SemanticProfileDescriptorV2,
        domain_policy: DomainAdmissionPolicy,
        source_context: NativeTextSourceAccessContext,
    ) -> None:
        self._connection = connection
        self._revision = revision
        self._proof = proof
        self._request = request.model_copy(deep=True)
        self._domain = domain_contract.model_copy(deep=True)
        self._profile = semantic_profile.model_copy(deep=True)
        self._policy = domain_policy
        self._source_context = source_context
        self._pin = (revision.space_id, revision.revision_id)
        self._closed = False

    def search_entities(self, query: str, *, limit: int = 20) -> SearchResult:
        """Read sealed predicate, term and lexical postings before ordinary search."""
        raw, normalized = _require_query(query)
        assertion_ids = self._posting_ids("predicate", (normalized,))
        assertion_ids.update(self._posting_ids("term", (normalized,)))
        assertion_ids.update(self._posting_ids("lexical", tokenize_search_text(normalized)))
        context = self._context(assertion_ids, entity_ids={raw})
        return SearchReadService().search_entities(context, query, limit=limit)

    def get_complete_entities(
        self, entity_ids: Sequence[str],
    ) -> tuple[CompleteEntityLookupResult, ...]:
        """Fetch the complete subject, incoming relationship and alias closures."""
        keys = tuple(dict.fromkeys(entity_ids))
        assertion_ids = self._posting_ids("subject", keys)
        assertion_ids.update(
            entry[0] for bucket in self._buckets("incoming", keys) for entry in bucket
        )
        context = self._context(
            assertion_ids, entity_ids=set(keys), alias_ids=self._posting_ids("aliases", keys),
        )
        return EntityReadService().get_complete_entities(context, entity_ids)

    def get_assertions_evidence(
        self, assertion_ids: Sequence[str],
    ) -> tuple[AssertionEvidenceResult, ...]:
        """Evaluate exact assertion membership and support through ordinary admission."""
        context = self._context(set(assertion_ids))
        return EvidenceReadService().get_assertions_evidence(context, assertion_ids)

    def _buckets(self, family: str, keys: Sequence[str]) -> list[list[Any]]:
        self._assert_open()
        requested = tuple(dict.fromkeys(keys))
        fetched = dict(_fetch(
            self._connection, self._pin, "selective_read_buckets", family, requested,
        ))
        rows = [(key, fetched.get(key, [])) for key in requested]
        if any(not isinstance(value, list) for _, value in rows):
            raise PersistenceIntegrityError("selective posting bucket is not an array")
        verify_selective_buckets(self._proof, family, requested, rows)
        return [value for _, value in rows]

    def _posting_ids(self, family: str, keys: Sequence[str]) -> set[str]:
        return {item for bucket in self._buckets(family, keys) for item in bucket}

    def _facts(self, family: str, identifiers: set[str]) -> list[dict[str, Any]]:
        self._assert_open()
        keys = sorted(identifiers)
        rows = _fetch(self._connection, self._pin, "selective_read_records", family, keys)
        verify_selective_records(self._proof, family, keys, rows)
        return [value for _, value in rows]

    def _context(
        self,
        assertion_ids: set[str],
        *,
        entity_ids: set[str] | None = None,
        alias_ids: set[str] | None = None,
    ) -> KnowledgeReadContext:
        assertions = self._facts("assertions", assertion_ids)
        aliases = self._facts("aliases", alias_ids or set())
        entities = set() if entity_ids is None else set(entity_ids)
        evidence_ids: set[str] = set()
        for assertion in assertions:
            entities.add(assertion["subject_entity_id"])
            value = assertion["value"]
            if value["kind"] == "entity_ref":
                entities.add(value["entity_id"])
            evidence_ids.update(assertion["metadata"]["evidence_ref_ids"])
        for alias in aliases:
            entities.add(alias["entity_id"])
            evidence_ids.update(alias["evidence_ref_ids"])
        parsed = _parse_authenticated_fact_rows(
            self._revision,
            {
                "entities": self._facts("entities", entities),
                "assertions": assertions,
                "aliases": aliases,
                "evidence": self._facts("evidence", evidence_ids),
            },
        )
        if parsed is None:
            raise PersistenceIntegrityError("selective query facts are invalid")
        return KnowledgeReadContext(
            parsed=parsed,
            request=self._request,
            domain_contract=self._domain,
            semantic_profile=self._profile,
            domain_policy=self._policy,
            source_reader=self._source_context.source_view,
        )

    def _assert_open(self) -> None:
        if self._closed:
            raise PersistenceUnavailableError("selective query scope is closed")


@contextmanager
def open_selective_query(
    database: PostgresDatabase,
    *,
    request: ProjectionRequest,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2,
    domain_policy: DomainAdmissionPolicy,
    source_context: NativeTextSourceAccessContext,
) -> Iterator[SelectiveQueryRead | None]:
    """Keep one authenticated projection transaction across a query's read waves.

    The source authority remains pinned to the caller's acquisition epoch.
    Release this scope before provider or controller waits.
    """
    if request.revision_id is None:
        raise ValueError("selective query requires an exact revision")
    pin = (request.space_id, request.revision_id)
    if pin != (source_context.space_id, source_context.revision_id):
        raise PersistenceIntegrityError("selective query and source pins differ")
    with database.transaction() as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        activation = _load_activation(connection, pin)
        if activation is None:
            yield None
            return
        revision, digest, content = activation
        if _parse_revision_identity(revision) != source_context.parsed.identity:
            raise PersistenceIntegrityError("selective query and source revisions differ")
        proof = open_selective_read_proof(content, expected_sha256=digest, revision=revision)
        reader = SelectiveQueryRead(
            connection, revision, proof, request, domain_contract, semantic_profile, domain_policy,
            source_context,
        )
        try:
            yield reader
        finally:
            reader._closed = True
