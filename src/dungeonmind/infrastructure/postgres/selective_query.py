"""Exact-pin search and claim reads over sealed PostgreSQL projections."""

from collections import defaultdict
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, cast

from psycopg import Connection, sql

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
from dungeonmind.application.vnext.admission import AlwaysAdmitPolicy, DomainAdmissionPolicy
from dungeonmind.application.vnext.builder import _parse_revision_identity
from dungeonmind.application.vnext.entity_reads import (
    CompleteEntityLookupResult,
    EntityClaimsResult,
    EntityReadService,
)
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
from dungeonmind.application.vnext.records import (
    ParsedAssertion,
    ParsedEntity,
    ParsedEntityRefValue,
    ParsedEvidenceRef,
    ParsedIdentityAlias,
)
from dungeonmind.application.vnext.search import (
    SearchReadService,
    SearchResult,
    _require_limit,
    _require_query,
)
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

from ._selective_fact_cache import Fact, SelectiveFactCache
from ._selective_query_facts import _SelectiveQueryFacts
from ._selective_revision import _fetch, _load_activation
from ._selective_search_rank import read_bounded_search
from .database import PostgresDatabase
from .selective_native_sources import _read_source_directory, _source_context
from .vnext_knowledge import SCHEMA
from .vnext_sources import PostgresNativeSourceEvidenceRepository


