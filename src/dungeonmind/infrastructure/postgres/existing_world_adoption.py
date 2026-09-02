"""PostgreSQL atomic existing-world adoption unit of work."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from psycopg import Connection, sql
from psycopg.errors import UniqueViolation

from ...application.existing_world_adoption import (
    bind_existing_world_adoption_command,
    terminal_existing_world_adoption_receipt,
)
from ...application.existing_world_adoption_repair import (
    LoadedAdoptedMembership,
    membership_from_loaded,
    prepare_source_classification_repair,
)
from ...application.repositories import (
    DurableExistingWorldAdoptionCommand,
    DurableExistingWorldAdoptionReceipt,
)
from ...contracts.evidence import SourceArtifactV2
from ...contracts.existing_world_adoption import (
    EXISTING_WORLD_ADOPTION_RECEIPT_SCHEMA,
    EXISTING_WORLD_ADOPTION_RECEIPT_V2_SCHEMA,
    EXISTING_WORLD_ADOPTION_RECEIPT_V3_SCHEMA,
    EXISTING_WORLD_ADOPTION_RECEIPT_V4_SCHEMA,
    ExistingWorldAdoptionReceiptV1,
    ExistingWorldAdoptionReceiptV2,
    ExistingWorldAdoptionReceiptV3,
    ExistingWorldAdoptionReceiptV4,
)
from ...contracts.existing_world_adoption_repair import (
    ExistingWorldAdoptionSourceClassificationRepairCommandV1,
)
from ...contracts.graph import PublishRevisionCommand
from ...domain.errors import IdempotencyConflictError, PersistenceIntegrityError
from .database import SCHEMA, PostgresDatabase, jsonb, lock_world
from .graph import (
    _REVISION_SELECT,
    PostgresWorldGraphRepository,
    _reconstruct_stored_revision,
)
from .records import (
    _ARTIFACT_SELECT as _SOURCE_ARTIFACT_SELECT,
)
from .records import (
    _CONTRIBUTION_SELECT,
    _IDENTITY_SELECT,
    _append_contribution_in_transaction,
    _append_identity_in_transaction,
    _put_artifact_in_transaction,
    _put_revision_in_transaction,
    _return_artifact,
    _return_contribution,
    _return_identity,
    _return_revision,
)
from .records import (
    _REVISION_SELECT as _SOURCE_REVISION_SELECT,
)
from .serialization import dump_payload, model_fingerprint, reconstruct

_ADOPTION_SELECT = """
    world_id,
    adoption_id,
    bundle_sha256,
    published_revision_id,
    graph_schema,
    graph_payload_sha256,
    adopted_at,
    source_artifact_count,
    source_revision_count,
    contribution_count,
    identity_decision_count,
    schema_version,
    record_fingerprint,
    payload
