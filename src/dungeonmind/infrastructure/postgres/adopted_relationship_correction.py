"""One writer-fenced graph replacement and append-only terminal receipt."""

from __future__ import annotations

from typing import TYPE_CHECKING

from psycopg.errors import UniqueViolation
from pydantic import ValidationError

from ...application.adopted_relationship_correction import (
    make_correction_receipt,
    materialize_relationship_correction,
    validate_endpoint_identity,
    verify_correction_receipt,
)
from ...contracts.adopted_relationship_correction import (
    AdoptedRelationshipCorrectionCommandV1,
    AdoptedRelationshipCorrectionReceiptV1,
)
from ...contracts.existing_world_adoption import ExistingWorldAdoptionReceiptV4
from ...contracts.graph import PublishRevisionCommand, StoredGraphRevision
from ...contracts.semantic_profile import SemanticProfileRef
from ...domain.canonical import canonical_sha256
from ...domain.errors import IdempotencyConflictError, PersistenceIntegrityError
from .database import jsonb, lock_world
from .existing_world_adoption import _adoption_row
from .graph import _REVISION_SELECT, _reconstruct_stored_revision
from .records import (
    _ARTIFACT_SELECT,
    _IDENTITY_SELECT,
    _return_artifact,
    _return_identity,
    _return_revision,
)
from .records import (
    _REVISION_SELECT as SOURCE_REVISION_SELECT,
)

if TYPE_CHECKING:
    from .existing_world_adoption import PostgresExistingWorldAdoptionRepository


