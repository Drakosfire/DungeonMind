"""PostgreSQL record repositories — contributions, identity, sources, retrieval."""

from __future__ import annotations

from typing import Any

from psycopg import sql

from ...contracts.contribution import ContributionStatus, GraphContribution
from ...contracts.evidence import SourceArtifact, SourceRevision
from ...contracts.identity import IdentityDecisionRecord
from ...contracts.retrieval import GraphRetrievalSession
from ...domain.errors import (
    DocumentNotFoundError,
    IdempotencyConflictError,
    PersistenceIntegrityError,
)
from .database import SCHEMA, PostgresDatabase, ensure_campaign, ensure_world, jsonb
from .evidence_extract import collect_evidence_from_contribution_payload, upsert_evidence_refs
from .serialization import dump_payload, model_fingerprint, reconstruct


def _contribution_identity(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "world_id": row["world_id"],
        "contribution_id": row["contribution_id"],
        "source_kind": row["source_kind"],
        "status": row["status"],
        "campaign_scope": row["campaign_scope"],
        "produced_at": row["produced_at"],
        "schema_version": row["schema_version"],
    }


def _identity_decision_identity(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "world_id": row["world_id"],
        "decision_id": row["decision_id"],
        "decision_kind": row["decision_kind"],
        "status": row["status"],
        "created_at": row["created_at"],
        "schema_version": row["schema_version"],
    }


def _source_artifact_identity(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_artifact_id": row["source_artifact_id"],
        "world_id": row["world_id"],
        "campaign_id": row["campaign_id"],
        "session_id": row["session_id"],
        "source_domain": row["source_domain"],
        "status": row["status"],
        "visibility": row["visibility"],
        "current_revision_id": row["current_revision_id"],
        "created_at": row["created_at"],
        "schema_version": row["schema_version"],
    }


def _source_revision_identity(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_revision_id": row["source_revision_id"],
        "source_artifact_id": row["source_artifact_id"],
        "content_sha256": row["content_sha256"],
        "body_storage": row["body_storage"],
        "locator": row["locator"],
        "created_at": row["created_at"],
        "schema_version": row["schema_version"],
    }


