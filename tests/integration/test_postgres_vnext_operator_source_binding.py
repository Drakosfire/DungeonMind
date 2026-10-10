from __future__ import annotations

import hashlib

import pytest

from dungeonmind.application.vnext.native_source_access import (
    open_admitted_native_text,
    open_native_text_source_access_context,
)
from dungeonmind.application.vnext.operator_approval import OperatorApprovalRejectedError
from dungeonmind.contracts.vnext.knowledge import PublishKnowledgeRevisionCommand
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.postgres.records import PostgresSourceRepository
from dungeonmind.infrastructure.postgres.vnext_operator_sources import (
    PostgresOperatorSourceRepository,
)
from tests.unit.test_vnext_operator_source_binding import BODY, GM, _fixture

pytestmark = pytest.mark.integration


def _pg_fixture(pg):
    memory, legacy_memory, domain, authority, selection = _fixture()
    legacy = PostgresSourceRepository(pg.database)
    legacy.put_artifact(legacy_memory.get_artifact(selection.source_artifact_id))
    legacy.put_revision(legacy_memory.get_revision(selection.source_revision_id))
    repo = PostgresOperatorSourceRepository(
        pg.database, approval_authority=authority,
    )
    stored = memory.get_revision(selection.space_id, selection.expected_head_revision_id)
    assert stored is not None
    repo.publish_revision(PublishKnowledgeRevisionCommand(
        space_id=selection.space_id, parent_revision_id=None,
        expected_parent_revision_id=None,
        operation_ids=list(stored.revision.operation_ids),
        graph_schema=stored.revision.graph_schema,
        graph_payload=stored.graph_payload,
        domain_contract_ref=stored.revision.domain_contract_ref,
        semantic_profile_ref=stored.revision.semantic_profile_ref,
        migration_origin_ref=stored.revision.migration_origin_ref,
        created_at=stored.revision.created_at,
    ))
    return repo, legacy, domain, authority, selection


def _approval(authority, selection, prepared):
    return authority.mint_from_authenticated_host(
        space_id=selection.space_id, world_id=selection.legacy_world_id,
        operation_id=selection.operation_id,
        preparation_sha256=prepared.preparation_sha256,
        source_vocabulary_sha256=prepared.command.source_vocabulary_sha256,
        actor="local_operator", role="gm", auth_method="session_hmac",
    )


def test_postgres_operator_attestation_is_atomic_and_gm_only(pg) -> None:
    repo, legacy, domain, authority, selection = _pg_fixture(pg)
    head = repo.get_head(selection.space_id)
    old = repo.open_native_source_view(selection.space_id)
    legacy_before = legacy.get_artifact(selection.source_artifact_id)
    prepared = repo.prepare_operator_source_span(
        selection=selection, domain_contract=domain,
    )
    assert repo.open_native_source_view(selection.space_id).epoch == old.epoch
    approval = _approval(authority, selection, prepared)
    with pytest.raises(PersistenceIntegrityError):
        repo.commit_operator_source_span(
            space_id=selection.space_id, operation_id=selection.operation_id,
            body_text=BODY.replace("amber", "silver"), approval=approval,
            domain_contract=domain,
        )
    assert repo.open_native_source_view(selection.space_id).epoch == old.epoch
    assert repo.get_operator_source_receipt(selection.space_id, selection.operation_id) is None
    with pytest.raises(OperatorApprovalRejectedError):
        repo.commit_operator_source_span(
            space_id=selection.space_id, operation_id=selection.operation_id,
            body_text=BODY, approval={"actor": "gm"},  # type: ignore[arg-type]
            domain_contract=domain,
        )
    receipt = repo.commit_operator_source_span(
        space_id=selection.space_id, operation_id=selection.operation_id,
        body_text=BODY, approval=approval, domain_contract=domain,
    )
    assert receipt.source_authority_epoch == old.epoch + 1
    assert repo.get_head(selection.space_id) == head
    assert legacy.get_artifact(selection.source_artifact_id) == legacy_before
    assert old.get_native_text_source(
        source_artifact_id=selection.source_artifact_id,
        source_revision_id=selection.source_revision_id,
        span_id=selection.source_span_ref_id,
    ) is None
    for audience, expected in [([], "unavailable"), (["test.visibility:player"],
                               "unavailable"), ([GM], "available")]:
        context = open_native_text_source_access_context(
            repository=repo, space_id=selection.space_id,
            revision_id=selection.expected_head_revision_id,
            domain_contract=domain, audience_labels=audience,
        )
        access = open_admitted_native_text(context, selection.evidence_ref_id)
        assert access.status == expected
        if expected == "available":
            assert access.body_sha256 == hashlib.sha256(BODY.encode()).hexdigest()
    assert repo.commit_operator_source_span(
        space_id=selection.space_id, operation_id=selection.operation_id,
        body_text=BODY, approval=approval, domain_contract=domain,
    ) == receipt


