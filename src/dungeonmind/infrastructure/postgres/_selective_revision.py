"""Read exact revision projections already authenticated by their publisher."""

from collections.abc import Sequence
from typing import Any

from psycopg import Connection, sql

from dungeonmind.contracts.vnext.knowledge import KnowledgeRevision
from dungeonmind.domain.errors import PersistenceIntegrityError

from .selective_read_projection import _SOURCE_SQL_SHA256
from .vnext_knowledge import SCHEMA, _normalize


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