def _session_identity(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": row["session_id"],
        "thread_id": row["thread_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "schema_version": row["schema_version"],
    }


def _return_contribution(row: dict[str, Any]) -> GraphContribution:
    return reconstruct(
        GraphContribution,
        dict(row["payload"]),
        expected_fingerprint=row["record_fingerprint"],
        identity=_contribution_identity(row),
    ).model_copy(deep=True)


def _return_identity(row: dict[str, Any]) -> IdentityDecisionRecord:
    return reconstruct(
        IdentityDecisionRecord,
        dict(row["payload"]),
        expected_fingerprint=row["record_fingerprint"],
        identity=_identity_decision_identity(row),
    ).model_copy(deep=True)


def _return_artifact(row: dict[str, Any]) -> SourceArtifact:
    return reconstruct(
        SourceArtifact,
        dict(row["payload"]),
        expected_fingerprint=row["record_fingerprint"],
        identity=_source_artifact_identity(row),
    ).model_copy(deep=True)


def _return_revision(row: dict[str, Any]) -> SourceRevision:
    return reconstruct(
        SourceRevision,
        dict(row["payload"]),
        expected_fingerprint=row["record_fingerprint"],
        identity=_source_revision_identity(row),
    ).model_copy(deep=True)


def _return_session(row: dict[str, Any]) -> GraphRetrievalSession:
    model = reconstruct(
        GraphRetrievalSession,
        dict(row["payload"]),
        expected_fingerprint=row["record_fingerprint"],
        identity=_session_identity(row),
    )
    if model.snapshot.world_id != row["world_id"]:
        raise PersistenceIntegrityError(
            f"retrieval session {row['session_id']!r} world_id column drift"
        )
    if model.snapshot.revision_id != row["revision_id"]:
        raise PersistenceIntegrityError(
            f"retrieval session {row['session_id']!r} revision_id column drift"
        )
    return model.model_copy(deep=True)


_CONTRIBUTION_SELECT = """
    world_id, contribution_id, source_kind, status, campaign_scope,
    produced_at, schema_version, record_fingerprint, payload
"""
_IDENTITY_SELECT = """
    world_id, decision_id, decision_kind, status, created_at,
    schema_version, record_fingerprint, payload
"""
_ARTIFACT_SELECT = """
    source_artifact_id, world_id, campaign_id, session_id, source_domain,
    status, visibility, current_revision_id, created_at, schema_version,
    record_fingerprint, payload
"""
_REVISION_SELECT = """
    source_revision_id, source_artifact_id, content_sha256, body_storage,
    locator, created_at, schema_version, record_fingerprint, payload
"""
_SESSION_SELECT = """
    session_id, thread_id, world_id, revision_id, created_at, updated_at,
    schema_version, record_fingerprint, payload
"""


class PostgresContributionRepository:
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def append(self, contribution: GraphContribution) -> GraphContribution:
        fingerprint = model_fingerprint(contribution)
        with self._database.transaction() as conn:
            ensure_world(conn, contribution.world_id, created_at=contribution.produced_at)
            upsert_evidence_refs(
                conn, collect_evidence_from_contribution_payload(contribution)
            )
            conn.execute(
                sql.SQL(
                    """
                    INSERT INTO {}.graph_contributions (
                        world_id,
                        contribution_id,
                        source_kind,
                        status,
                        campaign_scope,
                        produced_at,
                        schema_version,
                        record_fingerprint,
                        payload
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (world_id, contribution_id) DO NOTHING
                    """
                ).format(sql.Identifier(SCHEMA)),
                (
                    contribution.world_id,
                    contribution.contribution_id,
                    contribution.source_kind.value,
                    contribution.status.value,
                    contribution.campaign_scope,
                    contribution.produced_at,
                    contribution.schema_version,
                    fingerprint,
                    jsonb(dump_payload(contribution)),
                ),
            )
            row = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_CONTRIBUTION_SELECT}
                    FROM {{}}.graph_contributions
                    WHERE world_id = %s AND contribution_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (contribution.world_id, contribution.contribution_id),
            ).fetchone()
            if row is None:
                raise PersistenceIntegrityError(
                    f"contribution {contribution.contribution_id!r} missing after "
                    "insert/reconcile"
                )
            if row["record_fingerprint"] != fingerprint:
                raise IdempotencyConflictError(
                    f"contribution {contribution.contribution_id!r} replayed with "
                    "different payload"
                )
            return _return_contribution(row)

    def get(self, world_id: str, contribution_id: str) -> GraphContribution | None:
        with self._database.transaction() as conn:
            row = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_CONTRIBUTION_SELECT}
                    FROM {{}}.graph_contributions
                    WHERE world_id = %s AND contribution_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (world_id, contribution_id),
            ).fetchone()
        if row is None:
            return None
        return _return_contribution(row)

    def list_for_world(
        self, world_id: str, *, status: ContributionStatus | None = None
    ) -> list[GraphContribution]:
        with self._database.transaction() as conn:
            if status is None:
                rows = conn.execute(
                    sql.SQL(
                        f"""
                        SELECT {_CONTRIBUTION_SELECT}
                        FROM {{}}.graph_contributions
                        WHERE world_id = %s
                        ORDER BY contribution_id
                        """
                    ).format(sql.Identifier(SCHEMA)),
                    (world_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    sql.SQL(
                        f"""
                        SELECT {_CONTRIBUTION_SELECT}
                        FROM {{}}.graph_contributions
                        WHERE world_id = %s AND status = %s
                        ORDER BY contribution_id
                        """
                    ).format(sql.Identifier(SCHEMA)),
                    (world_id, status.value),
                ).fetchall()
        return [_return_contribution(row) for row in rows]

    def update_status(
        self,
        world_id: str,
        contribution_id: str,
        status: ContributionStatus,
        *,
        superseded_by: str | None = None,
    ) -> GraphContribution:
        with self._database.transaction() as conn:
            row = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_CONTRIBUTION_SELECT}
                    FROM {{}}.graph_contributions
                    WHERE world_id = %s AND contribution_id = %s
                    FOR UPDATE
                    """
                ).format(sql.Identifier(SCHEMA)),
                (world_id, contribution_id),
            ).fetchone()
            if row is None:
                raise DocumentNotFoundError(
                    f"contribution {contribution_id!r} not found in world {world_id!r}"
                )
            existing = reconstruct(
                GraphContribution,
                dict(row["payload"]),
                expected_fingerprint=row["record_fingerprint"],
                identity=_contribution_identity(row),
            )
            updated = existing.model_copy(deep=True)
            updated.status = status
            if superseded_by is not None:
                updated.diagnostics = {**updated.diagnostics, "superseded_by": superseded_by}
            fingerprint = model_fingerprint(updated)
            conn.execute(
                sql.SQL(
                    """
                    UPDATE {}.graph_contributions
                    SET status = %s, record_fingerprint = %s, payload = %s
                    WHERE world_id = %s AND contribution_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (
                    status.value,
                    fingerprint,
                    jsonb(dump_payload(updated)),
                    world_id,
                    contribution_id,
                ),
            )
        return updated.model_copy(deep=True)


