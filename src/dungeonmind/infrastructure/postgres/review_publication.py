"""PostgreSQL atomic finalized-review publication unit of work."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from typing import Any

from psycopg import Connection, sql
from pydantic import ValidationError

from ...application.graph_snapshot import GRAPH_SCHEMA_V6, GraphSnapshotReader
from ...application.publication_admission import (
    PublicationAdmissionRegistry,
    admission_source_refs,
    context_for,
    denied,
    require_command_policy,
    verified_profile,
    verify_receipt,
    verify_retained_revisions,
)
from ...application.repositories import VerifiedPublicationHistoryEntry
from ...application.review_materialization_v4 import (
    review_source_refs_v4,
    validate_reviewed_property_delta_v4,
)
from ...application.review_materialization_v6 import (
    introduced_evidence_v6,
    validate_materialized_source_domains_v6,
)
from ...application.source_provenance_snapshot import SourceProvenanceSnapshot
from ...contracts.contribution_review import ContributionReviewState
from ...contracts.contribution_review_v4 import ContributionReviewStateV4
from ...contracts.evidence import SourceRevision
from ...contracts.graph import PublishRevisionCommand, StoredGraphRevision, WorldGraphRevision
from ...contracts.publication_admission import (
    CONTEXT_BYTES,
    GRAPH_BYTES,
    PublicationAdmissionPolicyV1,
    bounded_canonical,
    bounded_sha256,
)
from ...contracts.review_publication import (
    FinalizedReviewPublication,
    FinalizedReviewPublicationCommand,
    FinalizedReviewPublicationCommandV3,
    FinalizedReviewPublicationV2,
    FinalizedReviewPublicationV3,
    decode_finalized_review_publication_command,
)
from ...contracts.semantic_profile import SemanticProfileRef
from ...domain.canonical import canonical_sha256
from ...domain.errors import (
    ContributionReviewNotFoundError,
    IdempotencyConflictError,
    PersistenceIntegrityError,
)
from .database import SCHEMA, PostgresDatabase, jsonb, lock_world
from .graph import (
    _REVISION_SELECT,
    PostgresWorldGraphRepository,
    _reconstruct_stored_revision,
)
from .publication_admission import PostgresPublicationAdmissionRepository, get_policy, lock_profile
from .records import (
    _ARTIFACT_SELECT,
    _IDENTITY_SELECT,
    _REVIEW_SELECT,
    PostgresSourceRepository,
    _return_artifact,
    _return_identity,
    _return_review_state,
    _return_revision,
)
from .records import (
    _REVISION_SELECT as _SOURCE_REVISION_SELECT,
)
from .serialization import dump_payload, model_fingerprint, reconstruct

_PUBLICATION_SELECT = """
    world_id,
    review_id,
    reviewed_contribution_id,
    reviewed_contribution_sha256,
    review_intent_sha256,
    confirmation_id,
    operation_id,
    expected_parent_revision_id,
    parent_graph_payload_sha256,
    published_revision_id,
    graph_schema,
    graph_payload_sha256,
    published_at,
    status,
    schema_version,
    record_fingerprint,
    payload
