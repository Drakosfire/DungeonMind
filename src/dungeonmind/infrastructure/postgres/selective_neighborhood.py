"""Opt-in exact-pin neighborhoods over authenticated PostgreSQL projections."""

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Literal

from dungeonmind.application.vnext._read_artifact import _parse_authenticated_fact_rows
from dungeonmind.application.vnext._selective_read_proof import (
    open_selective_read_proof,
    verify_selective_buckets,
    verify_selective_records,
)
from dungeonmind.application.vnext.admission import DomainAdmissionPolicy
from dungeonmind.application.vnext.entity_reads import EntityLookupResult, EntityReadService
from dungeonmind.application.vnext.native_source_access import NativeParsedRevisionCache
from dungeonmind.application.vnext.neighborhood import (
    NeighborhoodReadService,
    NeighborhoodResult,
    _normalize_depth,
    _normalize_seeds,
)
from dungeonmind.application.vnext.ports import NativeTextSourceView
from dungeonmind.application.vnext.read_context import KnowledgeReadContext
from dungeonmind.contracts.vnext.domain import DomainContractDescriptor, SemanticProfileDescriptorV2
from dungeonmind.contracts.vnext.projection import ProjectionRequest
from dungeonmind.domain.errors import PersistenceIntegrityError

from ._selective_revision import _fetch, _load_activation
from .database import PostgresDatabase
from .vnext_sources import PostgresNativeSourceEvidenceRepository


def read_selective_neighborhood(
    database: PostgresDatabase,
    *,
    request: ProjectionRequest,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2,
    domain_policy: DomainAdmissionPolicy,
    seed_entity_ids: Sequence[str],
    depth: Literal[1, 2] = 1,
    require_admitted_seeds: bool = False,
    parsed_cache: NativeParsedRevisionCache | None = None,
) -> NeighborhoodResult | None:
    """Read a selective neighborhood, or request ordinary exact-pin fallback."""
    with open_selective_neighborhood(
        database,
        request=request,
        domain_contract=domain_contract,
        semantic_profile=semantic_profile,
        domain_policy=domain_policy,
        seed_entity_ids=seed_entity_ids,
        depth=depth,
        require_admitted_seeds=require_admitted_seeds,
        parsed_cache=parsed_cache,
    ) as opened:
        return None if opened is None else opened.result


@dataclass(frozen=True, slots=True)
class SelectiveNeighborhoodRead:
    result: NeighborhoodResult
    source_reader: NativeTextSourceView
    read_entities: Callable[[Sequence[str]], tuple[EntityLookupResult, ...]]


@contextmanager
def open_selective_neighborhood(
    database: PostgresDatabase,
    *,
    request: ProjectionRequest,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2,
    domain_policy: DomainAdmissionPolicy,
    seed_entity_ids: Sequence[str],
    depth: Literal[1, 2] = 1,
    require_admitted_seeds: bool = False,
    parsed_cache: NativeParsedRevisionCache | None = None,
) -> Iterator[SelectiveNeighborhoodRead | None]:
    """Open a selective result and scoped presentation reader for this request.

    Scope/visibility and provenance are evaluated by the ordinary service
    against a fresh source view. Structural overfetch through unadmitted
    edges is internal and may never contribute to the returned traversal.
    """
    seeds = _normalize_seeds(seed_entity_ids)
    depth = _normalize_depth(depth)
    if request.revision_id is None:
        raise ValueError("selective neighborhood requires an exact revision")
    pin = (request.space_id, request.revision_id)
    if parsed_cache is not None and parsed_cache._has_parsed_pin(*pin):
        yield None
        return
    with database.transaction() as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        opened = _load_activation(connection, pin)
        if opened is None:
            yield None
            return
        revision, digest, content = opened
        proof = open_selective_read_proof(content, expected_sha256=digest, revision=revision)

        def buckets(family: str, keys: Sequence[str]) -> list[list[Any]]:
            fetched = dict(_fetch(connection, pin, "selective_read_buckets", family, keys))
            rows = [(key, fetched.get(key, [])) for key in keys]
            verify_selective_buckets(proof, family, keys, rows)
            return [value for _, value in rows]

        def facts(family: str, keys: set[str]) -> list[dict[str, Any]]:
            rows = _fetch(connection, pin, "selective_read_records", family, sorted(keys))
            verify_selective_records(proof, family, sorted(keys), rows)
            return [record for _, record in rows]

        entity_ids = set(seeds)
        assertion_ids: set[str] = set()
        frontier = sorted(entity_ids)
        for _ in range(depth):
            endpoints: set[str] = set()
            for direction in ("outgoing", "incoming"):
                for bucket in buckets(direction, frontier):
                    for aid, subject, target in bucket:
                        assertion_ids.add(aid)
                        endpoints.update((subject, target))
            frontier = sorted(endpoints - entity_ids)
            entity_ids.update(endpoints)

        if require_admitted_seeds:
            for bucket in buckets("subject", seeds):
                assertion_ids.update(bucket)
        view = PostgresNativeSourceEvidenceRepository(database).open_native_source_view(pin[0])

        def read_context(ids: set[str], entities: set[str]) -> KnowledgeReadContext:
            assertions = facts("assertions", ids)
            required_entities = set(entities)
            for assertion in assertions:
                required_entities.add(assertion["subject_entity_id"])
                value = assertion["value"]
                if value["kind"] == "entity_ref":
                    required_entities.add(value["entity_id"])
            evidence_ids = {
                evidence_id
                for assertion in assertions
                for evidence_id in assertion["metadata"]["evidence_ref_ids"]
            }
            parsed = _parse_authenticated_fact_rows(
                revision,
                {
                    "entities": facts("entities", required_entities),
                    "assertions": assertions,
                    "aliases": [],
                    "evidence": facts("evidence", evidence_ids),
                },
            )
            if parsed is None:
                raise PersistenceIntegrityError("active selective projection facts are invalid")
            return KnowledgeReadContext(
                parsed=parsed,
                request=request,
                domain_contract=domain_contract,
                semantic_profile=semantic_profile,
                domain_policy=domain_policy,
                source_reader=view,
            )

        context = read_context(assertion_ids, entity_ids)
        result = NeighborhoodReadService().get_neighborhood(
            context,
            seeds,
            depth,
            require_admitted_seeds=require_admitted_seeds,
        )
        admitted_nodes = frozenset(entity.entity_id for entity in result.entities)
        active = True

        def read_entities(ids: Sequence[str]) -> tuple[EntityLookupResult, ...]:
            if not active:
                raise PersistenceIntegrityError("selective neighborhood read is closed")
            requested = tuple(ids)
            unique = set(requested)
            if not unique.issubset(admitted_nodes):
                raise ValueError("presentation entities must belong to the authorized neighborhood")
            if not requested:
                return ()
            subject_ids = {aid for bucket in buckets("subject", sorted(unique)) for aid in bucket}
            presentation = read_context(subject_ids, unique)
            service = EntityReadService()
            return tuple(service.get_entity(presentation, key) for key in requested)

        try:
            yield SelectiveNeighborhoodRead(result, view, read_entities)
        finally:
            active = False