def correct_relationship(
    repo: PostgresExistingWorldAdoptionRepository, command: AdoptedRelationshipCorrectionCommandV1
) -> AdoptedRelationshipCorrectionReceiptV1:
    command = AdoptedRelationshipCorrectionCommandV1.model_validate(command.model_dump(mode="json"))
    world = command.world_id
    request_sha = canonical_sha256(command.model_dump(mode="json"))
    with repo._database.transaction() as conn:
        isolation = conn.execute("SHOW transaction_isolation").fetchone()["transaction_isolation"]
        if isolation not in {"read committed", "read uncommitted"}:
            raise PersistenceIntegrityError(
                "relationship correction requires fresh read-committed snapshots"
            )
        lock_world(conn, world, created_at=command.requested_at)
        prior = conn.execute(
            "SELECT * FROM dungeonmind.adopted_relationship_corrections WHERE operation_id=%s",
            (command.operation_id,),
        ).fetchone()
        if prior is not None and prior["request_sha256"] != request_sha:
            raise IdempotencyConflictError("relationship correction operation conflicts")
        adoption_row = _adoption_row(conn, world_id=world, adoption_id=command.adoption_id)
        if adoption_row is None:
            raise PersistenceIntegrityError("relationship correction adoption missing")
        adoption = repo._load_verified(conn, adoption_row)
        if not isinstance(adoption, ExistingWorldAdoptionReceiptV4):
            raise PersistenceIntegrityError(
                "relationship correction requires exact adoption membership"
            )

        def revision(identifier: str) -> StoredGraphRevision:
            row = conn.execute(
                f"SELECT {_REVISION_SELECT} FROM dungeonmind.graph_revisions "
                "WHERE world_id=%s AND revision_id=%s",
                (world, identifier),
            ).fetchone()
            if row is None:
                raise PersistenceIntegrityError("relationship correction graph history missing")
            return _reconstruct_stored_revision(row)

        adopted = revision(adoption.published_revision_id)
        parent = revision(command.expected_parent_revision_id)
        rules = repo._relationship_correction_rules.resolve(
            SemanticProfileRef.model_validate(parent.graph_payload["semantic_profile"])
        )
        history = [
            _return_identity(row).model_dump(mode="json")
            for row in conn.execute(
                f"SELECT {_IDENTITY_SELECT} FROM dungeonmind.identity_decisions "
                "WHERE world_id=%s ORDER BY decision_id",
                (world,),
            ).fetchall()
        ]
        for binding in (*command.old_evidence_bindings, *command.replacement_evidence_bindings):
            artifact_row = conn.execute(
                f"SELECT {_ARTIFACT_SELECT} FROM dungeonmind.source_artifacts "
                "WHERE source_artifact_id=%s",
                (binding.source_artifact_id,),
            ).fetchone()
            source_row = conn.execute(
                f"SELECT {SOURCE_REVISION_SELECT} FROM dungeonmind.source_revisions "
                "WHERE source_revision_id=%s",
                (binding.source_revision_id,),
            ).fetchone()
            if artifact_row is None or source_row is None:
                raise PersistenceIntegrityError("relationship correction source missing")
            artifact = _return_artifact(artifact_row)
            source_revision = _return_revision(source_row)
            if (
                artifact.world_id != world
                or str(artifact.status) != "active"
                or source_revision.source_artifact_id != binding.source_artifact_id
            ):
                raise PersistenceIntegrityError("relationship correction source lineage mismatch")
        refs = {r["evidence_ref_id"]: r for r in parent.graph_payload["evidence_refs"]}
        for binding in command.replacement_evidence_bindings:
            ref = refs.get(binding.evidence_ref_id)
            artifact_row = conn.execute(
                f"SELECT {_ARTIFACT_SELECT} FROM dungeonmind.source_artifacts "
                "WHERE source_artifact_id=%s",
                (binding.source_artifact_id,),
            ).fetchone()
            artifact = _return_artifact(artifact_row) if artifact_row is not None else None
            if (
                ref is None
                or artifact is None
                or ref.get("source_domain") != artifact.source_domain.value
                or ref.get("source_domain_key") != getattr(artifact, "source_domain_key", None)
            ):
                raise PersistenceIntegrityError(
                    "replacement evidence domain differs from authority"
                )
        if prior is not None:
            try:
                receipt = AdoptedRelationshipCorrectionReceiptV1.model_validate(prior["payload"])
            except (ValidationError, ValueError, TypeError):
                raise PersistenceIntegrityError(
                    "relationship correction receipt shape invalid"
                ) from None
            if (
                canonical_sha256(receipt.model_dump(mode="json")) != prior["record_fingerprint"]
                or receipt.command.world_id != prior["world_id"]
                or receipt.command.operation_id != prior["operation_id"]
                or receipt.command.adoption_id != prior["adoption_id"]
                or receipt.command.expected_parent_revision_id != prior["parent_revision_id"]
                or receipt.published_revision_id != prior["published_revision_id"]
                or receipt.request_sha256 != prior["request_sha256"]
            ):
                raise PersistenceIntegrityError("relationship correction receipt columns mismatch")
            return verify_correction_receipt(
                receipt,
                adoption=adoption,
                rules=rules,
                adopted=adopted,
                parent=parent,
                child=revision(receipt.published_revision_id),
                history=history,
            )
        validate_endpoint_identity(command, history)
        payload = materialize_relationship_correction(
            command,
            adoption_receipt=adoption,
            adopted_payload=adopted.graph_payload,
            parent_payload=parent.graph_payload,
            rules=rules,
        )
        child_revision = repo._graph._publish_revision_in_transaction(
            conn,
            PublishRevisionCommand(
                world_id=world,
                parent_revision_id=command.expected_parent_revision_id,
                expected_parent_revision_id=command.expected_parent_revision_id,
                operation_ids=[command.operation_id],
                graph_schema="dm_union_graph_v6",
                graph_payload=payload,
                created_at=command.requested_at,
            ),
            world_locked=True,
        )
        if repo._failure_hook:
            repo._failure_hook("correction_graph")
        child = revision(child_revision.revision_id)
        receipt = make_correction_receipt(command, adoption, rules, parent, child, history)
        try:
            conn.execute(
                """INSERT INTO dungeonmind.adopted_relationship_corrections
                (operation_id,world_id,adoption_id,parent_revision_id,published_revision_id,
                 request_sha256,record_fingerprint,payload) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    command.operation_id,
                    world,
                    command.adoption_id,
                    command.expected_parent_revision_id,
                    child_revision.revision_id,
                    request_sha,
                    canonical_sha256(receipt.model_dump(mode="json")),
                    jsonb(receipt.model_dump(mode="json")),
                ),
            )
        except UniqueViolation as exc:
            raise IdempotencyConflictError("relationship correction operation conflicts") from exc
        if repo._failure_hook:
            repo._failure_hook("correction_receipt")
        return receipt
