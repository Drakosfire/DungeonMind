"""Private derived-artifact storage; primary revision verification remains separate."""

from __future__ import annotations

import hashlib
from typing import Any

from psycopg import Connection, sql
from pydantic import ValidationError

from ...application.vnext._read_artifact import decode_read_artifact
from ...application.vnext._source_wire import _FORMAT, UnsupportedSourceWire, encode_source_wire
from ...application.vnext.errors import RevisionStructuralIntegrityError
from ...application.vnext.model import PARSED_REVISION_FORMAT_VERSION
from ...application.vnext.records import StoredKnowledgeRevision
from ...domain.canonical import canonical_sha256
from ...domain.errors import PersistenceIntegrityError
from .database import SCHEMA


def _generate(stored: StoredKnowledgeRevision) -> bytes | None:
    try:
        artifact = encode_source_wire(stored)
    except UnsupportedSourceWire:
        return None
    try:
        parsed = decode_read_artifact(artifact, stored)
    except RevisionStructuralIntegrityError:
        # Publication historically admits opaque native payloads. Cache eligibility
        # must not strengthen that authority's acceptance requirements.
        return None
    except PersistenceIntegrityError as exc:
        if isinstance(exc.__cause__, ValidationError):
            return None
        raise
    if parsed is None:
        raise PersistenceIntegrityError("generated artifact unexpectedly unsupported")
    return artifact


def _insert_artifact(
    conn: Connection[Any],
    stored: StoredKnowledgeRevision,
    *,
    replace: bool = False,
) -> bool:
    artifact = _generate(stored)
    if artifact is None:
        return False
    # Replacement is exclusive to explicit identity-only backfill, never a silent
    # conflict policy on new primary publication. Regenerate from the locked source.
    conflict = (
        """
        ON CONFLICT (space_id, revision_id, codec_version, parsed_format)
        DO UPDATE SET envelope_sha256 = EXCLUDED.envelope_sha256,
            graph_sha256 = EXCLUDED.graph_sha256,
            artifact_sha256 = EXCLUDED.artifact_sha256,
            artifact_length = EXCLUDED.artifact_length,
            artifact_bytes = EXCLUDED.artifact_bytes
    """
        if replace
        else ""
    )
    conn.execute(
        sql.SQL(
            """
            INSERT INTO {}.knowledge_native_read_artifacts (
                space_id, revision_id, codec_version, parsed_format, envelope_sha256,
                graph_sha256, artifact_sha256, artifact_length, artifact_bytes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
            + conflict
        ).format(sql.Identifier(SCHEMA)),
        (
            stored.revision.space_id,
            stored.revision.revision_id,
            _FORMAT,
            PARSED_REVISION_FORMAT_VERSION,
            canonical_sha256(stored.revision.model_dump(mode="json")),
            stored.graph_payload_sha256,
            hashlib.sha256(artifact).hexdigest(),
            len(artifact),
            artifact,
        ),
    )
    return True


def _read_artifact(conn: Connection[Any], stored: StoredKnowledgeRevision) -> bytes | None:
    maximum = 8 * len(stored._payload_json.encode("utf-8")) + 4096
    row = conn.execute(
        sql.SQL("""
            SELECT envelope_sha256, graph_sha256, artifact_sha256, artifact_length,
                octet_length(artifact_bytes) AS actual_length,
                CASE WHEN octet_length(artifact_bytes) <= %s THEN artifact_bytes
                     ELSE NULL END AS body
            FROM {}.knowledge_native_read_artifacts
            WHERE space_id = %s AND revision_id = %s AND codec_version = %s AND parsed_format = %s
        """).format(sql.Identifier(SCHEMA)),
        (
            maximum,
            stored.revision.space_id,
            stored.revision.revision_id,
            _FORMAT,
            PARSED_REVISION_FORMAT_VERSION,
        ),
    ).fetchone()
    if row is None:
        return None
    if row["actual_length"] > maximum or row["artifact_length"] != row["actual_length"]:
        raise PersistenceIntegrityError("native read artifact byte length mismatch")
    if row["envelope_sha256"] != canonical_sha256(stored.revision.model_dump(mode="json")):
        raise PersistenceIntegrityError("native read artifact source envelope mismatch")
    if row["graph_sha256"] != stored.graph_payload_sha256:
        raise PersistenceIntegrityError("native read artifact source graph mismatch")
    body = bytes(row["body"])
    if hashlib.sha256(body).hexdigest() != row["artifact_sha256"]:
        raise PersistenceIntegrityError("native read artifact byte checksum mismatch")
    return body
