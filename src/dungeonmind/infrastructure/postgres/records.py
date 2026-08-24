"""PostgreSQL record repositories — contributions, identity, sources, retrieval."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from psycopg import IsolationLevel, sql
from pydantic import ValidationError

from ...application.existing_world_adoption import require_v2_contribution_correction_closure
from ...application.repositories import DurableGraphContribution, DurableIdentityDecision
from ...application.source_provenance_snapshot import SourceProvenanceSnapshot
from ...contracts.contribution import (
    GRAPH_CONTRIBUTION_SCHEMA,
    GRAPH_CONTRIBUTION_V2_SCHEMA,
    ContributionStatus,
    GraphContribution,
    GraphContributionV2,
)
from ...contracts.contribution_review import (
    CONTRIBUTION_REVIEW_RECORD_SCHEMA,
    ContributionReviewRecord,
    ContributionReviewState,
)
from ...contracts.contribution_review_v2 import (
    CONTRIBUTION_REVIEW_RECORD_V2_SCHEMA,
    ContributionReviewRecordV2,
    ContributionReviewStateV2,
)
from ...contracts.evidence import (
    SOURCE_ARTIFACT_SCHEMA,
    SOURCE_ARTIFACT_V2_SCHEMA,
    SourceArtifact,
    SourceArtifactRecord,
    SourceArtifactV2,
    SourceRevision,
)
from ...contracts.identity import (
    IDENTITY_DECISION_SCHEMA,
    IDENTITY_DECISION_V2_SCHEMA,
    IdentityDecisionRecord,
    IdentityDecisionRecordV2,
)
from ...contracts.retrieval import GraphRetrievalSession
from ...domain.errors import (
    ContributionReviewAlreadyFinalizedError,
    DocumentNotFoundError,
    IdempotencyConflictError,
    InvalidLifecycleTransitionError,
    PersistenceIntegrityError,
)
from .database import (
    SCHEMA,
    PostgresDatabase,
    ensure_campaign,
    ensure_world,
    jsonb,
    lock_world,
)
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


def _return_contribution(row: dict[str, Any]) -> DurableGraphContribution:
    schema_version = row["schema_version"]
    if schema_version == GRAPH_CONTRIBUTION_SCHEMA:
        model_type: type[DurableGraphContribution] = GraphContribution
    elif schema_version == GRAPH_CONTRIBUTION_V2_SCHEMA:
        model_type = GraphContributionV2
    else:
        raise PersistenceIntegrityError(
            f"unsupported contribution schema {schema_version!r}"
        )
    return reconstruct(
        model_type,
        dict(row["payload"]),
        expected_fingerprint=row["record_fingerprint"],
        identity=_contribution_identity(row),
    ).model_copy(deep=True)


def _return_identity(row: dict[str, Any]) -> DurableIdentityDecision:
    schema_version = row["schema_version"]
    if schema_version == IDENTITY_DECISION_SCHEMA:
        model_type: type[DurableIdentityDecision] = IdentityDecisionRecord
    elif schema_version == IDENTITY_DECISION_V2_SCHEMA:
        model_type = IdentityDecisionRecordV2
    else:
        raise PersistenceIntegrityError(
            f"unsupported identity decision schema {schema_version!r}"
        )
    return reconstruct(
        model_type,
        dict(row["payload"]),
        expected_fingerprint=row["record_fingerprint"],
        identity=_identity_decision_identity(row),
    ).model_copy(deep=True)


def _return_artifact(row: dict[str, Any]) -> SourceArtifactRecord:
    schema_version = row["schema_version"]
    if schema_version == SOURCE_ARTIFACT_V2_SCHEMA:
        return reconstruct(
            SourceArtifactV2,
            dict(row["payload"]),
            expected_fingerprint=row["record_fingerprint"],
            identity=_source_artifact_identity(row),
        ).model_copy(deep=True)
    if schema_version != SOURCE_ARTIFACT_SCHEMA:
        raise PersistenceIntegrityError(f"unsupported source artifact schema {schema_version!r}")
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

_REVIEW_SELECT = """
    world_id, review_id, operation_id, source_plan_id,
    candidate_contribution_id, reviewed_contribution_id,
    expected_parent_revision_id, reviewer_id, reviewed_at, status,
    schema_version, record_fingerprint, payload
