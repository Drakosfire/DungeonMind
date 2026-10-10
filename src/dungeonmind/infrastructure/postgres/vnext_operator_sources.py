"""PostgreSQL prepared operator source-span attestation authority."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any

from psycopg import Connection, sql

from dungeonmind.application.vnext.operator_approval import (
    OperatorApprovalVerifier,
    TrustedOperatorApproval,
)
from dungeonmind.application.vnext.operator_source_binding import (
    validate_operator_source_selection,
)
from dungeonmind.application.vnext.ports import NativeTextSourceView, StoredNativeTextSource
from dungeonmind.application.vnext.provenance import (
    KnowledgeProvenanceSnapshot,
    _build_snapshot_from_loaded,
)
from dungeonmind.contracts.evidence import SourceStatus
from dungeonmind.contracts.vnext.domain import DomainContractDescriptor
from dungeonmind.contracts.vnext.native_source import (
    NATIVE_TEXT_BODY_STORAGE,
    NativeUtf8SpanProofV1,
)
from dungeonmind.contracts.vnext.operator_source import (
    OperatorSourceAttestationReceiptV1,
    OperatorSourceCommandV1,
    OperatorSourceSelectionV1,
    PreparedOperatorSourceV1,
)
from dungeonmind.contracts.vnext.source import SourceArtifactV3, SourceRevisionV2
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError

from .database import SCHEMA, PostgresDatabase, jsonb
from .records import (
    _ARTIFACT_SELECT,
    _REVISION_SELECT,
    _return_artifact,
    _return_revision,
)
from .vnext_knowledge import _lock_space, _read_head, _read_revision
from .vnext_sources import PostgresNativeSourceEvidenceRepository, _lock_native_epoch


def _legacy_pair(
    conn: Connection[Any], artifact_id: str, revision_id: str,
) -> tuple[Any, Any]:
    artifact_row = conn.execute(
        sql.SQL(f"SELECT {_ARTIFACT_SELECT} FROM {{}}.source_artifacts "
                "WHERE source_artifact_id = %s FOR SHARE").format(sql.Identifier(SCHEMA)),
        (artifact_id,),
    ).fetchone()
    revision_row = conn.execute(
        sql.SQL(f"SELECT {_REVISION_SELECT} FROM {{}}.source_revisions "
                "WHERE source_revision_id = %s FOR SHARE").format(sql.Identifier(SCHEMA)),
        (revision_id,),
    ).fetchone()
    return (
        None if artifact_row is None else _return_artifact(artifact_row),
        None if revision_row is None else _return_revision(revision_row),
    )


def _current_epoch(conn: Connection[Any]) -> int:
    row = conn.execute(
        sql.SQL("SELECT epoch FROM {}.knowledge_native_source_authority "
                "WHERE singleton_id = 1").format(sql.Identifier(SCHEMA))
    ).fetchone()
    if row is None:
        raise PersistenceIntegrityError("native source epoch row missing")
    return int(row["epoch"])


def _check_global_source_identities(
    conn: Connection[Any], *, command: OperatorSourceCommandV1, existing_artifact: bool,
) -> None:
    identities = (
        command.source_artifact_id, command.source_revision_id,
        command.source_span_ref_id, command.evidence_ref_id,
    )
    if len(set(identities)) != len(identities):
        raise PersistenceIntegrityError("source identities overlap")
    checks = (
        ("knowledge_native_source_admissions", "source_artifact_id, source_revision_id"),
        ("knowledge_native_source_spans", "span_id, evidence_ref_id"),
        ("knowledge_operator_source_attestations", "source_span_ref_id, evidence_ref_id"),
    )
    for table, columns in checks:
        first, second = columns.split(", ")
        row = conn.execute(
            sql.SQL("SELECT 1 FROM {}.{} WHERE {} = ANY(%s) OR {} = ANY(%s) LIMIT 1")
            .format(sql.Identifier(SCHEMA), sql.Identifier(table),
                    sql.Identifier(first), sql.Identifier(second)),
            (list(identities), list(identities)),
        ).fetchone()
        if row is not None:
            raise PersistenceIntegrityError("global source identity collision")
    rows = conn.execute(
        sql.SQL("SELECT space_id, source_artifact_id, source_revision_id FROM "
                "{}.knowledge_operator_source_artifacts "
                "WHERE source_artifact_id = ANY(%s) OR source_revision_id = ANY(%s)")
        .format(sql.Identifier(SCHEMA)),
        (list(identities), list(identities)),
    ).fetchall()
    if rows and not (
        existing_artifact and len(rows) == 1
        and rows[0]["space_id"] == command.space_id
        and rows[0]["source_artifact_id"] == command.source_artifact_id
        and rows[0]["source_revision_id"] == command.source_revision_id
    ):
        raise PersistenceIntegrityError("global artifact identity collision")


def _read_prepared(
    conn: Connection[Any], space_id: str, operation_id: str,
) -> PreparedOperatorSourceV1 | None:
    row = conn.execute(
        sql.SQL("SELECT preparation_sha256, payload, record_fingerprint FROM "
                "{}.knowledge_operator_source_preparations "
                "WHERE space_id = %s AND operation_id = %s").format(sql.Identifier(SCHEMA)),
        (space_id, operation_id),
    ).fetchone()
    if row is None:
        return None
    try:
        value = PreparedOperatorSourceV1.model_validate(row["payload"])
    except Exception as exc:
        raise PersistenceIntegrityError("operator preparation corrupt") from exc
    if (
        value.command.space_id != space_id
        or value.command.operation_id != operation_id
        or value.preparation_sha256 != row["preparation_sha256"]
        or canonical_sha256(value.model_dump(mode="json")) != row["record_fingerprint"]
    ):
        raise PersistenceIntegrityError("operator preparation fingerprint drift")
    return value


def _read_artifact(
    conn: Connection[Any], space_id: str, artifact_id: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        sql.SQL("SELECT * FROM {}.knowledge_operator_source_artifacts "
                "WHERE space_id = %s AND source_artifact_id = %s").format(
                    sql.Identifier(SCHEMA)
                ),
        (space_id, artifact_id),
    ).fetchone()
    if row is None:
        return None
    try:
        policy = SourceArtifactV3.model_validate(row["policy"])
        revision = SourceRevisionV2.model_validate(row["source_revision"])
        body = bytes(row["body_bytes"])
    except Exception as exc:
        raise PersistenceIntegrityError("operator source artifact corrupt") from exc
    payload = {
        "space_id": row["space_id"],
        "source_artifact_id": row["source_artifact_id"],
        "source_revision_id": row["source_revision_id"],
        "legacy_world_id": row["legacy_world_id"],
        "body_sha256": row["body_sha256"],
        "policy": policy.model_dump(mode="json"),
        "source_revision": revision.model_dump(mode="json"),
        "source_authority_epoch": row["source_authority_epoch"],
    }
    if (
        canonical_sha256(payload) != row["record_fingerprint"]
        or canonical_sha256(payload["policy"]) != row["policy_sha256"]
        or hashlib.sha256(body).hexdigest() != row["body_sha256"]
        or policy.source_artifact_id != artifact_id
        or revision.source_artifact_id != artifact_id
        or revision.source_revision_id != row["source_revision_id"]
    ):
        raise PersistenceIntegrityError("operator source artifact fingerprint drift")
    return {"policy": policy, "revision": revision, "body": body,
            "epoch": row["source_authority_epoch"], "policy_sha256": row["policy_sha256"]}


def _read_attestation(
    conn: Connection[Any], space_id: str, operation_id: str,
) -> tuple[OperatorSourceAttestationReceiptV1, NativeUtf8SpanProofV1] | None:
    row = conn.execute(
        sql.SQL("SELECT * FROM {}.knowledge_operator_source_attestations "
                "WHERE space_id = %s AND operation_id = %s").format(sql.Identifier(SCHEMA)),
        (space_id, operation_id),
    ).fetchone()
    if row is None:
        return None
    try:
        receipt = OperatorSourceAttestationReceiptV1.model_validate(row["receipt"])
        proof = NativeUtf8SpanProofV1.model_validate(row["proof"])
    except Exception as exc:
        raise PersistenceIntegrityError("operator attestation corrupt") from exc
    if (
        receipt.command.space_id != space_id
        or receipt.command.operation_id != operation_id
        or receipt.command.source_artifact_id != row["source_artifact_id"]
        or receipt.command.source_span_ref_id != row["source_span_ref_id"]
        or receipt.command.evidence_ref_id != row["evidence_ref_id"]
        or receipt.source_authority_epoch != row["source_authority_epoch"]
        or receipt.record_fingerprint != row["record_fingerprint"]
        or canonical_sha256(receipt.model_dump(mode="json", exclude={"record_fingerprint"}))
           != receipt.record_fingerprint
        or proof.span_id != receipt.command.source_span_ref_id
        or proof.evidence_ref_id != receipt.command.evidence_ref_id
        or proof.source_revision_id != receipt.command.source_revision_id
        or proof.start_byte != receipt.command.start_byte
        or proof.end_byte != receipt.command.end_byte
        or proof.slice_sha256 != receipt.command.slice_sha256
    ):
        raise PersistenceIntegrityError("operator attestation fingerprint drift")
    prepared = _read_prepared(conn, space_id, operation_id)
    artifact = _read_artifact(conn, space_id, receipt.command.source_artifact_id)
    if (
        prepared is None or prepared.command != receipt.command
        or prepared.preparation_sha256 != receipt.preparation_sha256
        or prepared.review_display_sha256 != receipt.review_display_sha256
        or artifact is None
        or artifact["policy"] != receipt.command.native_policy
        or artifact["revision"].content_sha256 != receipt.command.body_sha256
        or artifact["epoch"] > receipt.source_authority_epoch
        or proof.end_byte > len(artifact["body"])
        or hashlib.sha256(
            artifact["body"][proof.start_byte:proof.end_byte]
        ).hexdigest() != proof.slice_sha256
    ):
        raise PersistenceIntegrityError("operator preparation/receipt drift")
    return receipt, proof


class PostgresOperatorSourceRepository(PostgresNativeSourceEvidenceRepository):
    """Source-epoch-before-space locked PostgreSQL adapter; no graph publication."""

    def __init__(
        self, database: PostgresDatabase, *,
        approval_authority: OperatorApprovalVerifier,
        after_operator_artifact_insert: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(database)
        self._approval_authority = approval_authority
        self._after_operator_artifact_insert = after_operator_artifact_insert

    def prepare_operator_source_span(
        self, *, selection: OperatorSourceSelectionV1,
        domain_contract: DomainContractDescriptor,
    ) -> PreparedOperatorSourceV1:
        with self._database.transaction() as conn:
            _lock_native_epoch(conn)
            _lock_space(conn, selection.space_id, created_at=datetime.now(UTC))
            head = _read_head(conn, selection.space_id)
            stored = _read_revision(
                conn, selection.space_id, selection.expected_head_revision_id
            )
            if (head is None or stored is None
                    or head.head_revision_id != selection.expected_head_revision_id):
                raise PersistenceIntegrityError("operator expected head changed")
            legacy_artifact, legacy_revision = _legacy_pair(
                conn, selection.source_artifact_id, selection.source_revision_id,
            )
            epoch = _current_epoch(conn)
            prepared = validate_operator_source_selection(
                selection=selection, domain_contract=domain_contract,
                authority=self._approval_authority, head_revision=stored,
                legacy_artifact=legacy_artifact, legacy_revision=legacy_revision,
                source_epoch=epoch,
            )
            prior = _read_prepared(conn, selection.space_id, selection.operation_id)
            if prior is not None:
                if prior.command != prepared.command:
                    raise PersistenceIntegrityError("operator preparation ID conflict")
                return prior
            conn.execute(
                sql.SQL("INSERT INTO {}.knowledge_operator_source_preparations "
                        "(space_id, operation_id, preparation_sha256, expires_at, "
                        "payload, record_fingerprint) VALUES (%s, %s, %s, %s, %s, %s)").format(
                            sql.Identifier(SCHEMA)
                        ),
                (selection.space_id, selection.operation_id, prepared.preparation_sha256,
                 prepared.expires_at, jsonb(prepared.model_dump(mode="json")),
                 canonical_sha256(prepared.model_dump(mode="json"))),
            )
            return prepared

    def get_operator_source_receipt(
        self, space_id: str, operation_id: str,
    ) -> OperatorSourceAttestationReceiptV1 | None:
        with self._database.transaction() as conn:
            pair = _read_attestation(conn, space_id, operation_id)
            return None if pair is None else pair[0]

    def commit_operator_source_span(
        self, *, space_id: str, operation_id: str, body_text: str,
        approval: TrustedOperatorApproval,
        domain_contract: DomainContractDescriptor,
    ) -> OperatorSourceAttestationReceiptV1:
        with self._database.transaction() as conn:
            _lock_native_epoch(conn)
            _lock_space(conn, space_id, created_at=datetime.now(UTC))
            prior = _read_attestation(conn, space_id, operation_id)
            if prior is not None:
                receipt = prior[0]
                self._approval_authority.verify(
                    approval, space_id=space_id, world_id=receipt.command.legacy_world_id,
                    operation_id=operation_id,
                    preparation_sha256=receipt.preparation_sha256,
                    source_vocabulary_sha256=receipt.command.source_vocabulary_sha256,
                )
                if hashlib.sha256(body_text.encode("utf-8", "strict")).hexdigest() != (
                    receipt.command.body_sha256
                ):
                    raise PersistenceIntegrityError("operator replay body conflict")
                return receipt
            prepared = _read_prepared(conn, space_id, operation_id)
            if prepared is None:
                raise PersistenceIntegrityError("operator preparation missing")
            command = prepared.command
            self._approval_authority.verify(
                approval, space_id=space_id, world_id=command.legacy_world_id,
                operation_id=operation_id,
                preparation_sha256=prepared.preparation_sha256,
                source_vocabulary_sha256=command.source_vocabulary_sha256,
            )
            if datetime.now(UTC) >= prepared.expires_at:
                raise PersistenceIntegrityError("operator preparation expired")
            epoch = _current_epoch(conn)
            if epoch != command.expected_source_epoch:
                raise PersistenceIntegrityError("source epoch changed")
            head = _read_head(conn, space_id)
            stored = _read_revision(conn, space_id, command.expected_head_revision_id)
            if (head is None or stored is None
                    or head.head_revision_id != command.expected_head_revision_id):
                raise PersistenceIntegrityError("native head changed")
            body = body_text.encode("utf-8", "strict")
            if (hashlib.sha256(body).hexdigest() != command.body_sha256
                    or command.end_byte > len(body)):
                raise PersistenceIntegrityError("prepared body changed")
            passage = body[command.start_byte:command.end_byte]
            passage_text = passage.decode("utf-8", "strict")
            if hashlib.sha256(passage).hexdigest() != command.slice_sha256:
                raise PersistenceIntegrityError("prepared passage changed")
            legacy_artifact, legacy_revision = _legacy_pair(
                conn, command.source_artifact_id, command.source_revision_id,
            )
            selection = OperatorSourceSelectionV1(
                space_id=space_id, legacy_world_id=command.legacy_world_id,
                operation_id=operation_id,
                expected_head_revision_id=command.expected_head_revision_id,
                claim_kind=command.claim_kind, claim_id=command.claim_id,
                evidence_ref_id=command.evidence_ref_id,
                source_artifact_id=command.source_artifact_id,
                source_revision_id=command.source_revision_id,
                source_span_ref_id=command.source_span_ref_id,
                expected_body_sha256=command.body_sha256, body_text=body_text,
                passage_text=passage_text,
                occurrence_index=self._occurrence_index(body, passage, command.start_byte),
                native_policy=command.native_policy,
                source_vocabulary=sorted(self._approval_authority.allowed_source_terms),
                gm_label=command.gm_label,
            )
            rechecked = validate_operator_source_selection(
                selection=selection, domain_contract=domain_contract,
                authority=self._approval_authority, head_revision=stored,
                legacy_artifact=legacy_artifact, legacy_revision=legacy_revision,
                source_epoch=epoch, prepared_at=prepared.prepared_at,
            )
            if rechecked != prepared:
                raise PersistenceIntegrityError("prepared review/policy changed")
            existing_artifact = _read_artifact(conn, space_id, command.source_artifact_id)
            policy_sha = canonical_sha256(command.native_policy.model_dump(mode="json"))
            if existing_artifact is not None and (
                existing_artifact["policy_sha256"] != policy_sha
                or existing_artifact["revision"].source_revision_id != command.source_revision_id
                or existing_artifact["body"] != body
            ):
                raise PersistenceIntegrityError("artifact-wide source policy conflict")
            _check_global_source_identities(
                conn, command=command,
                existing_artifact=existing_artifact is not None,
            )
            new_epoch = epoch + 1
            native_revision = SourceRevisionV2(
                source_revision_id=command.source_revision_id,
                source_artifact_id=command.source_artifact_id,
                content_sha256=command.body_sha256,
                body_storage=NATIVE_TEXT_BODY_STORAGE,
                created_at=legacy_revision.created_at,
            )
            proof = NativeUtf8SpanProofV1(
                span_id=command.source_span_ref_id,
                source_revision_id=command.source_revision_id,
                evidence_ref_id=command.evidence_ref_id,
                start_byte=command.start_byte, end_byte=command.end_byte,
                slice_sha256=command.slice_sha256,
            )
            unsigned = OperatorSourceAttestationReceiptV1(
                command=command,
                preparation_sha256=prepared.preparation_sha256,
                review_display_sha256=prepared.review_display_sha256,
                actor=approval.actor,
                role=approval.role,  # type: ignore[arg-type]
                auth_method=approval.auth_method,
                approved_at=approval.approved_at,
                source_authority_epoch=new_epoch,
                record_fingerprint="0" * 64,
            )
            receipt = unsigned.model_copy(update={
                "record_fingerprint": canonical_sha256(
                    unsigned.model_dump(mode="json", exclude={"record_fingerprint"})
                )
            })
            if existing_artifact is None:
                artifact_record = {
                    "space_id": space_id,
                    "source_artifact_id": command.source_artifact_id,
                    "source_revision_id": command.source_revision_id,
                    "legacy_world_id": command.legacy_world_id,
                    "body_sha256": command.body_sha256,
                    "policy": command.native_policy.model_dump(mode="json"),
                    "source_revision": native_revision.model_dump(mode="json"),
                    "source_authority_epoch": new_epoch,
                }
                conn.execute(
                    sql.SQL("INSERT INTO {}.knowledge_operator_source_artifacts "
                            "(space_id, source_artifact_id, source_revision_id, "
                            "legacy_world_id, body_sha256, body_bytes, policy, "
                            "source_revision, policy_sha256, source_authority_epoch, "
                            "record_fingerprint) VALUES "
                            "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)").format(
                                sql.Identifier(SCHEMA)
                            ),
                    (space_id, command.source_artifact_id, command.source_revision_id,
                     command.legacy_world_id, command.body_sha256, body,
                     jsonb(artifact_record["policy"]),
                     jsonb(artifact_record["source_revision"]), policy_sha,
                     new_epoch, canonical_sha256(artifact_record)),
                )
            if self._after_operator_artifact_insert is not None:
                self._after_operator_artifact_insert()
            conn.execute(
                sql.SQL("INSERT INTO {}.knowledge_operator_source_attestations "
                        "(space_id, operation_id, source_artifact_id, source_span_ref_id, "
                        "evidence_ref_id, source_authority_epoch, proof, receipt, "
                        "record_fingerprint) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)").format(
                            sql.Identifier(SCHEMA)
                        ),
                (space_id, operation_id, command.source_artifact_id,
                 command.source_span_ref_id, command.evidence_ref_id, new_epoch,
                 jsonb(proof.model_dump(mode="json")),
                 jsonb(receipt.model_dump(mode="json")), receipt.record_fingerprint),
            )
            conn.execute(
                sql.SQL("UPDATE {}.knowledge_native_source_authority SET epoch = %s "
                        "WHERE singleton_id = 1").format(sql.Identifier(SCHEMA)),
                (new_epoch,),
            )
            return receipt

    @staticmethod
    def _occurrence_index(body: bytes, passage: bytes, wanted: int) -> int:
        index = 0
        cursor = 0
        while (found := body.find(passage, cursor)) != -1:
            if found == wanted:
                return index
            index += 1
            cursor = found + 1
        raise PersistenceIntegrityError("prepared occurrence disappeared")

    def open_native_source_view(self, space_id: str) -> NativeTextSourceView:
        return _PostgresOperatorSourceView(
            self._database, space_id, super().open_native_source_view(space_id)
        )


class _PostgresOperatorSourceView:
    def __init__(
        self, database: PostgresDatabase, space_id: str, base: NativeTextSourceView,
    ) -> None:
        self._database, self._space_id, self._base = database, space_id, base

    @property
    def epoch(self) -> int:
        return self._base.epoch

    def open_coherent_view(self) -> _PostgresOperatorSourceView:
        return _PostgresOperatorSourceView(
            self._database, self._space_id, self._base.open_coherent_view()
        )

    def get_provenance_snapshot(
        self, *, artifact_ids: Sequence[str], revision_ids: Sequence[str],
    ) -> KnowledgeProvenanceSnapshot:
        base = self._base.get_provenance_snapshot(
            artifact_ids=artifact_ids, revision_ids=revision_ids,
        )
        artifacts = dict(base.artifacts_by_id)
        revisions = dict(base.revisions_by_id)
        if artifact_ids or revision_ids:
            with self._database.transaction() as conn:
                rows = conn.execute(
                    sql.SQL("SELECT source_artifact_id FROM "
                            "{}.knowledge_operator_source_artifacts "
                            "WHERE space_id = %s AND source_authority_epoch <= %s "
                            "AND (source_artifact_id = ANY(%s) "
                            "OR source_revision_id = ANY(%s))").format(sql.Identifier(SCHEMA)),
                    (self._space_id, self.epoch, list(artifact_ids), list(revision_ids)),
                ).fetchall()
                for row in rows:
                    item = _read_artifact(conn, self._space_id, row["source_artifact_id"])
                    if item is None:
                        raise PersistenceIntegrityError("operator source artifact disappeared")
                    artifact_id = row["source_artifact_id"]
                    attestation_row = conn.execute(
                        sql.SQL("SELECT operation_id FROM "
                                "{}.knowledge_operator_source_attestations "
                                "WHERE space_id = %s AND source_artifact_id = %s "
                                "AND source_authority_epoch <= %s "
                                "ORDER BY source_authority_epoch LIMIT 1").format(
                                    sql.Identifier(SCHEMA)
                                ),
                        (self._space_id, artifact_id, self.epoch),
                    ).fetchone()
                    if (
                        attestation_row is None
                        or _read_attestation(
                            conn, self._space_id, attestation_row["operation_id"]
                        ) is None
                    ):
                        raise PersistenceIntegrityError("operator source has no attestation")
                    revision_id = item["revision"].source_revision_id
                    legacy_artifact, legacy_revision = _legacy_pair(
                        conn, artifact_id, revision_id,
                    )
                    if legacy_artifact is None or legacy_revision is None:
                        raise PersistenceIntegrityError("legacy source pair disappeared")
                    if legacy_revision.content_sha256 != item["revision"].content_sha256:
                        raise PersistenceIntegrityError("legacy/native body digest drift")
                    if (
                        legacy_artifact.status != SourceStatus.ACTIVE
                        or legacy_artifact.current_revision_id != revision_id
                    ):
                        continue
                    if artifact_id in artifact_ids:
                        artifacts[artifact_id] = item["policy"]
                    if revision_id in revision_ids:
                        revisions[revision_id] = item["revision"]
        return _build_snapshot_from_loaded(
            loaded_artifacts=artifacts, loaded_revisions=revisions,
            requested_artifacts=tuple(sorted(set(artifact_ids))),
            requested_revisions=tuple(sorted(set(revision_ids))),
            missing_artifacts=tuple(a for a in artifact_ids if a not in artifacts),
            missing_revisions=tuple(r for r in revision_ids if r not in revisions),
        )

    def get_native_text_source(
        self, *, source_artifact_id: str, source_revision_id: str, span_id: str,
    ) -> StoredNativeTextSource | None:
        base = self._base.get_native_text_source(
            source_artifact_id=source_artifact_id,
            source_revision_id=source_revision_id, span_id=span_id,
        )
        if base is not None:
            return base
        with self._database.transaction() as conn:
            row = conn.execute(
                sql.SQL("SELECT operation_id FROM "
                        "{}.knowledge_operator_source_attestations "
                        "WHERE space_id = %s AND source_artifact_id = %s "
                        "AND source_span_ref_id = %s AND source_authority_epoch <= %s").format(
                            sql.Identifier(SCHEMA)
                        ),
                (self._space_id, source_artifact_id, span_id, self.epoch),
            ).fetchone()
            if row is None:
                return None
            pair = _read_attestation(conn, self._space_id, row["operation_id"])
            artifact = _read_artifact(conn, self._space_id, source_artifact_id)
            if pair is None or artifact is None:
                raise PersistenceIntegrityError("operator source record disappeared")
            receipt, proof = pair
            if (
                receipt.command.source_revision_id != source_revision_id
                or artifact["revision"].source_revision_id != source_revision_id
                or artifact["epoch"] > self.epoch
            ):
                return None
            legacy_artifact, legacy_revision = _legacy_pair(
                conn, source_artifact_id, source_revision_id,
            )
            if legacy_artifact is None or legacy_revision is None:
                raise PersistenceIntegrityError("legacy source pair disappeared")
            if legacy_revision.content_sha256 != artifact["revision"].content_sha256:
                raise PersistenceIntegrityError("legacy/native body digest drift")
            if (
                legacy_artifact.status != SourceStatus.ACTIVE
                or legacy_artifact.current_revision_id != source_revision_id
            ):
                return None
            return StoredNativeTextSource(
                source_artifact=artifact["policy"],
                source_revision=artifact["revision"],
                body_bytes=artifact["body"], span_proof=proof,
                authority_epoch=receipt.source_authority_epoch,
            )