class PostgresIdentityDecisionRepository:
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def append(self, decision: IdentityDecisionRecord) -> IdentityDecisionRecord:
        fingerprint = model_fingerprint(decision)
        with self._database.transaction() as conn:
            ensure_world(conn, decision.world_id, created_at=decision.created_at)
            conn.execute(
                sql.SQL(
                    """
                    INSERT INTO {}.identity_decisions (
                        world_id,
                        decision_id,
                        decision_kind,
                        status,
                        created_at,
                        schema_version,
                        record_fingerprint,
                        payload
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (world_id, decision_id) DO NOTHING
                    """
                ).format(sql.Identifier(SCHEMA)),
                (
                    decision.world_id,
                    decision.decision_id,
                    decision.decision_kind.value,
                    decision.status.value,
                    decision.created_at,
                    decision.schema_version,
                    fingerprint,
                    jsonb(dump_payload(decision)),
                ),
            )
            row = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_IDENTITY_SELECT}
                    FROM {{}}.identity_decisions
                    WHERE world_id = %s AND decision_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (decision.world_id, decision.decision_id),
            ).fetchone()
            if row is None:
                raise PersistenceIntegrityError(
                    f"identity decision {decision.decision_id!r} missing after "
                    "insert/reconcile"
                )
            if row["record_fingerprint"] != fingerprint:
                raise IdempotencyConflictError(
                    f"identity decision {decision.decision_id!r} replayed with "
                    "different payload"
                )
            return _return_identity(row)

    def get(self, world_id: str, decision_id: str) -> IdentityDecisionRecord | None:
        with self._database.transaction() as conn:
            row = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_IDENTITY_SELECT}
                    FROM {{}}.identity_decisions
                    WHERE world_id = %s AND decision_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (world_id, decision_id),
            ).fetchone()
        if row is None:
            return None
        return _return_identity(row)

    def list_for_world(self, world_id: str) -> list[IdentityDecisionRecord]:
        with self._database.transaction() as conn:
            rows = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_IDENTITY_SELECT}
                    FROM {{}}.identity_decisions
                    WHERE world_id = %s
                    ORDER BY decision_id
                    """
                ).format(sql.Identifier(SCHEMA)),
                (world_id,),
            ).fetchall()
        return [_return_identity(row) for row in rows]


class PostgresSourceRepository:
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def put_artifact(self, artifact: SourceArtifact) -> SourceArtifact:
        fingerprint = model_fingerprint(artifact)
        with self._database.transaction() as conn:
            ensure_world(conn, artifact.world_id, created_at=artifact.created_at)
            if artifact.campaign_id is not None:
                ensure_campaign(
                    conn,
                    artifact.world_id,
                    artifact.campaign_id,
                    created_at=artifact.created_at,
                )
            conn.execute(
                sql.SQL(
                    """
                    INSERT INTO {}.source_artifacts (
                        source_artifact_id,
                        world_id,
                        campaign_id,
                        session_id,
                        source_domain,
                        status,
                        visibility,
                        current_revision_id,
                        created_at,
                        schema_version,
                        record_fingerprint,
                        payload
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_artifact_id) DO NOTHING
                    """
                ).format(sql.Identifier(SCHEMA)),
                (
                    artifact.source_artifact_id,
                    artifact.world_id,
                    artifact.campaign_id,
                    artifact.session_id,
                    artifact.source_domain.value,
                    artifact.status.value,
                    artifact.visibility.value,
                    artifact.current_revision_id,
                    artifact.created_at,
                    artifact.schema_version,
                    fingerprint,
                    jsonb(dump_payload(artifact)),
                ),
            )
            row = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_ARTIFACT_SELECT}
                    FROM {{}}.source_artifacts
                    WHERE source_artifact_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (artifact.source_artifact_id,),
            ).fetchone()
            if row is None:
                raise PersistenceIntegrityError(
                    f"source artifact {artifact.source_artifact_id!r} missing after "
                    "insert/reconcile"
                )
            if row["record_fingerprint"] != fingerprint:
                raise IdempotencyConflictError(
                    f"source artifact {artifact.source_artifact_id!r} replayed with "
                    "different payload; mutable lifecycle needs a typed operation"
                )
            return _return_artifact(row)

    def get_artifact(self, source_artifact_id: str) -> SourceArtifact | None:
        with self._database.transaction() as conn:
            row = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_ARTIFACT_SELECT}
                    FROM {{}}.source_artifacts
                    WHERE source_artifact_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (source_artifact_id,),
            ).fetchone()
        if row is None:
            return None
        return _return_artifact(row)

    def put_revision(self, revision: SourceRevision) -> SourceRevision:
        fingerprint = model_fingerprint(revision)
        with self._database.transaction() as conn:
            conn.execute(
                sql.SQL(
                    """
                    INSERT INTO {}.source_revisions (
                        source_revision_id,
                        source_artifact_id,
                        content_sha256,
                        body_storage,
                        locator,
                        created_at,
                        schema_version,
                        record_fingerprint,
                        payload
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_revision_id) DO NOTHING
                    """
                ).format(sql.Identifier(SCHEMA)),
                (
                    revision.source_revision_id,
                    revision.source_artifact_id,
                    revision.content_sha256,
                    revision.body_storage,
                    revision.locator,
                    revision.created_at,
                    revision.schema_version,
                    fingerprint,
                    jsonb(dump_payload(revision)),
                ),
            )
            row = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_REVISION_SELECT}
                    FROM {{}}.source_revisions
                    WHERE source_revision_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (revision.source_revision_id,),
            ).fetchone()
            if row is None:
                raise PersistenceIntegrityError(
                    f"source revision {revision.source_revision_id!r} missing after "
                    "insert/reconcile"
                )
            if row["record_fingerprint"] != fingerprint:
                raise IdempotencyConflictError(
                    f"source revision {revision.source_revision_id!r} replayed with "
                    "different payload"
                )
            return _return_revision(row)

    def get_revision(self, source_revision_id: str) -> SourceRevision | None:
        with self._database.transaction() as conn:
            row = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_REVISION_SELECT}
                    FROM {{}}.source_revisions
                    WHERE source_revision_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (source_revision_id,),
            ).fetchone()
        if row is None:
            return None
        return _return_revision(row)

    def list_revisions(self, source_artifact_id: str) -> list[SourceRevision]:
        with self._database.transaction() as conn:
            rows = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_REVISION_SELECT}
                    FROM {{}}.source_revisions
                    WHERE source_artifact_id = %s
                    ORDER BY source_revision_id
                    """
                ).format(sql.Identifier(SCHEMA)),
                (source_artifact_id,),
            ).fetchall()
        return [_return_revision(row) for row in rows]


