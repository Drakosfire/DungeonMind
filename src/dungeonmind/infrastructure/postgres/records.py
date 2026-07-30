"""PostgreSQL record repositories — contributions, identity, sources, retrieval."""

from __future__ import annotations

from typing import Any

from psycopg import sql

from ...contracts.contribution import ContributionStatus, GraphContribution
from ...contracts.evidence import SourceArtifact, SourceRevision
from ...contracts.identity import IdentityDecisionRecord
from ...contracts.retrieval import GraphRetrievalSession
from ...domain.errors import DocumentNotFoundError, IdempotencyConflictError
from .database import SCHEMA, PostgresDatabase, ensure_campaign, ensure_world, jsonb
from .evidence_extract import collect_evidence_from_contribution_payload, upsert_evidence_refs
from .serialization import dump_payload, model_fingerprint, reconstruct


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
            existing = conn.execute(
                sql.SQL(
                    """
                    SELECT record_fingerprint, payload
                    FROM {}.graph_contributions
                    WHERE world_id = %s AND contribution_id = %s
                    FOR UPDATE
                    """
                ).format(sql.Identifier(SCHEMA)),
                (contribution.world_id, contribution.contribution_id),
            ).fetchone()
            if existing is not None:
                if existing["record_fingerprint"] != fingerprint:
                    raise IdempotencyConflictError(
                        f"contribution {contribution.contribution_id!r} replayed with "
                        "different payload"
                    )
                return _return_copy(
                    GraphContribution,
                    existing["payload"],
                    fingerprint,
                    {
                        "world_id": contribution.world_id,
                        "contribution_id": contribution.contribution_id,
                    },
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
        return contribution.model_copy(deep=True)

    def get(self, world_id: str, contribution_id: str) -> GraphContribution | None:
        with self._database.transaction() as conn:
            row = conn.execute(
                sql.SQL(
                    """
                    SELECT record_fingerprint, payload, world_id, contribution_id
                    FROM {}.graph_contributions
                    WHERE world_id = %s AND contribution_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (world_id, contribution_id),
            ).fetchone()
        if row is None:
            return None
        return _return_copy(
            GraphContribution,
            row["payload"],
            row["record_fingerprint"],
            {"world_id": row["world_id"], "contribution_id": row["contribution_id"]},
        )

    def list_for_world(
        self, world_id: str, *, status: ContributionStatus | None = None
    ) -> list[GraphContribution]:
        with self._database.transaction() as conn:
            if status is None:
                rows = conn.execute(
                    sql.SQL(
                        """
                        SELECT record_fingerprint, payload, world_id, contribution_id
                        FROM {}.graph_contributions
                        WHERE world_id = %s
                        ORDER BY contribution_id
                        """
                    ).format(sql.Identifier(SCHEMA)),
                    (world_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    sql.SQL(
                        """
                        SELECT record_fingerprint, payload, world_id, contribution_id
                        FROM {}.graph_contributions
                        WHERE world_id = %s AND status = %s
                        ORDER BY contribution_id
                        """
                    ).format(sql.Identifier(SCHEMA)),
                    (world_id, status.value),
                ).fetchall()
        return [
            _return_copy(
                GraphContribution,
                row["payload"],
                row["record_fingerprint"],
                {"world_id": row["world_id"], "contribution_id": row["contribution_id"]},
            )
            for row in rows
        ]

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
                    """
                    SELECT record_fingerprint, payload, world_id, contribution_id
                    FROM {}.graph_contributions
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
                identity={
                    "world_id": row["world_id"],
                    "contribution_id": row["contribution_id"],
                },
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
            existing = conn.execute(
                sql.SQL(
                    """
                    SELECT record_fingerprint, payload
                    FROM {}.identity_decisions
                    WHERE world_id = %s AND decision_id = %s
                    FOR UPDATE
                    """
                ).format(sql.Identifier(SCHEMA)),
                (decision.world_id, decision.decision_id),
            ).fetchone()
            if existing is not None:
                if existing["record_fingerprint"] != fingerprint:
                    raise IdempotencyConflictError(
                        f"identity decision {decision.decision_id!r} replayed with "
                        "different payload"
                    )
                return _return_copy(
                    IdentityDecisionRecord,
                    existing["payload"],
                    fingerprint,
                    {"world_id": decision.world_id, "decision_id": decision.decision_id},
                )
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
        return decision.model_copy(deep=True)

    def get(self, world_id: str, decision_id: str) -> IdentityDecisionRecord | None:
        with self._database.transaction() as conn:
            row = conn.execute(
                sql.SQL(
                    """
                    SELECT record_fingerprint, payload, world_id, decision_id
                    FROM {}.identity_decisions
                    WHERE world_id = %s AND decision_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (world_id, decision_id),
            ).fetchone()
        if row is None:
            return None
        return _return_copy(
            IdentityDecisionRecord,
            row["payload"],
            row["record_fingerprint"],
            {"world_id": row["world_id"], "decision_id": row["decision_id"]},
        )

    def list_for_world(self, world_id: str) -> list[IdentityDecisionRecord]:
        with self._database.transaction() as conn:
            rows = conn.execute(
                sql.SQL(
                    """
                    SELECT record_fingerprint, payload, world_id, decision_id
                    FROM {}.identity_decisions
                    WHERE world_id = %s
                    ORDER BY decision_id
                    """
                ).format(sql.Identifier(SCHEMA)),
                (world_id,),
            ).fetchall()
        return [
            _return_copy(
                IdentityDecisionRecord,
                row["payload"],
                row["record_fingerprint"],
                {"world_id": row["world_id"], "decision_id": row["decision_id"]},
            )
            for row in rows
        ]


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
            existing = conn.execute(
                sql.SQL(
                    """
                    SELECT record_fingerprint, payload
                    FROM {}.source_artifacts
                    WHERE source_artifact_id = %s
                    FOR UPDATE
                    """
                ).format(sql.Identifier(SCHEMA)),
                (artifact.source_artifact_id,),
            ).fetchone()
            if existing is not None:
                if existing["record_fingerprint"] != fingerprint:
                    raise IdempotencyConflictError(
                        f"source artifact {artifact.source_artifact_id!r} replayed with "
                        "different payload; mutable lifecycle needs a typed operation"
                    )
                return _return_copy(
                    SourceArtifact,
                    existing["payload"],
                    fingerprint,
                    {"source_artifact_id": artifact.source_artifact_id},
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
        return artifact.model_copy(deep=True)

    def get_artifact(self, source_artifact_id: str) -> SourceArtifact | None:
        with self._database.transaction() as conn:
            row = conn.execute(
                sql.SQL(
                    """
                    SELECT record_fingerprint, payload, source_artifact_id
                    FROM {}.source_artifacts
                    WHERE source_artifact_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (source_artifact_id,),
            ).fetchone()
        if row is None:
            return None
        return _return_copy(
            SourceArtifact,
            row["payload"],
            row["record_fingerprint"],
            {"source_artifact_id": row["source_artifact_id"]},
        )

    def put_revision(self, revision: SourceRevision) -> SourceRevision:
        fingerprint = model_fingerprint(revision)
        with self._database.transaction() as conn:
            existing = conn.execute(
                sql.SQL(
                    """
                    SELECT record_fingerprint, payload
                    FROM {}.source_revisions
                    WHERE source_revision_id = %s
                    FOR UPDATE
                    """
                ).format(sql.Identifier(SCHEMA)),
                (revision.source_revision_id,),
            ).fetchone()
            if existing is not None:
                if existing["record_fingerprint"] != fingerprint:
                    raise IdempotencyConflictError(
                        f"source revision {revision.source_revision_id!r} replayed with "
                        "different payload"
                    )
                return _return_copy(
                    SourceRevision,
                    existing["payload"],
                    fingerprint,
                    {"source_revision_id": revision.source_revision_id},
                )
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
        return revision.model_copy(deep=True)

    def get_revision(self, source_revision_id: str) -> SourceRevision | None:
        with self._database.transaction() as conn:
            row = conn.execute(
                sql.SQL(
                    """
                    SELECT record_fingerprint, payload, source_revision_id
                    FROM {}.source_revisions
                    WHERE source_revision_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (source_revision_id,),
            ).fetchone()
        if row is None:
            return None
        return _return_copy(
            SourceRevision,
            row["payload"],
            row["record_fingerprint"],
            {"source_revision_id": row["source_revision_id"]},
        )

    def list_revisions(self, source_artifact_id: str) -> list[SourceRevision]:
        with self._database.transaction() as conn:
            rows = conn.execute(
                sql.SQL(
                    """
                    SELECT record_fingerprint, payload, source_revision_id
                    FROM {}.source_revisions
                    WHERE source_artifact_id = %s
                    ORDER BY source_revision_id
                    """
                ).format(sql.Identifier(SCHEMA)),
                (source_artifact_id,),
            ).fetchall()
        return [
            _return_copy(
                SourceRevision,
                row["payload"],
                row["record_fingerprint"],
                {"source_revision_id": row["source_revision_id"]},
            )
            for row in rows
        ]


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
            existing = conn.execute(
                sql.SQL(
                    """
                    SELECT record_fingerprint, payload
                    FROM {}.retrieval_sessions
                    WHERE session_id = %s
                    FOR UPDATE
                    """
                ).format(sql.Identifier(SCHEMA)),
                (session.session_id,),
            ).fetchone()
            if existing is not None:
                if existing["record_fingerprint"] != fingerprint:
                    raise IdempotencyConflictError(
                        f"retrieval session {session.session_id!r} already exists"
                    )
                return _return_copy(
                    GraphRetrievalSession,
                    existing["payload"],
                    fingerprint,
                    {"session_id": session.session_id},
                )
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
        return session.model_copy(deep=True)

    def get(self, session_id: str) -> GraphRetrievalSession | None:
        with self._database.transaction() as conn:
            row = conn.execute(
                sql.SQL(
                    """
                    SELECT record_fingerprint, payload, session_id
                    FROM {}.retrieval_sessions
                    WHERE session_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return _return_copy(
            GraphRetrievalSession,
            row["payload"],
            row["record_fingerprint"],
            {"session_id": row["session_id"]},
        )

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
                        updated_at = %s,
                        record_fingerprint = %s,
                        payload = %s
                    WHERE session_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (
                    session.thread_id,
                    world_id,
                    revision_id,
                    session.updated_at,
                    fingerprint,
                    jsonb(dump_payload(session)),
                    session.session_id,
                ),
            )
        return session.model_copy(deep=True)


def _return_copy(
    model_type: type[Any],
    payload: dict[str, Any],
    expected_fingerprint: str,
    identity: dict[str, Any],
) -> Any:
    model = reconstruct(
        model_type,
        dict(payload),
        expected_fingerprint=expected_fingerprint,
        identity=identity,
    )
    return model.model_copy(deep=True)