"""


def _publication_row(
    conn: Connection[Any],
    *,
    world_id: str,
    review_id: str | None = None,
    operation_id: str | None = None,
    published_revision_id: str | None = None,
) -> dict[str, Any] | None:
    return conn.execute(
        sql.SQL(
            f"""
            SELECT {_PUBLICATION_SELECT}
            FROM {{}}.finalized_review_publications
            WHERE world_id = %s
              AND (
                  review_id = %s
                  OR operation_id = %s
                  OR published_revision_id = %s
              )
            """
        ).format(sql.Identifier(SCHEMA)),
        (world_id, review_id, operation_id, published_revision_id),
    ).fetchone()


def _exact_publication_row(
    conn: Connection[Any],
    *,
    world_id: str,
    review_id: str,
) -> dict[str, Any] | None:
    return conn.execute(
        sql.SQL(
            f"""
            SELECT {_PUBLICATION_SELECT}
            FROM {{}}.finalized_review_publications
            WHERE world_id = %s AND review_id = %s
            """
        ).format(sql.Identifier(SCHEMA)),
        (world_id, review_id),
    ).fetchone()


def _review_row(
    conn: Connection[Any],
    *,
    world_id: str,
    review_id: str,
) -> dict[str, Any] | None:
    return conn.execute(
        sql.SQL(
            f"""
            SELECT {_REVIEW_SELECT}
            FROM {{}}.contribution_reviews
            WHERE world_id = %s AND review_id = %s
            """
        ).format(sql.Identifier(SCHEMA)),
        (world_id, review_id),
    ).fetchone()


def _revision_row(
    conn: Connection[Any],
    *,
    world_id: str,
    revision_id: str,
) -> dict[str, Any] | None:
    return conn.execute(
        sql.SQL(
            f"""
            SELECT {_REVISION_SELECT}
            FROM {{}}.graph_revisions
            WHERE world_id = %s AND revision_id = %s
            """
        ).format(sql.Identifier(SCHEMA)),
        (world_id, revision_id),
    ).fetchone()


def _return_publication(row: dict[str, Any]) -> FinalizedReviewPublication:
    identity = {
        key: row[key]
        for key in (
            "world_id",
            "review_id",
            "reviewed_contribution_id",
            "reviewed_contribution_sha256",
            "review_intent_sha256",
            "confirmation_id",
            "operation_id",
            "expected_parent_revision_id",
            "parent_graph_payload_sha256",
            "published_revision_id",
            "graph_schema",
            "graph_payload_sha256",
            "published_at",
            "status",
            "schema_version",
        )
    }
    if row["schema_version"] in {
        "dm_finalized_review_publication_v2",
        "dm_finalized_review_publication_v3",
    } and (row["payload"].get("schema_version") != row["schema_version"]):
        denied("admission_receipt_family_missing")
    try:
        publication = reconstruct(
            (
                FinalizedReviewPublicationV3
                if row["schema_version"] == "dm_finalized_review_publication_v3"
                else FinalizedReviewPublicationV2
                if row["schema_version"] == "dm_finalized_review_publication_v2"
                else FinalizedReviewPublication
            ),
            dict(row["payload"]),
            expected_fingerprint=row["record_fingerprint"],
            identity=identity,
        )
    except Exception:
        raise PersistenceIntegrityError(
            "finalized publication record failed reconstruction"
        ) from None
    return publication.model_copy(deep=True)


def _validate_review_binding(
    command: FinalizedReviewPublicationCommand,
    state: ContributionReviewState,
) -> None:
    from ...contracts.contribution_review_v5 import ContributionReviewStateV5
    from ...contracts.review_publication import FinalizedReviewPublicationCommandV3

    if isinstance(state, ContributionReviewStateV5) and not isinstance(
        command, FinalizedReviewPublicationCommandV3
    ):
        raise PersistenceIntegrityError("V5 reviews require explicit V7 publication")
    record = state.record
    expected = (
        record.world_id,
        record.review_id,
        record.reviewed_contribution_id,
        record.reviewed_contribution_sha256,
        record.review_intent_sha256,
        record.confirmation_id,
        record.operation_id,
        record.plan_ref.expected_parent_revision_id,
        record.plan_ref.base_graph_payload_sha256,
        record.plan_ref.base_graph_schema,
    )
    actual = (
        command.world_id,
        command.review_id,
        command.reviewed_contribution_id,
        command.reviewed_contribution_sha256,
        command.review_intent_sha256,
        command.confirmation_id,
        command.operation_id,
        command.expected_parent_revision_id,
        command.parent_graph_payload_sha256,
        command.parent_graph_schema
        if isinstance(command, FinalizedReviewPublicationCommandV3)
        else command.graph_schema,
    )
    from ...application.review_publication import validate_guarded_command_binding

    validate_guarded_command_binding(command, state.record)
    if actual != expected:
        raise IdempotencyConflictError(
            "finalized publication command disagrees with its durable review"
        )


def _validate_revision(
    stored: StoredGraphRevision,
    *,
    command: FinalizedReviewPublicationCommand,
) -> None:
    revision = stored.revision
    if (
        revision.world_id != command.world_id
        or revision.revision_id != command.expected_published_revision_id
        or revision.parent_revision_id != command.expected_parent_revision_id
        or revision.operation_ids != [command.operation_id]
        or revision.graph_schema != command.graph_schema
        or revision.status != "published"
        or canonical_sha256(stored.graph_payload) != command.graph_payload_sha256
        or revision.graph_payload_sha256 != command.graph_payload_sha256
        or stored.graph_payload != command.graph_payload
    ):
        raise PersistenceIntegrityError("finalized publication revision does not match its command")


def _validate_parent_revision(
    stored: StoredGraphRevision,
    *,
    world_id: str,
    parent_revision_id: str,
    graph_schema: str,
    graph_payload_sha256: str,
) -> None:
    revision = stored.revision
    if (
        revision.world_id != world_id
        or revision.revision_id != parent_revision_id
        or revision.graph_schema != graph_schema
        or revision.status != "published"
        or revision.graph_payload_sha256 != graph_payload_sha256
        or canonical_sha256(stored.graph_payload) != graph_payload_sha256
    ):
        raise PersistenceIntegrityError(
            "finalized publication parent revision does not match its binding"
        )


def _validate_record_review(
    publication: FinalizedReviewPublication,
    state: ContributionReviewState,
) -> None:
    record = state.record
    if (
        publication.world_id != record.world_id
        or publication.review_id != record.review_id
        or publication.reviewed_contribution_id != record.reviewed_contribution_id
        or publication.reviewed_contribution_sha256 != record.reviewed_contribution_sha256
        or publication.review_intent_sha256 != record.review_intent_sha256
        or publication.confirmation_id != record.confirmation_id
        or publication.operation_id != record.operation_id
        or publication.expected_parent_revision_id != record.plan_ref.expected_parent_revision_id
        or publication.parent_graph_payload_sha256 != record.plan_ref.base_graph_payload_sha256
        or (
            publication.parent_graph_schema
            if isinstance(publication, FinalizedReviewPublicationV3)
            else publication.graph_schema
        )
        != record.plan_ref.base_graph_schema
    ):
        raise PersistenceIntegrityError(
            "finalized publication record disagrees with its durable review"
        )


def _validate_record_revision(
    publication: FinalizedReviewPublication,
    stored: StoredGraphRevision,
) -> None:
    revision = stored.revision
    if (
        revision.world_id != publication.world_id
        or revision.revision_id != publication.published_revision_id
        or revision.parent_revision_id != publication.expected_parent_revision_id
        or revision.operation_ids != [publication.operation_id]
        or revision.graph_schema != publication.graph_schema
        or revision.graph_payload_sha256 != publication.graph_payload_sha256
        or revision.created_at != publication.published_at
        or revision.status != "published"
        or canonical_sha256(stored.graph_payload) != publication.graph_payload_sha256
    ):
        raise PersistenceIntegrityError(
            "finalized publication record disagrees with its immutable revision"
        )


def _record_from_revision(
    command: FinalizedReviewPublicationCommand,
    revision: WorldGraphRevision,
) -> FinalizedReviewPublication:
    return FinalizedReviewPublication(
        world_id=command.world_id,
        review_id=command.review_id,
        reviewed_contribution_id=command.reviewed_contribution_id,
        reviewed_contribution_sha256=command.reviewed_contribution_sha256,
        review_intent_sha256=command.review_intent_sha256,
        confirmation_id=command.confirmation_id,
        operation_id=command.operation_id,
        expected_parent_revision_id=command.expected_parent_revision_id,
        parent_graph_payload_sha256=command.parent_graph_payload_sha256,
        published_revision_id=command.expected_published_revision_id,
        graph_schema=command.graph_schema,
        graph_payload_sha256=command.graph_payload_sha256,
        published_at=revision.created_at,
    )


class PostgresFinalizedReviewPublicationRepository:
    """One PostgreSQL transaction for revision, head, and publication identity."""

    def __init__(
        self,
        database: PostgresDatabase,
        *,
        failure_hook: Callable[[], None] | None = None,
        admission_registry: PublicationAdmissionRegistry | None = None,
        v7_graph_reader: GraphSnapshotReader | None = None,
    ) -> None:
        self._database = database
        self._v7_graph_reader = v7_graph_reader
        self._graph = PostgresWorldGraphRepository(database)
        self._failure_hook = failure_hook
        self._admission_registry = admission_registry or PublicationAdmissionRegistry()
        self._admission = PostgresPublicationAdmissionRepository(database)

    def get_admission_policy(
        self, profile_ref: SemanticProfileRef | None
    ) -> PublicationAdmissionPolicyV1 | None:
        return self._admission.get(profile_ref)

    def get_provenance_snapshot(
        self,
        *,
        artifact_ids: Sequence[str],
        revision_ids: Sequence[str],
    ) -> SourceProvenanceSnapshot:
        return PostgresSourceRepository(self._database).get_provenance_snapshot(
            artifact_ids=artifact_ids,
            revision_ids=revision_ids,
        )

    @staticmethod
    def _locked_source_snapshot(
        conn: Connection[Any],
        *,
        artifact_ids: Sequence[str],
        revision_ids: Sequence[str],
        lock: bool = True,
    ) -> SourceProvenanceSnapshot:
        artifact_rows = conn.execute(
            sql.SQL(
                f"SELECT {_ARTIFACT_SELECT} FROM {{}}.source_artifacts "
                "WHERE source_artifact_id = ANY(%s) ORDER BY source_artifact_id"
                + (" FOR SHARE" if lock else "")
            ).format(sql.Identifier(SCHEMA)),
            (list(artifact_ids),),
        ).fetchall()
        revision_rows = conn.execute(
            sql.SQL(
                f"SELECT {_SOURCE_REVISION_SELECT} FROM {{}}.source_revisions "
                "WHERE source_revision_id = ANY(%s) ORDER BY source_revision_id"
                + (" FOR SHARE" if lock else "")
            ).format(sql.Identifier(SCHEMA)),
            (list(revision_ids),),
        ).fetchall()
        return SourceProvenanceSnapshot.from_loaded(
            requested_artifact_ids=frozenset(artifact_ids),
            requested_revision_ids=frozenset(revision_ids),
            artifacts={row["source_artifact_id"]: _return_artifact(row) for row in artifact_rows},
            revisions={row["source_revision_id"]: _return_revision(row) for row in revision_rows},
        )

    @staticmethod
    def _reload_command(
        command: FinalizedReviewPublicationCommand,
    ) -> FinalizedReviewPublicationCommand:
        try:
            return decode_finalized_review_publication_command(command.model_dump(mode="json"))
        except (AttributeError, TypeError, ValidationError, ValueError):
            raise PersistenceIntegrityError(
                "finalized publication command failed validation"
            ) from None

    @staticmethod
    def _load_review(
        conn: Connection[Any],
        *,
        world_id: str,
        review_id: str,
    ) -> ContributionReviewState:
        row = _review_row(conn, world_id=world_id, review_id=review_id)
        if row is None:
            raise ContributionReviewNotFoundError(
                "finalized contribution review was not found",
                details={"world_id": world_id, "review_id": review_id},
            )
        return _return_review_state(conn, row)

    @staticmethod
    def _load_revision(
        conn: Connection[Any],
        *,
        world_id: str,
        revision_id: str,
    ) -> StoredGraphRevision:
        row = _revision_row(conn, world_id=world_id, revision_id=revision_id)
        if row is None:
            raise PersistenceIntegrityError("finalized publication references a missing revision")
        try:
            return _reconstruct_stored_revision(row)
        except PersistenceIntegrityError:
            raise PersistenceIntegrityError(
                "finalized publication references an invalid revision"
            ) from None

    def _load_verified(
        self,
        conn: Connection[Any],
        row: dict[str, Any],
        *,
        revision_loader: Callable[[str], StoredGraphRevision] | None = None,
        review_loader: Callable[[str], ContributionReviewState] | None = None,
    ) -> FinalizedReviewPublication:
        publication = _return_publication(row)
        try:
            state = (
                review_loader(publication.review_id)
                if review_loader is not None
                else self._load_review(
                    conn, world_id=publication.world_id, review_id=publication.review_id
                )
            )
        except ContributionReviewNotFoundError:
            raise PersistenceIntegrityError(
                "finalized publication references a missing review"
            ) from None
        _validate_record_review(publication, state)
        stored = (
            revision_loader(publication.published_revision_id)
            if revision_loader is not None
            else self._load_revision(
                conn, world_id=publication.world_id, revision_id=publication.published_revision_id
            )
        )
        parent = (
            revision_loader(publication.expected_parent_revision_id)
            if revision_loader is not None
            else self._load_revision(
                conn,
                world_id=publication.world_id,
                revision_id=publication.expected_parent_revision_id,
            )
        )
        _validate_parent_revision(
            parent,
            world_id=publication.world_id,
            parent_revision_id=publication.expected_parent_revision_id,
            graph_schema=publication.parent_graph_schema
            if isinstance(publication, FinalizedReviewPublicationV3)
            else publication.graph_schema,
            graph_payload_sha256=publication.parent_graph_payload_sha256,
        )
        _validate_record_revision(publication, stored)
        profile = verified_profile(state, parent, stored.graph_payload)
        verify_receipt(publication, state, parent, stored, get_policy(conn, profile))

        def immutable_source_revision(revision_id: str) -> SourceRevision | None:
            row = conn.execute(
                sql.SQL(
                    f"SELECT {_SOURCE_REVISION_SELECT} FROM {{}}.source_revisions "
                    "WHERE source_revision_id=%s"
                ).format(sql.Identifier(SCHEMA)),
                (revision_id,),
            ).fetchone()
            return _return_revision(row) if row is not None else None

        if isinstance(publication, FinalizedReviewPublicationV3):
            from .review_publication_v7 import verify_history

            verify_history(self, conn, publication, state, parent, stored)
        else:
            verify_retained_revisions(publication, immutable_source_revision)
        return publication

    @classmethod
    def _validate_command_record(
        cls,
        command: FinalizedReviewPublicationCommand,
        publication: FinalizedReviewPublication,
    ) -> None:
        if isinstance(command, FinalizedReviewPublicationCommandV3) != isinstance(
            publication, FinalizedReviewPublicationV3
        ) or (
            isinstance(command, FinalizedReviewPublicationCommandV3)
            and isinstance(publication, FinalizedReviewPublicationV3)
            and command.parent_graph_schema != publication.parent_graph_schema
        ):
            raise IdempotencyConflictError("publication replay family or parent differs")
        if (
            getattr(command, "admission_policy_ref", None)
            != getattr(publication, "admission_policy_ref", None)
        ) or (
            getattr(command, "validator_ref", None) != getattr(publication, "validator_ref", None)
        ):
            raise IdempotencyConflictError("publication admission replay differs")
        if (
            publication.world_id != command.world_id
            or publication.review_id != command.review_id
            or publication.reviewed_contribution_id != command.reviewed_contribution_id
            or publication.reviewed_contribution_sha256 != command.reviewed_contribution_sha256
            or publication.review_intent_sha256 != command.review_intent_sha256
            or publication.confirmation_id != command.confirmation_id
            or publication.operation_id != command.operation_id
            or publication.expected_parent_revision_id != command.expected_parent_revision_id
            or publication.parent_graph_payload_sha256 != command.parent_graph_payload_sha256
            or publication.published_revision_id != command.expected_published_revision_id
            or publication.graph_schema != command.graph_schema
            or publication.graph_payload_sha256 != command.graph_payload_sha256
        ):
            raise IdempotencyConflictError(
                "finalized publication identity conflicts with the requested content"
            )

    @staticmethod
    def _insert_publication(
        conn: Connection[Any],
        publication: FinalizedReviewPublication,
    ) -> dict[str, Any]:
        fingerprint = model_fingerprint(publication)
        conn.execute(
            sql.SQL(
                """
                INSERT INTO {}.finalized_review_publications (
                    world_id,
                    review_id,
                    reviewed_contribution_id,
                    reviewed_contribution_sha256,
                    review_intent_sha256,
                    confirmation_id,
                    operation_id,
                    expected_parent_revision_id,
                    parent_graph_payload_sha256,
                    published_revision_id,
                    graph_schema,
                    graph_payload_sha256,
                    published_at,
                    status,
                    schema_version,
                    record_fingerprint,
                    payload
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                """
            ).format(sql.Identifier(SCHEMA)),
            (
                publication.world_id,
                publication.review_id,
                publication.reviewed_contribution_id,
                publication.reviewed_contribution_sha256,
                publication.review_intent_sha256,
                publication.confirmation_id,
                publication.operation_id,
                publication.expected_parent_revision_id,
                publication.parent_graph_payload_sha256,
                publication.published_revision_id,
                publication.graph_schema,
                publication.graph_payload_sha256,
                publication.published_at,
                publication.status,
                publication.schema_version,
                fingerprint,
                jsonb(dump_payload(publication)),
            ),
        )
        row = conn.execute(
            sql.SQL(
                f"""
                SELECT {_PUBLICATION_SELECT}
                FROM {{}}.finalized_review_publications
                WHERE world_id = %s AND review_id = %s
                """
            ).format(sql.Identifier(SCHEMA)),
            (publication.world_id, publication.review_id),
        ).fetchone()
        if row is None:
            raise PersistenceIntegrityError("finalized publication missing after insert")
        return row

    def get(
        self,
        world_id: str,
        operation_id: str,
    ) -> FinalizedReviewPublication | None:
        with self._database.transaction() as conn:
            row = _publication_row(
                conn,
                world_id=world_id,
                operation_id=operation_id,
            )
            return None if row is None else self._load_verified(conn, row)

    def get_for_review(
        self,
        world_id: str,
        review_id: str,
    ) -> FinalizedReviewPublication | None:
        with self._database.transaction() as conn:
            row = _exact_publication_row(
                conn,
                world_id=world_id,
                review_id=review_id,
            )
            return None if row is None else self._load_verified(conn, row)

    def read_verified_ancestry(
        self, world_id: str, revision_id: str
    ) -> tuple[VerifiedPublicationHistoryEntry, ...]:
        # Local maps belong to this one coherent read, never the repository.
        # Even internal validation joins reuse only records verified here.
        with self._database.transaction() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            revisions: dict[str, StoredGraphRevision] = {}
            reviews: dict[str, ContributionReviewState] = {}

            def revision(key: str) -> StoredGraphRevision:
                if key not in revisions:
                    revisions[key] = self._load_revision(conn, world_id=world_id, revision_id=key)
                return revisions[key]

            def review(key: str) -> ContributionReviewState:
                if key not in reviews:
                    reviews[key] = self._load_review(conn, world_id=world_id, review_id=key)
                return reviews[key]

            rows: list[VerifiedPublicationHistoryEntry] = []
            visited: set[str] = set()
            current: str | None = revision_id
            while current is not None:
                if current in visited:
                    raise PersistenceIntegrityError("graph revision ancestry contains a cycle")
                visited.add(current)
                stored = revision(current)
                row = _publication_row(conn, world_id=world_id, published_revision_id=current)
                publication = (
                    self._load_verified(conn, row, revision_loader=revision, review_loader=review)
                    if row is not None
                    else None
                )
                state = review(publication.review_id) if publication is not None else None
                rows.append(VerifiedPublicationHistoryEntry(stored.revision, publication, state))
                current = stored.revision.parent_revision_id
                # Only the next parent can be needed again in a linear scan.
                # Returned facts omit full historical graph bodies altogether.
                for key in tuple(revisions):
                    if key != current:
                        del revisions[key]
            return tuple(rows)

    def get_for_published_revision(
        self,
        world_id: str,
        revision_id: str,
    ) -> FinalizedReviewPublication | None:
        with self._database.transaction() as conn:
            row = conn.execute(
                sql.SQL(
                    f"SELECT {_PUBLICATION_SELECT} FROM {{}}.finalized_review_publications "
                    "WHERE world_id = %s AND published_revision_id = %s"
                ).format(sql.Identifier(SCHEMA)),
                (world_id, revision_id),
            ).fetchone()
            return None if row is None else self._load_verified(conn, row)

    def _validate_guard_in_transaction(
        self,
        conn: Connection[Any],
        command: FinalizedReviewPublicationCommand,
        parent: StoredGraphRevision,
    ) -> None:
        from ...application.review_publication import (
            validate_reviewed_identity_publication_preconditions,
        )
        from ...application.source_provenance_snapshot import SourceProvenanceSnapshot
        from ...contracts.review_publication import GuardedFinalizedReviewPublicationCommand

        if not isinstance(command, GuardedFinalizedReviewPublicationCommand):
            return
        guard = command.reviewed_identity_preconditions
        rows = conn.execute(
            sql.SQL(
                f"SELECT {_IDENTITY_SELECT} FROM {{}}.identity_decisions "
                "WHERE world_id = %s ORDER BY decision_id"
            ).format(sql.Identifier(SCHEMA)),
            (guard.world_id,),
        ).fetchall()
        decisions = [_return_identity(row) for row in rows]
        artifacts, revisions = {}, {}
        for artifact_id in sorted({s.source_artifact_id for s in guard.sources}):
            row = conn.execute(
                sql.SQL(
                    f"SELECT {_ARTIFACT_SELECT} FROM {{}}.source_artifacts "
                    "WHERE source_artifact_id = %s FOR SHARE"
                ).format(sql.Identifier(SCHEMA)),
                (artifact_id,),
            ).fetchone()
            if row is not None:
                artifacts[artifact_id] = _return_artifact(row)
        for revision_id in sorted({s.source_revision_id for s in guard.sources}):
            row = conn.execute(
                sql.SQL(
                    f"SELECT {_SOURCE_REVISION_SELECT} FROM {{}}.source_revisions "
                    "WHERE source_revision_id = %s"
                ).format(sql.Identifier(SCHEMA)),
                (revision_id,),
            ).fetchone()
            if row is not None:
                revisions[revision_id] = _return_revision(row)
        snapshot = SourceProvenanceSnapshot.from_loaded(
            requested_artifact_ids=frozenset(s.source_artifact_id for s in guard.sources),
            requested_revision_ids=frozenset(s.source_revision_id for s in guard.sources),
            artifacts=artifacts,
            revisions=revisions,
        )
        validate_reviewed_identity_publication_preconditions(
            guard, parent=parent, decisions=decisions, sources=snapshot
        )

    def publish(
        self,
        command: FinalizedReviewPublicationCommand,
    ) -> FinalizedReviewPublication:
        from ...contracts.review_publication import FinalizedReviewPublicationCommandV3

        if isinstance(command, FinalizedReviewPublicationCommandV3):
            from .review_publication_v7 import publish_v7

            return publish_v7(self, command)
        from ...application.review_materialization_v4 import capture_property_literals_v4

        raw_literals = capture_property_literals_v4(command.graph_payload)
        try:
            raw_graph_bytes = bounded_canonical(command.graph_payload, max_bytes=GRAPH_BYTES)
        except (ValueError, TypeError, RecursionError):
            raw_graph_bytes = None
        from ...contracts.review_publication import FinalizedReviewPublicationCommandV2

        if isinstance(command, FinalizedReviewPublicationCommandV2) and raw_graph_bytes is None:
            denied("admission_context_limit_exceeded")
        validated_command = self._reload_command(command)
        with self._database.transaction() as conn:
            # The profile fence may wait on a different World's first use.
            conn.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
            lock_world(
                conn,
                validated_command.world_id,
                created_at=validated_command.requested_published_at,
            )
            state = self._load_review(
                conn,
                world_id=validated_command.world_id,
                review_id=validated_command.review_id,
            )
            _validate_review_binding(validated_command, state)
            parent = self._load_revision(
                conn,
                world_id=validated_command.world_id,
                revision_id=validated_command.expected_parent_revision_id,
            )
            _validate_parent_revision(
                parent,
                world_id=validated_command.world_id,
                parent_revision_id=validated_command.expected_parent_revision_id,
                graph_schema=validated_command.graph_schema,
                graph_payload_sha256=validated_command.parent_graph_payload_sha256,
            )

            existing_row = _publication_row(
                conn,
                world_id=validated_command.world_id,
                review_id=validated_command.review_id,
                operation_id=validated_command.operation_id,
                published_revision_id=validated_command.expected_published_revision_id,
            )
            if existing_row is not None:
                existing = self._load_verified(conn, existing_row)
                self._validate_command_record(validated_command, existing)
                return existing

            profile = verified_profile(state, parent, validated_command.graph_payload)
            lock_profile(conn, profile)
            policy = get_policy(conn, profile)
            require_command_policy(validated_command, policy)
            if policy is not None:
                admission_source_refs(state)
            if policy is not None and (
                raw_graph_bytes is None
                or bounded_sha256(validated_command.graph_payload, max_bytes=GRAPH_BYTES)
                != hashlib.sha256(raw_graph_bytes).hexdigest()
            ):
                denied("admission_context_limit_exceeded")

            self._validate_guard_in_transaction(conn, validated_command, parent)

            if validated_command.graph_schema == GRAPH_SCHEMA_V6:
                new_evidence = introduced_evidence_v6(parent, validated_command.graph_payload)
                source_snapshot = self._locked_source_snapshot(
                    conn,
                    artifact_ids=tuple(sorted({r.source_artifact_id for r in new_evidence})),
                    revision_ids=tuple(
                        sorted({r.source_revision_id for r in new_evidence if r.source_revision_id})
                    ),
                )
                validate_materialized_source_domains_v6(
                    new_evidence,
                    world_id=validated_command.world_id,
                    sources=source_snapshot,
                )

            if isinstance(state, ContributionReviewStateV4):
                artifact_ids, revision_ids = review_source_refs_v4(state)
                property_sources = self._locked_source_snapshot(
                    conn, artifact_ids=artifact_ids, revision_ids=revision_ids
                )
                validate_reviewed_property_delta_v4(
                    state,
                    parent=parent,
                    graph_payload=validated_command.graph_payload,
                    source_snapshot=property_sources,
                    raw_literals=raw_literals,
                )

            admission_context = None
            if policy is not None:
                artifact_ids, revision_ids = admission_source_refs(state)
                sources = self._locked_source_snapshot(
                    conn, artifact_ids=artifact_ids, revision_ids=revision_ids
                )
                admission_context, parent_bytes, child_bytes = context_for(
                    state, parent, validated_command, policy, sources
                )
                self._admission_registry.validate(
                    policy,
                    bounded_canonical(
                        admission_context.model_dump(mode="json"), max_bytes=CONTEXT_BYTES
                    ),
                    parent_bytes,
                    child_bytes,
                )

            existing_revision_row = _revision_row(
                conn,
                world_id=validated_command.world_id,
                revision_id=validated_command.expected_published_revision_id,
            )
            if existing_revision_row is not None:
                if policy is not None:
                    denied("admission_raw_revision_adoption_forbidden")
                existing_revision = self._load_revision(
                    conn,
                    world_id=validated_command.world_id,
                    revision_id=validated_command.expected_published_revision_id,
                )
                _validate_revision(existing_revision, command=validated_command)
                publication = _record_from_revision(
                    validated_command,
                    existing_revision.revision,
                )
                row = self._insert_publication(conn, publication)
                return self._load_verified(conn, row)

            graph_command = PublishRevisionCommand(
                world_id=validated_command.world_id,
                parent_revision_id=validated_command.expected_parent_revision_id,
                expected_parent_revision_id=validated_command.expected_parent_revision_id,
                operation_ids=[validated_command.operation_id],
                graph_schema=validated_command.graph_schema,
                graph_payload=validated_command.graph_payload,
                created_at=validated_command.requested_published_at,
            )
            revision = self._graph._publish_revision_in_transaction(
                conn,
                graph_command,
                world_locked=True,
            )
            if self._failure_hook is not None:
                self._failure_hook()
            publication = _record_from_revision(validated_command, revision)
            if admission_context is not None:
                publication = FinalizedReviewPublicationV2(
                    **publication.model_dump(mode="python", exclude={"schema_version"}),
                    admission_policy_ref=policy.reference,
                    validator_ref=policy.validator_ref,
                    admission_context=admission_context,
                    admission_context_sha256=bounded_sha256(
                        admission_context.model_dump(mode="json"), max_bytes=CONTEXT_BYTES
                    ),
                )
            row = self._insert_publication(conn, publication)
            if self._failure_hook is not None:
                self._failure_hook()
            return self._load_verified(conn, row)