class PostgresRetrievalSessionRepository:
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def create(self, session: GraphRetrievalSession) -> GraphRetrievalSession:
        fingerprint = model_fingerprint(session)
        world_id = session.snapshot.world_id
        revision_id = session.snapshot.revision_id
        with self._database.transaction() as conn:
            ensure_world(conn, world_id, created_at=session.created_at)
            upsert_evidence_refs(conn, session.evidence)
            conn.execute(
                sql.SQL(
                    """
                    INSERT INTO {}.retrieval_sessions (
                        session_id,
                        thread_id,
                        world_id,
                        revision_id,
                        created_at,
                        updated_at,
                        schema_version,
                        record_fingerprint,
                        payload
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (session_id) DO NOTHING
                    """
                ).format(sql.Identifier(SCHEMA)),
                (
                    session.session_id,
                    session.thread_id,
                    world_id,
                    revision_id,
                    session.created_at,
                    session.updated_at,
                    session.schema_version,
                    fingerprint,
                    jsonb(dump_payload(session)),
                ),
            )
            row = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_SESSION_SELECT}
                    FROM {{}}.retrieval_sessions
                    WHERE session_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (session.session_id,),
            ).fetchone()
            if row is None:
                raise PersistenceIntegrityError(
                    f"retrieval session {session.session_id!r} missing after "
                    "insert/reconcile"
                )
            if row["record_fingerprint"] != fingerprint:
                raise IdempotencyConflictError(
                    f"retrieval session {session.session_id!r} already exists"
                )
            return _return_session(row)

    def get(self, session_id: str) -> GraphRetrievalSession | None:
        with self._database.transaction() as conn:
            row = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_SESSION_SELECT}
                    FROM {{}}.retrieval_sessions
                    WHERE session_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return _return_session(row)

    def save(self, session: GraphRetrievalSession) -> GraphRetrievalSession:
        fingerprint = model_fingerprint(session)
        world_id = session.snapshot.world_id
        revision_id = session.snapshot.revision_id
        with self._database.transaction() as conn:
            existing = conn.execute(
                sql.SQL(
                    """
                    SELECT session_id
                    FROM {}.retrieval_sessions
                    WHERE session_id = %s
                    FOR UPDATE
                    """
                ).format(sql.Identifier(SCHEMA)),
                (session.session_id,),
            ).fetchone()
            if existing is None:
                raise DocumentNotFoundError(
                    f"retrieval session {session.session_id!r} not found"
                )
            upsert_evidence_refs(conn, session.evidence)
            conn.execute(
                sql.SQL(
                    """
                    UPDATE {}.retrieval_sessions
                    SET
                        thread_id = %s,
                        world_id = %s,
                        revision_id = %s,
                        created_at = %s,
                        updated_at = %s,
                        schema_version = %s,
                        record_fingerprint = %s,
                        payload = %s
                    WHERE session_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (
                    session.thread_id,
                    world_id,
                    revision_id,
                    session.created_at,
                    session.updated_at,
                    session.schema_version,
                    fingerprint,
                    jsonb(dump_payload(session)),
                    session.session_id,
                ),
            )
        return session.model_copy(deep=True)
