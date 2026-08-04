"""PostgreSQL atomic finalized-review publication unit of work."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from psycopg import Connection, sql
from pydantic import ValidationError

from ...contracts.contribution_review import ContributionReviewState
from ...contracts.graph import PublishRevisionCommand, StoredGraphRevision, WorldGraphRevision
from ...contracts.review_publication import (
    FinalizedReviewPublication,
    FinalizedReviewPublicationCommand,
)
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
from .records import _REVIEW_SELECT, _return_review_state
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
    try:
        publication = reconstruct(
            FinalizedReviewPublication,
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
        command.graph_schema,
    )
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
        raise PersistenceIntegrityError(
            "finalized publication revision does not match its command"
        )


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
        or publication.reviewed_contribution_sha256
        != record.reviewed_contribution_sha256
        or publication.review_intent_sha256 != record.review_intent_sha256
        or publication.confirmation_id != record.confirmation_id
        or publication.operation_id != record.operation_id
        or publication.expected_parent_revision_id
        != record.plan_ref.expected_parent_revision_id
        or publication.parent_graph_payload_sha256
        != record.plan_ref.base_graph_payload_sha256
        or publication.graph_schema != record.plan_ref.base_graph_schema
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
    ) -> None:
        self._database = database
        self._graph = PostgresWorldGraphRepository(database)
        self._failure_hook = failure_hook

    @staticmethod
    def _reload_command(
        command: FinalizedReviewPublicationCommand,
    ) -> FinalizedReviewPublicationCommand:
        try:
            return FinalizedReviewPublicationCommand.model_validate(
                command.model_dump(mode="json")
            )
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
            raise PersistenceIntegrityError(
                "finalized publication references a missing revision"
            )
        try:
            return _reconstruct_stored_revision(row)
        except PersistenceIntegrityError:
            raise PersistenceIntegrityError(
                "finalized publication references an invalid revision"
            ) from None

    @classmethod
    def _load_verified(
        cls,
        conn: Connection[Any],
        row: dict[str, Any],
    ) -> FinalizedReviewPublication:
        publication = _return_publication(row)
        try:
            state = cls._load_review(
                conn,
                world_id=publication.world_id,
                review_id=publication.review_id,
            )
        except ContributionReviewNotFoundError:
            raise PersistenceIntegrityError(
                "finalized publication references a missing review"
            ) from None
        _validate_record_review(publication, state)
        stored = cls._load_revision(
            conn,
            world_id=publication.world_id,
            revision_id=publication.published_revision_id,
        )
        parent = cls._load_revision(
            conn,
            world_id=publication.world_id,
            revision_id=publication.expected_parent_revision_id,
        )
        _validate_parent_revision(
            parent,
            world_id=publication.world_id,
            parent_revision_id=publication.expected_parent_revision_id,
            graph_schema=publication.graph_schema,
            graph_payload_sha256=publication.parent_graph_payload_sha256,
        )
        _validate_record_revision(publication, stored)
        return publication

    @classmethod
    def _validate_command_record(
        cls,
        command: FinalizedReviewPublicationCommand,
        publication: FinalizedReviewPublication,
    ) -> None:
        if (
            publication.world_id != command.world_id
            or publication.review_id != command.review_id
            or publication.reviewed_contribution_id != command.reviewed_contribution_id
            or publication.reviewed_contribution_sha256
            != command.reviewed_contribution_sha256
            or publication.review_intent_sha256 != command.review_intent_sha256
            or publication.confirmation_id != command.confirmation_id
            or publication.operation_id != command.operation_id
            or publication.expected_parent_revision_id
            != command.expected_parent_revision_id
            or publication.parent_graph_payload_sha256
            != command.parent_graph_payload_sha256
            or publication.published_revision_id
            != command.expected_published_revision_id
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
            raise PersistenceIntegrityError(
                "finalized publication missing after insert"
            )
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

    def publish(
        self,
        command: FinalizedReviewPublicationCommand,
    ) -> FinalizedReviewPublication:
        validated_command = self._reload_command(command)
        with self._database.transaction() as conn:
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

            existing_revision_row = _revision_row(
                conn,
                world_id=validated_command.world_id,
                revision_id=validated_command.expected_published_revision_id,
            )
            if existing_revision_row is not None:
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
            row = self._insert_publication(conn, publication)
            if self._failure_hook is not None:
                self._failure_hook()
            return self._load_verified(conn, row)
