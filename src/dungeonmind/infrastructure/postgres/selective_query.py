"""Exact-pin search and claim reads over sealed PostgreSQL projections."""

from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from psycopg import Connection

from dungeonmind.application.vnext._read_artifact import (
    _decode_authenticated_fact_rows,
    _DecodedFacts,
)
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
from dungeonmind.application.vnext.native_source_access import (
    NativeTextSourceAccessContext,
    NativeTextSourceMembership,
    _verified_source_domain,
)
from dungeonmind.application.vnext.read_context import KnowledgeReadContext
from dungeonmind.application.vnext.records import ParsedEntityRefValue
from dungeonmind.application.vnext.search import SearchReadService, SearchResult, _require_query
from dungeonmind.application.vnext.search_normalize import tokenize_search_text
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext.domain import (
    DomainContractDescriptor,
    DomainContractRef,
    SemanticProfileDescriptorV2,
)
from dungeonmind.contracts.vnext.knowledge import KnowledgeRevision
from dungeonmind.contracts.vnext.projection import ProjectionRequest
from dungeonmind.domain.errors import PersistenceIntegrityError, PersistenceUnavailableError

from ._selective_query_facts import _SelectiveQueryFacts
from ._selective_revision import _fetch, _load_activation
from .database import PostgresDatabase
from .selective_native_sources import _read_membership, _source_context
from .vnext_sources import PostgresNativeSourceEvidenceRepository


@dataclass(frozen=True, slots=True)
class RetainedSelectiveQuery:
    """Verified immutable facts retained by the composer before its query closes."""

    _complete: Mapping[str, KnowledgeReadContext[_SelectiveQueryFacts]]

    def get_complete_entity(self, entity_id: str) -> CompleteEntityLookupResult:
        """Repeat ordinary complete-entity admission for a captured query entity."""
        context = self._complete.get(entity_id)
        if context is None:
            raise PersistenceIntegrityError("entity was not captured by the selective query")
        return EntityReadService().get_complete_entity(context, entity_id)

    def get_assertions_evidence(
        self, assertion_ids: Sequence[str],
    ) -> tuple[AssertionEvidenceResult, ...]:
        """Build ordered exact evidence from the query's already verified facts."""
        if not assertion_ids:
            return ()
        contexts = tuple({id(context): context for context in self._complete.values()}.values())
        preferred = next((
            context for context in contexts
            if all(context.parsed.get_assertion(key) is not None for key in assertion_ids)
        ), None)
        if preferred is not None:
            return EvidenceReadService().get_assertions_evidence(preferred, assertion_ids)
        return self._read_across_waves(contexts, assertion_ids)

    @staticmethod
    def _read_across_waves(
        contexts: Sequence[KnowledgeReadContext[_SelectiveQueryFacts]],
        assertion_ids: Sequence[str],
    ) -> tuple[AssertionEvidenceResult, ...]:
        if not contexts:
            raise PersistenceIntegrityError("no complete entities were captured by the query")
        assertions = {}
        for key in dict.fromkeys(assertion_ids):
            for context in contexts:
                row = context.parsed.get_assertion(key)
                if row is not None:
                    assertions[key] = row
                    break
            else:
                raise PersistenceIntegrityError("assertion was not captured by the selective query")
        evidence = {}
        entities = {}
        for context in contexts:
            evidence.update(context.parsed._evidence)
            entities.update(context.parsed._entities)
        required_entities = {row.subject_entity_id for row in assertions.values()}
        required_entities.update(
            row.value.entity_id for row in assertions.values()
            if isinstance(row.value, ParsedEntityRefValue)
        )
        required_evidence = {
            key for row in assertions.values() for key in row.metadata.evidence_ref_ids
        }
        retained = contexts[0]
        facts = _SelectiveQueryFacts.from_decoded(
            retained.parsed.identity,
            _DecodedFacts(
                entities=tuple(entities[key] for key in required_entities),
                assertions=tuple(assertions.values()),
                aliases=(),
                evidence=tuple(evidence[key] for key in required_evidence),
            ),
            {},
        )
        context = KnowledgeReadContext(
            parsed=facts,
            request=retained.request,
            domain_contract=retained.domain_contract,
            semantic_profile=retained.semantic_profile,
            domain_policy=retained.domain_policy,
            source_reader=retained.source_reader,
        )
        return EvidenceReadService().get_assertions_evidence(context, assertion_ids)


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
        self._complete: dict[str, KnowledgeReadContext[_SelectiveQueryFacts]] = {}

    def search_entities(self, query: str, *, limit: int = 20) -> SearchResult:
        """Read sealed predicate, term and lexical postings before ordinary search."""
        raw, normalized = _require_query(query)
        postings = {}
        for family, keys in (
            ("predicate", (normalized,)),
            ("term", (normalized,)),
            ("lexical", tuple(dict.fromkeys(tokenize_search_text(normalized)))),
        ):
            for key, values in zip(keys, self._buckets(family, keys), strict=True):
                postings[family, key] = tuple(values)
        assertion_ids = {identity for values in postings.values() for identity in values}
        context = self._context(assertion_ids, entity_ids={raw}, postings=postings)
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
        results = EntityReadService().get_complete_entities(context, entity_ids)
        self._complete.update(dict.fromkeys(keys, context))
        return results

    def retain_complete_facts(self) -> RetainedSelectiveQuery:
        """Release the projection transaction before handling controller input."""
        self._assert_open()
        return RetainedSelectiveQuery(MappingProxyType(self._complete.copy()))

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
        postings: Mapping[tuple[str, str], tuple[str, ...]] | None = None,
    ) -> KnowledgeReadContext[_SelectiveQueryFacts]:
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
        decoded = _decode_authenticated_fact_rows(
            {
                "entities": self._facts("entities", entities),
                "assertions": assertions,
                "aliases": aliases,
                "evidence": self._facts("evidence", evidence_ids),
            },
        )
        if decoded is None:
            raise PersistenceIntegrityError("selective query facts are invalid")
        parsed = _SelectiveQueryFacts.from_decoded(
            _parse_revision_identity(self._revision), decoded, postings or {},
        )
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


@contextmanager
def open_selective_source_query(
    repository: PostgresNativeSourceEvidenceRepository,
    *,
    request: ProjectionRequest,
    resolve_descriptors: Callable[
        [DomainContractRef, SemanticProfileRef],
        tuple[DomainContractDescriptor, SemanticProfileDescriptorV2],
    ],
    domain_policy: DomainAdmissionPolicy,
    source_audience_labels: Sequence[str] = (),
) -> Iterator[
    tuple[NativeTextSourceAccessContext[NativeTextSourceMembership], SelectiveQueryRead] | None
]:
    """Open source membership and query access from one exact projection proof."""
    if request.revision_id is None:
        raise ValueError("selective query requires an exact revision")
    pin = (request.space_id, request.revision_id)
    with repository._database.transaction() as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        activation = _load_activation(connection, pin)
        if activation is None:
            yield None
            return
        revision, digest, content = activation
        proof = open_selective_read_proof(content, expected_sha256=digest, revision=revision)
        domain, profile = resolve_descriptors(
            revision.domain_contract_ref, revision.semantic_profile_ref,
        )
        domain = _verified_source_domain(revision, domain)
        membership = _read_membership(connection, revision, proof)
        source = _source_context(repository, membership, domain, source_audience_labels)
        reader = SelectiveQueryRead(
            connection, revision, proof, request, domain, profile, domain_policy, source,
        )
        try:
            yield source, reader
        finally:
            reader._closed = True
