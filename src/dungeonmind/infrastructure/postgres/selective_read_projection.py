"""Opt-in PostgreSQL publication of exact-revision selective read projections."""

from hashlib import sha256

from psycopg import sql

from dungeonmind.application.vnext._selective_read_proof import (
    build_selective_read_projection,
    open_selective_read_proof,
)
from dungeonmind.domain.errors import PersistenceIntegrityError

from .database import PostgresDatabase, jsonb
from .vnext_knowledge import SCHEMA, _read_revision

# This digest binds the current PostgreSQL representation. It supplements
# the canonical Core verification performed by the publisher. An output
# representation change across PostgreSQL versions requires reactivation.
_SOURCE_SQL_SHA256 = "encode(sha256(convert_to(graph_payload::text, 'UTF8')), 'hex')"


def publish_selective_read_projection(
    database: PostgresDatabase,
    *,
    space_id: str,
    revision_id: str,
) -> str:
    """Derive one verified projection and make it visible in a single commit.

    The authoritative writer owns the activation row. Read-model rows and the
    proof directory cannot establish authority without the activation digest.
    This operation is explicit and does not run in normal Graph publication.
    """
    pin = (space_id, revision_id)
    with database.transaction() as connection:
        stored = _read_revision(connection, *pin, lock=True)
        if stored is None:
            raise PersistenceIntegrityError("selective projection source revision is missing")
        source = connection.execute(
            sql.SQL(f"""
                SELECT {_SOURCE_SQL_SHA256} AS source_sql_sha256, record_fingerprint
                FROM {{}}.knowledge_revisions WHERE space_id = %s AND revision_id = %s
            """).format(sql.Identifier(SCHEMA)),
            pin,
        ).fetchone()
        if source is None:
            raise PersistenceIntegrityError("selective projection locked revision disappeared")
        source_digest = source["source_sql_sha256"]
        source_fingerprint = source["record_fingerprint"]
        projection = build_selective_read_projection(stored)
        digest = sha256(projection.proof).hexdigest()
        inserted = connection.execute(
            sql.SQL("""
                INSERT INTO {}.selective_read_activations (
                    space_id, revision_id, proof_sha256, source_sql_sha256,
                    source_record_fingerprint
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (space_id, revision_id) DO NOTHING
                RETURNING proof_sha256
            """).format(sql.Identifier(SCHEMA)),
            (*pin, digest, source_digest, source_fingerprint),
        ).fetchone()
        if inserted is None:
            existing = connection.execute(
                sql.SQL("""
                    SELECT a.proof_sha256, a.source_sql_sha256,
                           a.source_record_fingerprint, p.content
                    FROM {}.selective_read_activations a
                    JOIN {}.selective_read_proofs p USING (space_id, revision_id)
                    WHERE a.space_id = %s AND a.revision_id = %s
                """).format(sql.Identifier(SCHEMA), sql.Identifier(SCHEMA)),
                pin,
            ).fetchone()
            if (
                existing is None
                or existing["proof_sha256"] != digest
                or existing["source_sql_sha256"] != source_digest
                or existing["source_record_fingerprint"] != source_fingerprint
            ):
                raise PersistenceIntegrityError("selective projection activation drift")
            open_selective_read_proof(
                bytes(existing["content"]),
                expected_sha256=digest,
                revision=stored.revision,
            )
            return digest
        connection.execute(
            sql.SQL("""
                INSERT INTO {}.selective_read_proofs (space_id, revision_id, content)
                VALUES (%s, %s, %s)
            """).format(sql.Identifier(SCHEMA)),
            (*pin, projection.proof),
        )
        for table, families in (
            ("selective_read_records", projection.records),
            ("selective_read_buckets", projection.buckets),
        ):
            statement = sql.SQL("COPY {}.{} (space_id, revision_id, family, key, value) FROM STDIN")
            with (
                connection.cursor() as cursor,
                cursor.copy(
                    statement.format(sql.Identifier(SCHEMA), sql.Identifier(table))
                ) as copy,
            ):
                for family, rows in families.items():
                    for key, value in rows.items():
                        copy.write_row((*pin, family, key, jsonb(value)))
        return digest
