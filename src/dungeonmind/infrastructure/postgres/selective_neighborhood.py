"""Opt-in exact-pin neighborhoods over authenticated PostgreSQL projections."""

from collections.abc import Sequence
from typing import Any, Literal

from psycopg import Connection, sql

from dungeonmind.application.vnext._read_artifact import _parse_authenticated_fact_rows
from dungeonmind.application.vnext._selective_read_proof import (
    open_selective_read_proof,
    verify_selective_buckets,
    verify_selective_records,
)
from dungeonmind.application.vnext.admission import DomainAdmissionPolicy
from dungeonmind.application.vnext.native_source_access import NativeParsedRevisionCache
from dungeonmind.application.vnext.neighborhood import (
    NeighborhoodReadService,
    NeighborhoodResult,
    _normalize_depth,
    _normalize_seeds,
)
from dungeonmind.application.vnext.read_context import KnowledgeReadContext
from dungeonmind.contracts.vnext.domain import DomainContractDescriptor, SemanticProfileDescriptorV2
from dungeonmind.contracts.vnext.knowledge import KnowledgeRevision
from dungeonmind.contracts.vnext.projection import ProjectionRequest
from dungeonmind.domain.errors import PersistenceIntegrityError

from .database import PostgresDatabase
from .selective_read_projection import _SOURCE_SQL_SHA256
from .vnext_knowledge import SCHEMA, _normalize
from .vnext_sources import PostgresNativeSourceEvidenceRepository


def _load_activation(
    connection: Connection[Any],
    pin: tuple[str, str],
) -> tuple[KnowledgeRevision, str, bytes] | None:
    # First establish activation presence without detoasting the primary graph.
    anchor = connection.execute(
        sql.SQL(
            "SELECT * FROM {}.selective_read_activations WHERE space_id=%s AND revision_id=%s"
        ).format(sql.Identifier(SCHEMA)),
        pin,
    ).fetchone()
    if anchor is None:
        return None
    row = connection.execute(
        sql.SQL(f"""
            SELECT schema_version, space_id, revision_id, parent_revision_id, graph_schema,
                   graph_payload_sha256, created_at, revision_payload, record_fingerprint,
                   {_SOURCE_SQL_SHA256} AS source_sql_sha256
            FROM {{}}.knowledge_revisions WHERE space_id=%s AND revision_id=%s
        """).format(sql.Identifier(SCHEMA)),
        pin,
    ).fetchone()
    if (
        row is None
        or anchor["source_sql_sha256"] != row["source_sql_sha256"]
        or anchor["source_record_fingerprint"] != row["record_fingerprint"]
    ):
        raise PersistenceIntegrityError("selective projection primary revision drift")
    try:
        revision = KnowledgeRevision.model_validate(row["revision_payload"])
    except ValueError as exc:
        raise PersistenceIntegrityError("selective projection revision header is invalid") from exc
    columns = (
        "schema_version",
        "space_id",
        "revision_id",
        "parent_revision_id",
        "graph_schema",
        "graph_payload_sha256",
    )
    if any(row[key] != getattr(revision, key) for key in columns) or _normalize(
        row["created_at"]
    ) != _normalize(revision.created_at):
        raise PersistenceIntegrityError("selective projection revision header drift")
    proof = connection.execute(
        sql.SQL(
            "SELECT content FROM {}.selective_read_proofs WHERE space_id=%s AND revision_id=%s"
        ).format(sql.Identifier(SCHEMA)),
        pin,
    ).fetchone()
    if proof is None:
        raise PersistenceIntegrityError("active selective projection proof is missing")
    return revision, anchor["proof_sha256"], bytes(proof["content"])


def _fetch(
    connection: Connection[Any],
    pin: tuple[str, str],
    table: str,
    family: str,
    keys: Sequence[str],
) -> list[tuple[str, Any]]:
    if not keys:
        return []
    rows = connection.execute(
        sql.SQL("""
            SELECT key, value FROM {}.{}
            WHERE space_id=%s AND revision_id=%s AND family=%s AND key=ANY(%s)
        """).format(sql.Identifier(SCHEMA), sql.Identifier(table)),
        (*pin, family, list(keys)),
    ).fetchall()
    return [(row["key"], row["value"]) for row in rows]


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
    """Return a selective result, or None to use the ordinary exact-pin read.

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
        return None
    with database.transaction() as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        opened = _load_activation(connection, pin)
        if opened is None:
            return None
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
        assertions = facts("assertions", assertion_ids)
        for assertion in assertions:
            entity_ids.add(assertion["subject_entity_id"])
            value = assertion["value"]
            if value["kind"] == "entity_ref":
                entity_ids.add(value["entity_id"])
        evidence_ids = {
            evidence_id
            for assertion in assertions
            for evidence_id in assertion["metadata"]["evidence_ref_ids"]
        }
        projected = {
            "entities": facts("entities", entity_ids),
            "assertions": assertions,
            "aliases": [],
            "evidence": facts("evidence", evidence_ids),
        }

    parsed = _parse_authenticated_fact_rows(revision, projected)
    if parsed is None:
        raise PersistenceIntegrityError("active selective projection facts are invalid")
    view = PostgresNativeSourceEvidenceRepository(database).open_native_source_view(pin[0])
    context = KnowledgeReadContext(
        parsed=parsed,
        request=request,
        domain_contract=domain_contract,
        semantic_profile=semantic_profile,
        domain_policy=domain_policy,
        source_reader=view,
    )
    return NeighborhoodReadService().get_neighborhood(
        context,
        seeds,
        depth,
        require_admitted_seeds=require_admitted_seeds,
    )