"""


def _adoption_identity(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "world_id": row["world_id"],
        "adoption_id": row["adoption_id"],
        "bundle_sha256": row["bundle_sha256"],
        "published_revision_id": row["published_revision_id"],
        "graph_schema": row["graph_schema"],
        "graph_payload_sha256": row["graph_payload_sha256"],
        "adopted_at": row["adopted_at"],
        "source_artifact_count": row["source_artifact_count"],
        "source_revision_count": row["source_revision_count"],
        "contribution_count": row["contribution_count"],
        "identity_decision_count": row["identity_decision_count"],
        "schema_version": row["schema_version"],
    }


def _adoption_row(
    conn: Connection[Any],
    *,
    world_id: str,
    adoption_id: str | None = None,
) -> dict[str, Any] | None:
    if adoption_id is None:
        return conn.execute(
            sql.SQL(
                f"""
                SELECT {_ADOPTION_SELECT}
                FROM {{}}.existing_world_adoptions
                WHERE world_id = %s
                """
            ).format(sql.Identifier(SCHEMA)),
            (world_id,),
        ).fetchone()
    return conn.execute(
        sql.SQL(
            f"""
            SELECT {_ADOPTION_SELECT}
            FROM {{}}.existing_world_adoptions
            WHERE world_id = %s AND adoption_id = %s
            """
        ).format(sql.Identifier(SCHEMA)),
        (world_id, adoption_id),
    ).fetchone()


def _adoption_row_for_id(conn: Connection[Any], adoption_id: str) -> dict[str, Any] | None:
    return conn.execute(
        sql.SQL(
            f"""
            SELECT {_ADOPTION_SELECT}
            FROM {{}}.existing_world_adoptions
            WHERE adoption_id = %s
            """
        ).format(sql.Identifier(SCHEMA)),
        (adoption_id,),
    ).fetchone()


def _exists(conn: Connection[Any], query: str, params: tuple[Any, ...]) -> bool:
    row = conn.execute(
        sql.SQL(query).format(sql.Identifier(SCHEMA)),
        params,
    ).fetchone()
    return row is not None


def _v2_adoption_facts(receipt: DurableExistingWorldAdoptionReceipt) -> dict[str, Any]:
    """The adoption facts shared by v2/v3 receipts (representation excluded)."""
    return receipt.model_dump(
        mode="json",
        exclude={
            "schema_version",
            "membership_sha256",
            "effective_membership_sha256",
            "membership_manifest",
            "source_classification_repair",
        },
    )


def _update_source_artifact_in_transaction(
    conn: Connection[Any],
    artifact: SourceArtifactV2,
) -> SourceArtifactV2:
    """Typed in-transaction SourceArtifactV2 update owned by the adoption UoW."""
    fingerprint = model_fingerprint(artifact)
    source_domain = (
        artifact.source_domain.value if artifact.source_domain is not None else None
    )
    visibility = artifact.visibility.value if artifact.visibility is not None else None
    conn.execute(
        sql.SQL(
            """
            UPDATE {}.source_artifacts
            SET campaign_id = %s,
                session_id = %s,
                source_domain = %s,
                status = %s,
                visibility = %s,
                current_revision_id = %s,
                created_at = %s,
                schema_version = %s,
                record_fingerprint = %s,
                payload = %s
            WHERE source_artifact_id = %s
            """
        ).format(sql.Identifier(SCHEMA)),
        (
            artifact.campaign_id,
            artifact.session_id,
            source_domain,
            artifact.status.value,
            visibility,
            artifact.current_revision_id,
            artifact.created_at,
            artifact.schema_version,
            fingerprint,
            jsonb(dump_payload(artifact)),
            artifact.source_artifact_id,
        ),
    )
    row = conn.execute(
        sql.SQL(
            f"""
            SELECT {_SOURCE_ARTIFACT_SELECT}
            FROM {{}}.source_artifacts
            WHERE source_artifact_id = %s
            """
        ).format(sql.Identifier(SCHEMA)),
        (artifact.source_artifact_id,),
    ).fetchone()
    if row is None:
        raise PersistenceIntegrityError(
            f"source artifact {artifact.source_artifact_id!r} missing after repair update"
        )
    restored = _return_artifact(row)
    if not isinstance(restored, SourceArtifactV2):
        raise PersistenceIntegrityError(
            "existing-world adoption repair restored a non-v2 source artifact"
        )
    if model_fingerprint(restored) != fingerprint:
        raise PersistenceIntegrityError(
            "existing-world adoption repair artifact fingerprint mismatch after update"
        )
    return restored


class PostgresExistingWorldAdoptionRepository:
    """Atomic PostgreSQL existing-world adoption unit of work."""

    def __init__(
        self,
        database: PostgresDatabase,
        *,
        failure_hook: Callable[[str], None] | None = None,
    ) -> None:
        self._database = database
        self._graph = PostgresWorldGraphRepository(database)
        self._failure_hook = failure_hook

    def _return_receipt(self, row: dict[str, Any]) -> DurableExistingWorldAdoptionReceipt:
        identity = _adoption_identity(row)
        schema_version = row["schema_version"]
        if schema_version == EXISTING_WORLD_ADOPTION_RECEIPT_SCHEMA:
            receipt_type: type[DurableExistingWorldAdoptionReceipt] = (
                ExistingWorldAdoptionReceiptV1
            )
        elif schema_version == EXISTING_WORLD_ADOPTION_RECEIPT_V2_SCHEMA:
            receipt_type = ExistingWorldAdoptionReceiptV2
        elif schema_version == EXISTING_WORLD_ADOPTION_RECEIPT_V4_SCHEMA:
            receipt_type = ExistingWorldAdoptionReceiptV4
        elif schema_version == EXISTING_WORLD_ADOPTION_RECEIPT_V3_SCHEMA:
            receipt_type = ExistingWorldAdoptionReceiptV3
        else:
            raise PersistenceIntegrityError(
                f"unsupported existing-world adoption receipt schema {schema_version!r}"
            )
        try:
            receipt = reconstruct(
                receipt_type,
                dict(row["payload"]),
                expected_fingerprint=row["record_fingerprint"],
                identity=identity,
            )
        except Exception:
            raise PersistenceIntegrityError(
                "existing-world adoption receipt failed reconstruction"
            ) from None
        return receipt.model_copy(deep=True)

    def _load_verified(
        self,
        conn: Connection[Any],
        row: dict[str, Any],
    ) -> DurableExistingWorldAdoptionReceipt:
        receipt = self._return_receipt(row)
        revision_row = conn.execute(
            sql.SQL(
                f"""
                SELECT {_REVISION_SELECT}
                FROM {{}}.graph_revisions
                WHERE world_id = %s AND revision_id = %s
                """
            ).format(sql.Identifier(SCHEMA)),
            (receipt.world_id, receipt.published_revision_id),
        ).fetchone()
        if revision_row is None:
            raise PersistenceIntegrityError(
                "existing-world adoption receipt references a missing revision"
            )
        stored = _reconstruct_stored_revision(revision_row)
        if (
            stored.revision.graph_payload_sha256 != receipt.graph_payload_sha256
            or stored.revision.graph_schema != receipt.graph_schema
            or stored.revision.world_id != receipt.world_id
        ):
            raise PersistenceIntegrityError(
                "existing-world adoption receipt disagrees with its published revision"
            )
        return receipt

    def _assert_pristine(self, conn: Connection[Any], world_id: str) -> None:
        checks = (
            (
                "SELECT 1 FROM {}.reviewed_world_initializations WHERE world_id = %s LIMIT 1",
                "reviewed_world_initialization",
            ),
            (
                "SELECT 1 FROM {}.world_graph_heads WHERE world_id = %s",
                "graph_head",
            ),
            (
                "SELECT 1 FROM {}.graph_revisions WHERE world_id = %s LIMIT 1",
                "graph_revision",
            ),
            (
                "SELECT 1 FROM {}.graph_contributions WHERE world_id = %s LIMIT 1",
                "contribution",
            ),
            (
                "SELECT 1 FROM {}.identity_decisions WHERE world_id = %s LIMIT 1",
                "identity_decision",
            ),
            (
                "SELECT 1 FROM {}.source_artifacts WHERE world_id = %s LIMIT 1",
                "source_artifact",
            ),
        )
        for query, family in checks:
            if _exists(conn, query, (world_id,)):
                raise PersistenceIntegrityError(
                    "existing-world adoption target is not pristine",
                    details={"reason": "non_pristine_target", "family": family},
                )

    def _insert_receipt(
        self,
        conn: Connection[Any],
        receipt: DurableExistingWorldAdoptionReceipt,
    ) -> dict[str, Any]:
        fingerprint = model_fingerprint(receipt)
        conn.execute(
            sql.SQL(
                """
                INSERT INTO {}.existing_world_adoptions (
                    world_id,
                    adoption_id,
                    bundle_sha256,
                    published_revision_id,
                    graph_schema,
                    graph_payload_sha256,
                    adopted_at,
                    source_artifact_count,
                    source_revision_count,
                    contribution_count,
                    identity_decision_count,
                    schema_version,
                    record_fingerprint,
                    payload
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """
            ).format(sql.Identifier(SCHEMA)),
            (
                receipt.world_id,
                receipt.adoption_id,
                receipt.bundle_sha256,
                receipt.published_revision_id,
                receipt.graph_schema,
                receipt.graph_payload_sha256,
                receipt.adopted_at,
                receipt.source_artifact_count,
                receipt.source_revision_count,
                receipt.contribution_count,
                receipt.identity_decision_count,
                receipt.schema_version,
                fingerprint,
                jsonb(dump_payload(receipt)),
            ),
        )
        row = _adoption_row(conn, world_id=receipt.world_id, adoption_id=receipt.adoption_id)
        if row is None:
            raise PersistenceIntegrityError("existing-world adoption receipt missing after insert")
        return row

    def get(self, world_id: str, adoption_id: str) -> DurableExistingWorldAdoptionReceipt | None:
        with self._database.transaction() as conn:
            row = _adoption_row(conn, world_id=world_id, adoption_id=adoption_id)
            return None if row is None else self._load_verified(conn, row)

    def get_for_world(self, world_id: str) -> DurableExistingWorldAdoptionReceipt | None:
        with self._database.transaction() as conn:
            row = _adoption_row(conn, world_id=world_id)
            return None if row is None else self._load_verified(conn, row)

    def list_world_ids(self) -> list[str]:
        with self._database.transaction() as conn:
            rows = conn.execute(
                sql.SQL(
                    """
                    SELECT world_id
                    FROM {}.existing_world_adoptions
                    ORDER BY world_id
                    """
                ).format(sql.Identifier(SCHEMA)),
            ).fetchall()
        return [str(row["world_id"]) for row in rows]

    def promote_to_v3_receipt(
        self,
        world_id: str,
        *,
        expected: ExistingWorldAdoptionReceiptV2,
        promoted: ExistingWorldAdoptionReceiptV3,
        current_membership_sha256: Callable[[], str],
    ) -> ExistingWorldAdoptionReceiptV3:
        """Atomically replace the stored v2 receipt with its v3 form.

        One transaction: lock the world row, then lock the four membership
        family tables ``SHARE ROW EXCLUSIVE`` — history writers (contribution
        append, source puts, identity append) commit through independent
        transactions that never take the world row lock, so the table locks
        are the genuine writer-excluding boundary for this rare
        steward-supervised operation. Inside that boundary: re-read and
        re-verify the current receipt, require fingerprint equality with
        ``expected`` and v2-fact preservation by ``promoted``, re-invoke
        ``current_membership_sha256()`` and require exact equality with the
        promoted checkpoint, then update only the receipt's versioned
        representation columns. An already-promoted receipt fingerprint-equal
        to ``promoted`` is an exact no-op; anything else fails with zero
        mutation. The in-boundary membership re-proof is the authoritative
        equality check: a writer cannot commit a membership change between it
        and the receipt swap.
        """
        with self._database.transaction() as conn:
            lock_world(conn, world_id, created_at=promoted.adopted_at)
            conn.execute(
                sql.SQL(
                    """
                    LOCK TABLE {}.source_artifacts,
                                {}.source_revisions,
                                {}.graph_contributions,
                                {}.identity_decisions
                    IN SHARE ROW EXCLUSIVE MODE
                    """
                ).format(
                    sql.Identifier(SCHEMA),
                    sql.Identifier(SCHEMA),
                    sql.Identifier(SCHEMA),
                    sql.Identifier(SCHEMA),
                )
            )
            row = _adoption_row(conn, world_id=world_id)
            if row is None:
                raise PersistenceIntegrityError(
                    "existing-world adoption receipt promotion found no receipt",
                    details={"reason": "adoption_receipt_missing", "world_id": world_id},
                )
            current = self._load_verified(conn, row)
            if isinstance(current, ExistingWorldAdoptionReceiptV4):
                raise PersistenceIntegrityError(
                    "existing-world adoption receipt promotion requires a v2 receipt",
                    details={
                        "reason": "adoption_receipt_promotion_unsupported_schema",
                        "world_id": world_id,
                        "receipt_schema": current.schema_version,
                    },
                )
            if isinstance(current, ExistingWorldAdoptionReceiptV3):
                if model_fingerprint(current) == model_fingerprint(promoted):
                    return current.model_copy(deep=True)
                raise PersistenceIntegrityError(
                    "existing-world adoption promotion conflicts with the stored v3 receipt",
                    details={
                        "reason": "adoption_receipt_promotion_identity_mismatch",
                        "world_id": world_id,
                    },
                )
            if not isinstance(current, ExistingWorldAdoptionReceiptV2):
                raise PersistenceIntegrityError(
                    "existing-world adoption receipt promotion requires a v2 receipt",
                    details={
                        "reason": "adoption_receipt_promotion_unsupported_schema",
                        "world_id": world_id,
                        "receipt_schema": current.schema_version,
                    },
                )
            if model_fingerprint(current) != model_fingerprint(expected):
                raise PersistenceIntegrityError(
                    "existing-world adoption receipt changed before promotion",
                    details={
                        "reason": "adoption_receipt_promotion_identity_mismatch",
                        "world_id": world_id,
                    },
                )
            if _v2_adoption_facts(current) != _v2_adoption_facts(promoted):
                raise PersistenceIntegrityError(
                    "existing-world adoption v3 receipt must preserve the v2 adoption facts",
                    details={
                        "reason": "adoption_receipt_promotion_fact_drift",
                        "world_id": world_id,
                    },
                )
            observed_membership_sha256 = current_membership_sha256()
            if observed_membership_sha256 != promoted.membership_sha256:
                raise PersistenceIntegrityError(
                    "existing-world adoption membership changed before promotion",
                    details={
                        "reason": "adoption_promotion_membership_mismatch",
                        "world_id": world_id,
                        "adoption_id": promoted.adoption_id,
                        "expected_membership_sha256": promoted.membership_sha256,
                        "current_membership_sha256": observed_membership_sha256,
                    },
                )
            conn.execute(
                sql.SQL(
                    """
                    UPDATE {}.existing_world_adoptions
                    SET schema_version = %s,
                        record_fingerprint = %s,
                        payload = %s
                    WHERE world_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (
                    promoted.schema_version,
                    model_fingerprint(promoted),
                    jsonb(dump_payload(promoted)),
                    world_id,
                ),
            )
            updated = _adoption_row(conn, world_id=world_id)
            if updated is None:
                raise PersistenceIntegrityError(
                    "existing-world adoption receipt missing after promotion"
                )
            restored = self._load_verified(conn, updated)
            if not isinstance(restored, ExistingWorldAdoptionReceiptV3):
                raise PersistenceIntegrityError(
                    "existing-world adoption receipt failed reconstruction"
                )
            return restored

    def _load_adopted_membership(
        self,
        conn: Connection[Any],
        command: ExistingWorldAdoptionSourceClassificationRepairCommandV1,
    ) -> LoadedAdoptedMembership:
        manifest = command.membership_manifest
        artifact_rows = conn.execute(
            sql.SQL(
                f"""
                SELECT {_SOURCE_ARTIFACT_SELECT}
                FROM {{}}.source_artifacts
                WHERE source_artifact_id = ANY(%s)
                """
            ).format(sql.Identifier(SCHEMA)),
            (list(manifest.source_artifact_ids),),
        ).fetchall()
        if len(artifact_rows) != len(manifest.source_artifact_ids):
            raise PersistenceIntegrityError(
                "existing-world adoption repair adopted artifact missing",
                details={"reason": "adoption_repair_artifact_missing"},
            )
        artifacts = {}
        for row in artifact_rows:
            artifact = _return_artifact(row)
            if artifact.world_id != command.world_id:
                raise PersistenceIntegrityError(
                    "existing-world adoption repair artifact world mismatch",
                    details={
                        "reason": "adoption_repair_artifact_world_mismatch",
                        "artifact_id": artifact.source_artifact_id,
                    },
                )
            artifacts[artifact.source_artifact_id] = artifact

        revision_rows = conn.execute(
            sql.SQL(
                f"""
                SELECT {_SOURCE_REVISION_SELECT}
                FROM {{}}.source_revisions
                WHERE source_revision_id = ANY(%s)
                """
            ).format(sql.Identifier(SCHEMA)),
            (list(manifest.source_revision_ids),),
        ).fetchall()
        if len(revision_rows) != len(manifest.source_revision_ids):
            raise PersistenceIntegrityError(
                "existing-world adoption repair adopted revision missing",
                details={"reason": "adoption_repair_revision_missing"},
            )
        revisions = {
            revision.source_revision_id: revision
            for revision in (_return_revision(row) for row in revision_rows)
        }

        contribution_rows = conn.execute(
            sql.SQL(
                f"""
                SELECT {_CONTRIBUTION_SELECT}
                FROM {{}}.graph_contributions
                WHERE world_id = %s AND contribution_id = ANY(%s)
                """
            ).format(sql.Identifier(SCHEMA)),
            (command.world_id, list(manifest.contribution_ids)),
        ).fetchall()
        if len(contribution_rows) != len(manifest.contribution_ids):
            raise PersistenceIntegrityError(
                "existing-world adoption repair adopted contribution missing",
                details={"reason": "adoption_repair_contribution_missing"},
            )
        contributions = {
            item.contribution_id: item
            for item in (_return_contribution(row) for row in contribution_rows)
        }

        identity_rows = conn.execute(
            sql.SQL(
                f"""
                SELECT {_IDENTITY_SELECT}
                FROM {{}}.identity_decisions
                WHERE world_id = %s AND decision_id = ANY(%s)
                """
            ).format(sql.Identifier(SCHEMA)),
            (command.world_id, list(manifest.identity_decision_ids)),
        ).fetchall()
        if len(identity_rows) != len(manifest.identity_decision_ids):
            raise PersistenceIntegrityError(
                "existing-world adoption repair adopted identity decision missing",
                details={"reason": "adoption_repair_identity_missing"},
            )
        identity_decisions = {
            item.decision_id: item
            for item in (_return_identity(row) for row in identity_rows)
        }
        return LoadedAdoptedMembership(
            artifacts=artifacts,
            revisions=revisions,
            contributions=contributions,
            identity_decisions=identity_decisions,
        )

    def repair_source_classification(
        self,
        command: ExistingWorldAdoptionSourceClassificationRepairCommandV1,
        *,
        dry_run: bool = False,
    ) -> ExistingWorldAdoptionReceiptV4:
        """Atomically repair adopted source classification, or prove it with no writes."""
        world_id = command.world_id
        with self._database.transaction() as conn:
            lock_world(conn, world_id, created_at=command.repaired_at)
            conn.execute(
                sql.SQL(
                    """
                    LOCK TABLE {}.source_artifacts,
                                {}.source_revisions,
                                {}.graph_contributions,
                                {}.identity_decisions
                    IN SHARE ROW EXCLUSIVE MODE
                    """
                ).format(
                    sql.Identifier(SCHEMA),
                    sql.Identifier(SCHEMA),
                    sql.Identifier(SCHEMA),
                    sql.Identifier(SCHEMA),
                )
            )
            row = _adoption_row(conn, world_id=world_id)
            if row is None:
                raise PersistenceIntegrityError(
                    "existing-world adoption repair found no receipt",
                    details={"reason": "adoption_receipt_missing", "world_id": world_id},
                )
            verified = self._load_verified(conn, row)
            loaded = self._load_adopted_membership(conn, command)
            revision_row = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_REVISION_SELECT}
                    FROM {{}}.graph_revisions
                    WHERE world_id = %s AND revision_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (verified.world_id, verified.published_revision_id),
            ).fetchone()
            if revision_row is None:
                raise PersistenceIntegrityError(
                    "existing-world adoption receipt references a missing revision"
                )
            stored_revision = _reconstruct_stored_revision(revision_row)
            prepared = prepare_source_classification_repair(
                command=command,
                stored=verified,
                loaded=loaded,
                published_graph_payload=stored_revision.graph_payload,
            )
            if isinstance(prepared, ExistingWorldAdoptionReceiptV4):
                return prepared.model_copy(deep=True)
            if dry_run:
                return prepared.v4_receipt.model_copy(deep=True)
            for target in prepared.artifacts_to_write:
                _update_source_artifact_in_transaction(conn, target)
            if self._failure_hook is not None:
                self._failure_hook("repaired_artifacts")
            observed_m1 = membership_from_loaded(
                self._load_adopted_membership(conn, command),
                command.membership_manifest,
            )
            if observed_m1 != command.effective_membership_sha256:
                raise PersistenceIntegrityError(
                    "existing-world adoption repair effective membership mismatch",
                    details={
                        "reason": "adoption_repair_effective_mismatch",
                        "world_id": world_id,
                        "expected_membership_sha256": (
                            command.effective_membership_sha256
                        ),
                        "observed_membership_sha256": observed_m1,
                    },
                )
            promoted = prepared.v4_receipt
            conn.execute(
                sql.SQL(
                    """
                    UPDATE {}.existing_world_adoptions
                    SET schema_version = %s,
                        record_fingerprint = %s,
                        payload = %s
                    WHERE world_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (
                    promoted.schema_version,
                    model_fingerprint(promoted),
                    jsonb(dump_payload(promoted)),
                    world_id,
                ),
            )
            if self._failure_hook is not None:
                self._failure_hook("receipt")
            updated = _adoption_row(conn, world_id=world_id)
            if updated is None:
                raise PersistenceIntegrityError(
                    "existing-world adoption receipt missing after repair"
                )
            restored = self._load_verified(conn, updated)
            if not isinstance(restored, ExistingWorldAdoptionReceiptV4):
                raise PersistenceIntegrityError(
                    "existing-world adoption receipt failed reconstruction"
                )
            return restored

    def adopt(
        self, command: DurableExistingWorldAdoptionCommand
    ) -> DurableExistingWorldAdoptionReceipt:
        validated = bind_existing_world_adoption_command(command)
        bundle = validated.bundle
        world_id = bundle.world_id
        with self._database.transaction() as conn:
            lock_world(conn, world_id, created_at=validated.requested_adopted_at)
            existing_row = _adoption_row(conn, world_id=world_id)
            if existing_row is not None:
                existing = self._load_verified(conn, existing_row)
                if existing.bundle_sha256 == validated.bundle_sha256:
                    return existing
                raise IdempotencyConflictError(
                    "existing-world adoption identity conflicts with the requested bundle"
                )
            other_row = _adoption_row_for_id(conn, bundle.adoption_id)
            if other_row is not None:
                raise IdempotencyConflictError(
                    f"adoption {bundle.adoption_id!r} already exists for another world"
                )
            self._assert_pristine(conn, world_id)
            for artifact in bundle.source_artifacts:
                _put_artifact_in_transaction(conn, artifact)
            for revision in bundle.source_revisions:
                _put_revision_in_transaction(conn, revision)
            if self._failure_hook is not None:
                self._failure_hook("source_records")
            for contribution in bundle.contributions:
                _append_contribution_in_transaction(conn, contribution)
            if self._failure_hook is not None:
                self._failure_hook("contributions")
            for decision in bundle.identity_decisions:
                _append_identity_in_transaction(conn, decision)
            if self._failure_hook is not None:
                self._failure_hook("identity_decisions")
                self._failure_hook("source_history")
            graph_command = PublishRevisionCommand(
                world_id=world_id,
                parent_revision_id=None,
                expected_parent_revision_id=None,
                operation_ids=[bundle.adoption_id],
                graph_schema=bundle.graph_schema,
                graph_payload=bundle.graph_payload,
                created_at=validated.requested_adopted_at,
            )
            revision = self._graph._publish_revision_in_transaction(
                conn,
                graph_command,
                world_locked=True,
            )
            if revision.revision_id != validated.expected_published_revision_id:
                raise PersistenceIntegrityError(
                    "published adoption revision id disagrees with the command"
                )
            if revision.graph_payload_sha256 != validated.graph_payload_sha256:
                raise PersistenceIntegrityError(
                    "published adoption payload digest disagrees with the command"
                )
            if self._failure_hook is not None:
                self._failure_hook("graph")
            receipt = terminal_existing_world_adoption_receipt(
                validated,
                published_revision_id=revision.revision_id,
            )
            try:
                row = self._insert_receipt(conn, receipt)
            except UniqueViolation:
                raise IdempotencyConflictError(
                    f"adoption {bundle.adoption_id!r} already exists for another world"
                ) from None
            if self._failure_hook is not None:
                self._failure_hook("receipt")
            return self._load_verified(conn, row)