@dataclass(frozen=True, slots=True)
class RetainedSelectiveQuery:
    """Verified immutable facts retained by the composer before its query closes."""

    _complete: Mapping[str, KnowledgeReadContext[_SelectiveQueryFacts]]
    _claims: Mapping[str, KnowledgeReadContext[_SelectiveQueryFacts]] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def get_complete_entity(self, entity_id: str) -> CompleteEntityLookupResult:
        """Repeat ordinary complete-entity admission for a captured query entity."""
        context = self._complete.get(entity_id)
        if context is None:
            raise PersistenceIntegrityError("entity was not captured by the selective query")
        return EntityReadService().get_complete_entity(context, entity_id)

    def get_entity_claim(self, entity_id: str) -> EntityClaimsResult:
        """Reauthorize claims for an entity captured during discovery."""
        context = self._claims.get(entity_id) or self._complete.get(entity_id)
        if context is None:
            raise PersistenceIntegrityError(
                "entity claims were not captured by the selective query"
            )
        return EntityReadService().get_entity_claims(context, (entity_id,))[0]

    def get_assertions_evidence(
        self, assertion_ids: Sequence[str],
    ) -> tuple[AssertionEvidenceResult, ...]:
        """Build ordered exact evidence from the query's already verified facts."""
        if not assertion_ids:
            return ()
        contexts = tuple({
            id(context): context
            for captures in (self._complete, self._claims)
            for context in captures.values()
        }.values())
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
            raise PersistenceIntegrityError("no entity facts were captured by the query")
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
        fact_cache: SelectiveFactCache | None = None,
        *,
        _verified_evidence: Mapping[str, ParsedEvidenceRef] | None = None,
    ) -> None:
        self._connection = connection
        self._revision = revision
        self._proof = proof
        self._request = request.model_copy(deep=True)
        self._domain = domain_contract.model_copy(deep=True)
        self._profile = semantic_profile.model_copy(deep=True)
        self._policy = domain_policy
        self._source_context = source_context
        self._fact_cache = fact_cache
        self._verified_evidence = _verified_evidence
        self._pin = (revision.space_id, revision.revision_id)
        self._closed = False
        self._complete: dict[str, KnowledgeReadContext[_SelectiveQueryFacts]] = {}
        self._claims: dict[str, KnowledgeReadContext[_SelectiveQueryFacts]] = {}

    def search_entities(self, query: str, *, limit: int = 20) -> SearchResult:
        """Read sealed predicate, term and lexical postings before ordinary search."""
        raw, normalized = _require_query(query)
        limit = _require_limit(limit)
        postings = {}
        for family, keys in (
            ("predicate", (normalized,)),
            ("term", (normalized,)),
            ("lexical", tuple(dict.fromkeys(tokenize_search_text(normalized)))),
        ):
            for key, values in zip(keys, self._buckets(family, keys), strict=True):
                postings[family, key] = frozenset(values)
        assertion_ids = {identity for values in postings.values() for identity in values}

        def read_wave(
            subjects: set[str], buckets: Mapping[tuple[str, str], tuple[str, ...]],
        ) -> SearchResult:
            selected = {identity for values in buckets.values() for identity in values}
            context = self._context(
                selected, entity_ids={raw} if raw in subjects else set(), postings=buckets,
            )
            return SearchReadService().search_entities(context, query, limit=limit)

        if type(self._policy) is AlwaysAdmitPolicy and 0 < limit < 128 and len(assertion_ids) > 256:
            return read_bounded_search(
                raw_query=raw,
                normalized_query=normalized,
                limit=limit,
                exact_entity_exists=raw in self._proof.records["entities"],
                postings=postings,
                subject_assertions=self._verified_search_subjects(assertion_ids),
                read_wave=read_wave,
            )
        return read_wave({raw}, {key: tuple(sorted(values)) for key, values in postings.items()})

    def _verified_search_subjects(self, assertion_ids: set[str]) -> dict[str, set[str]]:
        # Fast assignments from JSONB are a hint. Each assignment must be backed
        # by the exact assertion directory and the publisher's sealed subject posting.
        if not assertion_ids <= self._proof.records["assertions"].keys():
            raise PersistenceIntegrityError("selective search posting references an unknown claim")
        rows = self._connection.execute(
            sql.SQL("""
                SELECT key, value->>'subject_entity_id' AS subject
                FROM {}.selective_read_records
                WHERE space_id=%s AND revision_id=%s AND family='assertions' AND key=ANY(%s)
            """).format(sql.Identifier(SCHEMA)),
            (*self._pin, sorted(assertion_ids)),
        ).fetchall()
        if len(rows) != len(assertion_ids) or {row["key"] for row in rows} != assertion_ids:
            raise PersistenceIntegrityError("selective search subject assignments are incomplete")
        by_subject: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            subject = row["subject"]
            if not isinstance(subject, str) or subject not in self._proof.records["entities"]:
                raise PersistenceIntegrityError("selective search subject is invalid")
            by_subject[subject].add(row["key"])
        subjects = tuple(sorted(by_subject))
        for subject, certified in zip(subjects, self._buckets("subject", subjects), strict=True):
            if not by_subject[subject] <= set(certified):
                raise PersistenceIntegrityError("selective search subject assignment seal mismatch")
        return dict(by_subject)

    def get_complete_entities(
        self, entity_ids: Sequence[str],
    ) -> tuple[CompleteEntityLookupResult, ...]:
        """Fetch the complete subject, incoming relationship and alias closures."""
        context = self._entity_context(entity_ids, include_aliases=True)
        results = EntityReadService().get_complete_entities(context, entity_ids)
        self._complete.update(dict.fromkeys(entity_ids, context))
        return results

    def get_entity_claims(self, entity_ids: Sequence[str]) -> tuple[EntityClaimsResult, ...]:
        """Fetch the exact subject and incoming claim closures for discovery."""
        context = self._entity_context(entity_ids, include_aliases=False)
        results = EntityReadService().get_entity_claims(context, entity_ids)
        self._claims.update(dict.fromkeys(entity_ids, context))
        return results

    def _entity_context(
        self, entity_ids: Sequence[str], *, include_aliases: bool,
    ) -> KnowledgeReadContext[_SelectiveQueryFacts]:
        keys = tuple(dict.fromkeys(entity_ids))
        assertion_ids = self._posting_ids("subject", keys)
        assertion_ids.update(
            entry[0] for bucket in self._buckets("incoming", keys) for entry in bucket
        )
        return self._context(
            assertion_ids,
            entity_ids=set(keys),
            alias_ids=self._posting_ids("aliases", keys) if include_aliases else None,
        )

    def retain_complete_facts(self) -> RetainedSelectiveQuery:
        """Release the projection transaction before handling controller input."""
        self._assert_open()
        return RetainedSelectiveQuery(
            MappingProxyType(self._complete.copy()), MappingProxyType(self._claims.copy()),
        )

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

    def _decoded(self, family: str, identifiers: set[str]) -> tuple[Fact, ...]:
        self._assert_open()
        keys = sorted(identifiers)
        evidence = self._verified_evidence
        if family == "evidence" and evidence is not None:
            return tuple(evidence[key] for key in keys if key in evidence)
        cache = self._fact_cache
        seals = self._proof.records[family]
        found = {} if cache is None else cache._read(self._pin, family, keys, seals)
        rows = self._facts(family, identifiers - found.keys())
        key_field = {
            "assertions": "assertion_id", "aliases": "alias_id", "entities": "entity_id",
            "evidence": "evidence_ref_id",
        }[family]
        if not rows:
            return tuple(found[key] for key in keys if key in found)
        wire_sizes = (
            {row[key_field]: len(repr(row).encode("utf-8")) for row in rows}
            if cache is not None else {}
        )
        inputs = {name: [] for name in ("assertions", "aliases", "entities", "evidence")}
        inputs[family] = rows
        decoded = _decode_authenticated_fact_rows(inputs)
        if decoded is None:
            raise PersistenceIntegrityError("selective query facts are invalid")
        verified = {getattr(record, key_field): record for record in getattr(decoded, family)}
        if cache is not None:
            cache._remember(
                self._pin, family, {key: (fact, wire_sizes[key]) for key, fact in verified.items()},
                seals,
            )
        found.update(verified)
        return tuple(found[key] for key in keys if key in found)

    def _context(
        self,
        assertion_ids: set[str],
        *,
        entity_ids: set[str] | None = None,
        alias_ids: set[str] | None = None,
        postings: Mapping[tuple[str, str], tuple[str, ...]] | None = None,
    ) -> KnowledgeReadContext[_SelectiveQueryFacts]:
        assertions = cast(tuple[ParsedAssertion, ...], self._decoded("assertions", assertion_ids))
        aliases = cast(
            tuple[ParsedIdentityAlias, ...], self._decoded("aliases", alias_ids or set()),
        )
        entities = set() if entity_ids is None else set(entity_ids)
        evidence_ids: set[str] = set()
        for assertion in assertions:
            entities.add(assertion.subject_entity_id)
            if isinstance(assertion.value, ParsedEntityRefValue):
                entities.add(assertion.value.entity_id)
            evidence_ids.update(assertion.metadata.evidence_ref_ids)
        for alias in aliases:
            entities.add(alias.entity_id)
            evidence_ids.update(alias.evidence_ref_ids)
        decoded = _DecodedFacts(
            entities=cast(tuple[ParsedEntity, ...], self._decoded("entities", entities)),
            assertions=assertions,
            aliases=aliases,
            evidence=cast(tuple[ParsedEvidenceRef, ...], self._decoded("evidence", evidence_ids)),
        )
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
    fact_cache: SelectiveFactCache | None = None,
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
        membership = _read_source_directory(connection, revision, proof)
        source = _source_context(repository, membership, domain, source_audience_labels)
        reader = SelectiveQueryRead(
            connection, revision, proof, request, domain, profile, domain_policy, source,
            fact_cache=fact_cache,
            _verified_evidence=membership.evidence_by_id,
        )
        try:
            yield source, reader
        finally:
            reader._closed = True