"""


def _append_contribution_in_transaction(
    conn: Any,
    contribution: DurableGraphContribution,
) -> DurableGraphContribution:
    """Insert/reconcile one contribution inside an existing transaction."""
    fingerprint = model_fingerprint(contribution)
    upsert_evidence_refs(conn, collect_evidence_from_contribution_payload(contribution))
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
            f"contribution {contribution.contribution_id!r} missing after insert/reconcile"
        )
    if row["record_fingerprint"] != fingerprint:
        raise IdempotencyConflictError(
            f"contribution {contribution.contribution_id!r} replayed with different payload"
        )
    try:
        return _return_contribution(row)
    except PersistenceIntegrityError:
        raise PersistenceIntegrityError(
            f"contribution {contribution.contribution_id!r} failed reconstruction"
        ) from None


def _load_contribution_in_transaction(
    conn: Any,
    *,
    world_id: str,
    contribution_id: str,
) -> DurableGraphContribution | None:
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


def _get_contribution_in_transaction(
    conn: Any,
    *,
    world_id: str,
    contribution_id: str,
) -> GraphContribution:
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
        raise PersistenceIntegrityError(f"review contribution child {contribution_id!r} is missing")
    try:
        loaded = _return_contribution(row)
    except PersistenceIntegrityError:
        raise PersistenceIntegrityError(
            f"review contribution child {contribution_id!r} failed reconstruction"
        ) from None
    if not isinstance(loaded, GraphContribution):
        raise PersistenceIntegrityError(
            f"review contribution child {contribution_id!r} is not dm_graph_contribution_v1"
        )
    return loaded


def _get_contribution_in_transaction_any_schema(
    conn: Any,
    *,
    world_id: str,
    contribution_id: str,
) -> DurableGraphContribution:
    """Load one review contribution child of either contribution generation."""
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
        raise PersistenceIntegrityError(f"review contribution child {contribution_id!r} is missing")
    try:
        return _return_contribution(row)
    except PersistenceIntegrityError:
        raise PersistenceIntegrityError(
            f"review contribution child {contribution_id!r} failed reconstruction"
        ) from None


def _return_review_record(
    row: dict[str, Any],
) -> ContributionReviewRecord | ContributionReviewRecordV2:
    schema_version = row["schema_version"]
    if schema_version == CONTRIBUTION_REVIEW_RECORD_SCHEMA:
        model_type: type[ContributionReviewRecord | ContributionReviewRecordV2] = (
            ContributionReviewRecord
        )
    elif schema_version == CONTRIBUTION_REVIEW_RECORD_V2_SCHEMA:
        model_type = ContributionReviewRecordV2
    else:
        raise PersistenceIntegrityError(
            f"unsupported contribution review schema {schema_version!r}"
        )
    record = reconstruct(
        model_type,
        dict(row["payload"]),
        expected_fingerprint=row["record_fingerprint"],
        identity={
            "world_id": row["world_id"],
            "review_id": row["review_id"],
            "operation_id": row["operation_id"],
            "status": row["status"],
            "schema_version": row["schema_version"],
        },
    )
    if (
        record.plan_ref.source_plan_id != row["source_plan_id"]
        or record.stored_candidate_contribution_id != row["candidate_contribution_id"]
        or record.reviewed_contribution_id != row["reviewed_contribution_id"]
        or record.plan_ref.expected_parent_revision_id != row["expected_parent_revision_id"]
        or record.reviewer_id != row["reviewer_id"]
        or record.reviewed_at != row["reviewed_at"]
    ):
        raise PersistenceIntegrityError(
            f"review {record.review_id!r} extracted identity columns drifted"
        )
    return record


def _return_review_state(
    conn: Any,
    row: dict[str, Any],
) -> ContributionReviewState | ContributionReviewStateV2:
    record = _return_review_record(row)
    if isinstance(record, ContributionReviewRecordV2):
        candidate = _get_contribution_in_transaction_any_schema(
            conn,
            world_id=record.world_id,
            contribution_id=record.stored_candidate_contribution_id,
        )
        reviewed = _get_contribution_in_transaction_any_schema(
            conn,
            world_id=record.world_id,
            contribution_id=record.reviewed_contribution_id,
        )
        if not isinstance(candidate, GraphContributionV2) or not isinstance(
            reviewed, GraphContributionV2
        ):
            raise PersistenceIntegrityError(
                f"review {record.review_id!r} received a non-v2 contribution"
            )
        try:
            return ContributionReviewStateV2(
                record=record,
                candidate_contribution=candidate,
                reviewed_contribution=reviewed,
            )
        except ValidationError:
            raise PersistenceIntegrityError(
                f"review {record.review_id!r} failed cross-record reconstruction"
            ) from None
    candidate = _get_contribution_in_transaction(
        conn,
        world_id=record.world_id,
        contribution_id=record.stored_candidate_contribution_id,
    )
    reviewed = _get_contribution_in_transaction(
        conn,
        world_id=record.world_id,
        contribution_id=record.reviewed_contribution_id,
    )
    try:
        return ContributionReviewState(
            record=record,
            candidate_contribution=candidate,
            reviewed_contribution=reviewed,
        )
    except ValidationError:
        raise PersistenceIntegrityError(
            f"review {record.review_id!r} failed cross-record reconstruction"
        ) from None


class PostgresContributionRepository:
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def append(self, contribution: DurableGraphContribution) -> DurableGraphContribution:
        with self._database.transaction() as conn:
            ensure_world(conn, contribution.world_id, created_at=contribution.produced_at)
            if isinstance(contribution, GraphContributionV2):
                world_id = contribution.world_id
                require_v2_contribution_correction_closure(
                    contribution,
                    resolve_target=lambda target_id: _load_contribution_in_transaction(
                        conn,
                        world_id=world_id,
                        contribution_id=target_id,
                    ),
                )
            return _append_contribution_in_transaction(conn, contribution)

    def get(self, world_id: str, contribution_id: str) -> DurableGraphContribution | None:
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
    ) -> list[DurableGraphContribution]:
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
    ) -> DurableGraphContribution:
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
            existing = _return_contribution(row)
            protected = conn.execute(
                sql.SQL(
                    """
                    SELECT 1
                    FROM {}.contribution_reviews
                    WHERE world_id = %s
                      AND (
                          candidate_contribution_id = %s
                          OR reviewed_contribution_id = %s
                      )
                    LIMIT 1
                    """
                ).format(sql.Identifier(SCHEMA)),
                (world_id, contribution_id, contribution_id),
            ).fetchone()
            if protected is not None:
                raise InvalidLifecycleTransitionError(
                    record_type="contribution",
                    record_id=contribution_id,
                    current_status=existing.status.value,
                    requested_status=status.value,
                    message=(
                        f"contribution {contribution_id!r} is lifecycle-protected "
                        "by a finalized review"
                    ),
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


class PostgresContributionReviewRepository:
    """Atomic PostgreSQL persistence for finalized review bundles."""

    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def _find_by_operation(self, conn: Any, world_id: str, operation_id: str) -> Any:
        return conn.execute(
            sql.SQL(
                f"""
                SELECT {_REVIEW_SELECT}
                FROM {{}}.contribution_reviews
                WHERE world_id = %s AND operation_id = %s
                """
            ).format(sql.Identifier(SCHEMA)),
            (world_id, operation_id),
        ).fetchone()

    def _find_by_plan(self, conn: Any, world_id: str, source_plan_id: str) -> Any:
        return conn.execute(
            sql.SQL(
                f"""
                SELECT {_REVIEW_SELECT}
                FROM {{}}.contribution_reviews
                WHERE world_id = %s AND source_plan_id = %s
                """
            ).format(sql.Identifier(SCHEMA)),
            (world_id, source_plan_id),
        ).fetchone()

    def finalize(
        self, state: ContributionReviewState | ContributionReviewStateV2
    ) -> ContributionReviewState | ContributionReviewStateV2:
        try:
            dumped = state.model_dump(mode="json")
            validated: ContributionReviewState | ContributionReviewStateV2 = (
                ContributionReviewStateV2.model_validate(dumped)
                if isinstance(state, ContributionReviewStateV2)
                else ContributionReviewState.model_validate(dumped)
            )
        except ValidationError:
            raise PersistenceIntegrityError(
                "review state failed validation before PostgreSQL persistence"
            ) from None
        record = validated.record
        fingerprint = model_fingerprint(record)
        with self._database.transaction() as conn:
            lock_world(conn, record.world_id, created_at=record.reviewed_at)
            if record.campaign_id is not None:
                ensure_campaign(
                    conn,
                    record.world_id,
                    record.campaign_id,
                    created_at=record.reviewed_at,
                )
            existing = self._find_by_operation(conn, record.world_id, record.operation_id)
            if existing is None:
                existing = self._find_by_plan(conn, record.world_id, record.plan_ref.source_plan_id)
            if existing is not None:
                existing_record = _return_review_record(existing)
                existing_state = _return_review_state(conn, existing)
                if existing_record.review_id == record.review_id and model_fingerprint(
                    existing_state
                ) == model_fingerprint(validated):
                    return existing_state
                if existing_record.operation_id == record.operation_id:
                    raise IdempotencyConflictError(
                        f"operation {record.operation_id!r} replayed with different payload"
                    )
                if existing_record.plan_ref.source_plan_id == record.plan_ref.source_plan_id:
                    raise ContributionReviewAlreadyFinalizedError(
                        f"source plan {record.plan_ref.source_plan_id!r} is already finalized"
                    )
                raise IdempotencyConflictError(
                    f"operation {record.operation_id!r} replayed with different payload"
                )

            candidate = _append_contribution_in_transaction(conn, validated.candidate_contribution)
            reviewed = _append_contribution_in_transaction(conn, validated.reviewed_contribution)
            if (
                candidate.contribution_id != record.stored_candidate_contribution_id
                or reviewed.contribution_id != record.reviewed_contribution_id
            ):
                raise PersistenceIntegrityError(
                    "review contribution IDs drifted during persistence"
                )
            conn.execute(
                sql.SQL(
                    """
                    INSERT INTO {}.contribution_reviews (
                        world_id,
                        review_id,
                        operation_id,
                        source_plan_id,
                        candidate_contribution_id,
                        reviewed_contribution_id,
                        expected_parent_revision_id,
                        reviewer_id,
                        reviewed_at,
                        status,
                        schema_version,
                        record_fingerprint,
                        payload
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (world_id, review_id) DO NOTHING
                    """
                ).format(sql.Identifier(SCHEMA)),
                (
                    record.world_id,
                    record.review_id,
                    record.operation_id,
                    record.plan_ref.source_plan_id,
                    record.stored_candidate_contribution_id,
                    record.reviewed_contribution_id,
                    record.plan_ref.expected_parent_revision_id,
                    record.reviewer_id,
                    record.reviewed_at,
                    record.status,
                    record.schema_version,
                    fingerprint,
                    jsonb(dump_payload(record)),
                ),
            )
            row = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_REVIEW_SELECT}
                    FROM {{}}.contribution_reviews
                    WHERE world_id = %s AND review_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (record.world_id, record.review_id),
            ).fetchone()
            if row is None:
                raise PersistenceIntegrityError(
                    f"review {record.review_id!r} missing after insert/reconcile"
                )
            if row["record_fingerprint"] != fingerprint:
                raise IdempotencyConflictError(
                    f"review {record.review_id!r} replayed with different payload"
                )
            return _return_review_state(conn, row)

    def get(
        self, world_id: str, review_id: str
    ) -> ContributionReviewState | ContributionReviewStateV2 | None:
        with self._database.transaction() as conn:
            row = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_REVIEW_SELECT}
                    FROM {{}}.contribution_reviews
                    WHERE world_id = %s AND review_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (world_id, review_id),
            ).fetchone()
            return None if row is None else _return_review_state(conn, row)

    def get_for_plan(
        self, world_id: str, source_plan_id: str
    ) -> ContributionReviewState | ContributionReviewStateV2 | None:
        with self._database.transaction() as conn:
            row = self._find_by_plan(conn, world_id, source_plan_id)
            return None if row is None else _return_review_state(conn, row)


def _append_identity_in_transaction(
    conn: Any,
    decision: DurableIdentityDecision,
) -> DurableIdentityDecision:
    """Insert/reconcile one identity decision inside an existing transaction."""
    fingerprint = model_fingerprint(decision)
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
            f"identity decision {decision.decision_id!r} missing after insert/reconcile"
        )
    if row["record_fingerprint"] != fingerprint:
        raise IdempotencyConflictError(
            f"identity decision {decision.decision_id!r} replayed with different payload"
        )
    return _return_identity(row)


class PostgresIdentityDecisionRepository:
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def append(self, decision: DurableIdentityDecision) -> DurableIdentityDecision:
        with self._database.transaction() as conn:
            return _append_identity_in_transaction(conn, decision)

    def get(self, world_id: str, decision_id: str) -> DurableIdentityDecision | None:
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

    def list_for_world(self, world_id: str) -> list[DurableIdentityDecision]:
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


def _put_artifact_in_transaction(
    conn: Any,
    artifact: SourceArtifactRecord,
) -> SourceArtifactRecord:
    """Insert/reconcile one source artifact inside an existing transaction."""
    fingerprint = model_fingerprint(artifact)
    if isinstance(artifact, SourceArtifactV2):
        source_domain = artifact.source_domain.value if artifact.source_domain is not None else None
        visibility = artifact.visibility.value if artifact.visibility is not None else None
        # Producer timestamps may be unknown. Persist NULL — never invent.
        created_at = artifact.created_at
        # World/campaign registry rows still require a substrate timestamp.
        # This is relational ensure metadata only; it is not written into
        # the artifact payload or the source_artifacts.created_at column
        # when the producer value is unknown.
        substrate_created_at = artifact.created_at or artifact.updated_at or datetime.now(UTC)
    else:
        source_domain = artifact.source_domain.value
        visibility = artifact.visibility.value
        created_at = artifact.created_at
        substrate_created_at = artifact.created_at
    ensure_world(conn, artifact.world_id, created_at=substrate_created_at)
    if artifact.campaign_id is not None:
        ensure_campaign(
            conn,
            artifact.world_id,
            artifact.campaign_id,
            created_at=substrate_created_at,
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
            source_domain,
            artifact.status.value,
            visibility,
            artifact.current_revision_id,
            created_at,
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
            f"source artifact {artifact.source_artifact_id!r} missing after insert/reconcile"
        )
    if row["record_fingerprint"] != fingerprint:
        raise IdempotencyConflictError(
            f"source artifact {artifact.source_artifact_id!r} replayed with "
            "different payload; mutable lifecycle needs a typed operation"
        )
    return _return_artifact(row)


def _put_revision_in_transaction(
    conn: Any,
    revision: SourceRevision,
) -> SourceRevision:
    """Insert/reconcile one source revision inside an existing transaction."""
    fingerprint = model_fingerprint(revision)
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
            f"source revision {revision.source_revision_id!r} missing after insert/reconcile"
        )
    if row["record_fingerprint"] != fingerprint:
        raise IdempotencyConflictError(
            f"source revision {revision.source_revision_id!r} replayed with different payload"
        )
    return _return_revision(row)


class PostgresSourceRepository:
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def put_artifact(self, artifact: SourceArtifactRecord) -> SourceArtifactRecord:
        with self._database.transaction() as conn:
            return _put_artifact_in_transaction(conn, artifact)

    def get_artifact(self, source_artifact_id: str) -> SourceArtifactRecord | None:
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

    def list_artifacts_for_world(self, world_id: str) -> list[SourceArtifactRecord]:
        with self._database.transaction() as conn:
            rows = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_ARTIFACT_SELECT}
                    FROM {{}}.source_artifacts
                    WHERE world_id = %s
                    ORDER BY source_artifact_id
                    """
                ).format(sql.Identifier(SCHEMA)),
                (world_id,),
            ).fetchall()
        return [_return_artifact(row) for row in rows]

    def put_revision(self, revision: SourceRevision) -> SourceRevision:
        with self._database.transaction() as conn:
            return _put_revision_in_transaction(conn, revision)

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

    def get_provenance_snapshot(
        self,
        *,
        artifact_ids: Sequence[str],
        revision_ids: Sequence[str],
    ) -> SourceProvenanceSnapshot:
        requested_artifacts = frozenset(artifact_ids)
        requested_revisions = frozenset(revision_ids)
        artifacts: dict[str, SourceArtifactRecord] = {}
        revisions: dict[str, SourceRevision] = {}
        with self._database.connect() as conn:
            conn.isolation_level = IsolationLevel.REPEATABLE_READ
            with conn.transaction():
                if requested_artifacts:
                    artifact_rows = conn.execute(
                        sql.SQL(
                            f"""
                            SELECT {_ARTIFACT_SELECT}
                            FROM {{}}.source_artifacts
                            WHERE source_artifact_id = ANY(%s)
                            """
                        ).format(sql.Identifier(SCHEMA)),
                        (list(requested_artifacts),),
                    ).fetchall()
                    artifacts = {
                        row["source_artifact_id"]: _return_artifact(row) for row in artifact_rows
                    }
                if requested_revisions:
                    revision_rows = conn.execute(
                        sql.SQL(
                            f"""
                            SELECT {_REVISION_SELECT}
                            FROM {{}}.source_revisions
                            WHERE source_revision_id = ANY(%s)
                            """
                        ).format(sql.Identifier(SCHEMA)),
                        (list(requested_revisions),),
                    ).fetchall()
                    revisions = {
                        row["source_revision_id"]: _return_revision(row) for row in revision_rows
                    }
        return SourceProvenanceSnapshot.from_loaded(
            requested_artifact_ids=requested_artifacts,
            requested_revision_ids=requested_revisions,
            artifacts=artifacts,
            revisions=revisions,
        )


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
                    f"retrieval session {session.session_id!r} missing after insert/reconcile"
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
                raise DocumentNotFoundError(f"retrieval session {session.session_id!r} not found")
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