def test_postgres_operator_fault_rolls_back_artifact_span_receipt_and_epoch(pg) -> None:
    repo, legacy, domain, authority, selection = _pg_fixture(pg)
    prepared = repo.prepare_operator_source_span(selection=selection, domain_contract=domain)
    approval = _approval(authority, selection, prepared)
    before_head = repo.get_head(selection.space_id)
    before_legacy = legacy.get_artifact(selection.source_artifact_id)
    before_epoch = repo.open_native_source_view(selection.space_id).epoch
    def fail() -> None:
        raise RuntimeError("injected after-artifact failure")
    repo._after_operator_artifact_insert = fail
    with pytest.raises(RuntimeError, match="injected"):
        repo.commit_operator_source_span(
            space_id=selection.space_id, operation_id=selection.operation_id,
            body_text=BODY, approval=approval, domain_contract=domain,
        )
    with pg.database.connect() as conn:
        for table in (
            "knowledge_operator_source_artifacts",
            "knowledge_operator_source_attestations",
        ):
            row = conn.execute(
                f"SELECT COUNT(*) AS n FROM dungeonmind.{table}"
            ).fetchone()
            assert row["n"] == 0
    assert repo.open_native_source_view(selection.space_id).epoch == before_epoch
    assert repo.get_head(selection.space_id) == before_head
    assert legacy.get_artifact(selection.source_artifact_id) == before_legacy
    assert repo.get_operator_source_receipt(selection.space_id, selection.operation_id) is None
    repo._after_operator_artifact_insert = None
    assert repo.commit_operator_source_span(
        space_id=selection.space_id, operation_id=selection.operation_id,
        body_text=BODY, approval=approval, domain_contract=domain,
    ).source_authority_epoch == before_epoch + 1


def test_postgres_later_binding_rejects_conflicting_artifact_policy(pg) -> None:
    repo, _, domain, authority, selection = _pg_fixture(pg)
    prepared = repo.prepare_operator_source_span(selection=selection, domain_contract=domain)
    receipt = repo.commit_operator_source_span(
        space_id=selection.space_id, operation_id=selection.operation_id,
        body_text=BODY, approval=_approval(authority, selection, prepared),
        domain_contract=domain,
    )
    later = selection.model_copy(deep=True)
    later.operation_id = "attest:later"
    later.native_policy.foreign_refs = ["ref:changed"]
    later_prepared = repo.prepare_operator_source_span(
        selection=later, domain_contract=domain,
    )
    with pytest.raises(PersistenceIntegrityError, match="policy conflict"):
        repo.commit_operator_source_span(
            space_id=later.space_id, operation_id=later.operation_id,
            body_text=BODY,
            approval=_approval(authority, later, later_prepared),
            domain_contract=domain,
        )
    assert repo.open_native_source_view(selection.space_id).epoch == receipt.source_authority_epoch
    assert repo.get_operator_source_receipt(selection.space_id, selection.operation_id) == receipt
    assert repo.get_operator_source_receipt(later.space_id, later.operation_id) is None
