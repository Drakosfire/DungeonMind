from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dungeonmind.application.vnext.materialization import (
    NATIVE_VNEXT_GRAPH_SCHEMA,
    encode_native_graph_payload,
)
from dungeonmind.application.vnext.native_source_access import (
    open_admitted_native_text,
    open_native_text_source_access_context,
)
from dungeonmind.application.vnext.operator_approval import (
    OperatorApprovalRejectedError,
    OperatorApprovalVerifier,
    TrustedOperatorApproval,
    operator_approval_signing_message,
)
from dungeonmind.contracts.evidence import (
    SourceArtifactV2,
    SourceAuthority,
    SourceRevision,
    SourceStatus,
)
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext.common import (
    EpistemicBasis,
    KnowledgeStanding,
    LabelsAllVisibility,
    PublicVisibility,
    TimelessTemporalScope,
)
from dungeonmind.contracts.vnext.domain import (
    Assertion,
    AssertionMetadata,
    DomainContractDescriptor,
    DomainContractRef,
    Entity,
    LiteralValue,
    SemanticProfileDescriptorV2,
)
from dungeonmind.contracts.vnext.knowledge import PublishKnowledgeRevisionCommand
from dungeonmind.contracts.vnext.operator_source import OperatorSourceSelectionV1
from dungeonmind.contracts.vnext.source import EvidenceRefV3, SourceArtifactV3
from dungeonmind.contracts.vocabulary import Visibility
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.memory.repositories import InMemorySourceRepository
from dungeonmind.infrastructure.memory.vnext_operator_sources import (
    InMemoryOperatorSourceRepository,
)
from dungeonmind.infrastructure.operator_approval import Ed25519OperatorApprovalVerifier

NOW = datetime(2026, 10, 9, 12, tzinfo=UTC)
BODY = "An amber gate remembers the rain.\n"
GM = "test.visibility:gm"
PLAYER = "test.visibility:player"


class _TestAuthenticatedHostIssuer:
    """Test-only host signer; production Core receives only its public key."""

    def __init__(self, private_key: Ed25519PrivateKey, verifier: OperatorApprovalVerifier):
        self._private_key = private_key
        self.verifier = verifier

    def mint_from_authenticated_host(
        self, *, space_id: str, world_id: str, operation_id: str,
        preparation_sha256: str, source_vocabulary_sha256: str,
        actor: str, role: str, auth_method: str,
    ) -> TrustedOperatorApproval:
        # This helper represents the external authenticated host in tests only.
        unsigned = TrustedOperatorApproval(
            space_id, world_id, operation_id, preparation_sha256,
            source_vocabulary_sha256, actor, role, auth_method, datetime.now(UTC), "",
        )
        signature = self._private_key.sign(operator_approval_signing_message(unsigned)).hex()
        return replace(unsigned, signature=signature)


def _fixture():
    domain = DomainContractDescriptor(
        domain_id="test.operator", domain_revision="1",
        visibility_labels=[GM, PLAYER],
        claim_modes=["test:fact"], admission_policy_id="test:allow",
    )
    profile = SemanticProfileDescriptorV2(
        profile_id="test.profile", profile_revision="1", term_namespaces=["test"],
    )
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    verifier = Ed25519OperatorApprovalVerifier(
        public_key,
        domain_descriptor_sha256=canonical_sha256(domain.model_dump(mode="json")),
        allowed_source_terms=frozenset({"test.source:recap"}), gm_label=GM,
    )
    authority = _TestAuthenticatedHostIssuer(private_key, verifier)
    legacy = InMemorySourceRepository()
    body_sha = hashlib.sha256(BODY.encode()).hexdigest()
    legacy.put_artifact(SourceArtifactV2(
        source_artifact_id="art:amber", source_domain_key="opaque-producer-key",
        source_domain=None, world_id="world:amber", campaign_id=None,
        session_id=None, uri=None, current_revision_id="srev:amber",
        authority=SourceAuthority.PRIMARY, visibility=None,
        artifact_kind=None, document_class=None, review_state=None,
        source_visibility_state=None, workspace_document_ref=None,
        status=SourceStatus.ACTIVE, created_at=NOW, updated_at=NOW,
    ))
    legacy.put_revision(SourceRevision(
        source_revision_id="srev:amber", source_artifact_id="art:amber",
        content_sha256=body_sha, body_storage="postgres", created_at=NOW,
    ))
    repo = InMemoryOperatorSourceRepository(
        legacy_sources=legacy, approval_authority=verifier,
    )
    assertion = Assertion(
        assertion_id="assert:amber", subject_entity_id="ent:gate",
        predicate="test:title", value=LiteralValue(value="Amber Gate"),
        metadata=AssertionMetadata(
            scope=[], visibility=PublicVisibility(),
            epistemic_basis=EpistemicBasis.ASSERTED,
            claim_mode="test:fact", standing=KnowledgeStanding.ESTABLISHED,
            evidence_ref_ids=["ev:amber"], temporal_scope=TimelessTemporalScope(),
        ),
    )
    evidence = EvidenceRefV3(
        evidence_ref_id="ev:amber", source_artifact_id="art:amber",
        source_revision_id="srev:amber", evidence_role="support",
        can_open_source=True, can_highlight_span=True,
        source_span_ref_id="span:amber",
    )
    command = PublishKnowledgeRevisionCommand(
        space_id="space:amber", parent_revision_id=None,
        expected_parent_revision_id=None, operation_ids=["op:genesis"],
        graph_schema=NATIVE_VNEXT_GRAPH_SCHEMA,
        graph_payload=encode_native_graph_payload(
            entities={"ent:gate": Entity(entity_id="ent:gate")},
            assertions={assertion.assertion_id: assertion}, aliases={},
            evidence={evidence.evidence_ref_id: evidence},
        ),
        domain_contract_ref=DomainContractRef(
            domain_id=domain.domain_id, domain_revision=domain.domain_revision,
            descriptor_sha256=canonical_sha256(domain.model_dump(mode="json")),
        ),
        semantic_profile_ref=SemanticProfileRef(
            profile_id=profile.profile_id, profile_revision=profile.profile_revision,
            descriptor_sha256=canonical_sha256(profile.model_dump(mode="json")),
        ),
        created_at=NOW,
    )
    head = repo.publish_revision(command)
    policy = SourceArtifactV3(
        source_artifact_id="art:amber", source_classification="test.source:recap",
        current_revision_id="srev:amber", authority="primary",
        visibility=LabelsAllVisibility(labels=[GM]), status="active",
    )
    selection = OperatorSourceSelectionV1(
        space_id="space:amber", legacy_world_id="world:amber",
        operation_id="attest:amber", expected_head_revision_id=head.revision.revision_id,
        claim_kind="assertion", claim_id="assert:amber", evidence_ref_id="ev:amber",
        source_artifact_id="art:amber", source_revision_id="srev:amber",
        source_span_ref_id="span:amber", expected_body_sha256=body_sha,
        body_text=BODY, passage_text="amber gate", native_policy=policy,
        source_vocabulary=["test.source:recap"], gm_label=GM,
    )
    return repo, legacy, domain, authority, selection


def test_operator_attested_binding_preserves_graph_and_restricts_source() -> None:
    repo, legacy, domain, authority, selection = _fixture()
    old = repo.open_native_source_view(selection.space_id)
    before_head = repo.get_head(selection.space_id)
    before_legacy = legacy.get_artifact(selection.source_artifact_id)
    prepared = repo.prepare_operator_source_span(
        selection=selection, domain_contract=domain,
    )
    assert prepared.command.start_byte == BODY.encode().find(b"amber gate")
    assert repo.open_native_source_view(selection.space_id).epoch == old.epoch
    approval = authority.mint_from_authenticated_host(
        space_id=selection.space_id, world_id=selection.legacy_world_id,
        operation_id=selection.operation_id,
        preparation_sha256=prepared.preparation_sha256,
        source_vocabulary_sha256=prepared.command.source_vocabulary_sha256,
        actor="local_operator", role="gm", auth_method="session_hmac",
    )
    receipt = repo.commit_operator_source_span(
        space_id=selection.space_id, operation_id=selection.operation_id,
        body_text=BODY, approval=approval, domain_contract=domain,
    )
    assert receipt.actor == "local_operator"
    assert receipt.command.native_policy.visibility.kind == "labels_all"
    assert repo.get_head(selection.space_id) == before_head
    assert legacy.get_artifact(selection.source_artifact_id) == before_legacy
    assert old.get_native_text_source(
        source_artifact_id="art:amber", source_revision_id="srev:amber",
        span_id="span:amber",
    ) is None
    for audience, expected in [([], "unavailable"), ([PLAYER], "unavailable"),
                               ([GM], "available")]:
        context = open_native_text_source_access_context(
            repository=repo, space_id=selection.space_id,
            revision_id=selection.expected_head_revision_id,
            domain_contract=domain, audience_labels=audience,
        )
        assert open_admitted_native_text(context, "ev:amber").status == expected
    assert repo.commit_operator_source_span(
        space_id=selection.space_id, operation_id=selection.operation_id,
        body_text=BODY, approval=approval, domain_contract=domain,
    ) == receipt


def test_forged_approval_and_conflicting_policy_fail_without_epoch_mutation() -> None:
    repo, _, domain, authority, selection = _fixture()
    prepared = repo.prepare_operator_source_span(selection=selection, domain_contract=domain)
    epoch = repo.open_native_source_view(selection.space_id).epoch
    with pytest.raises(OperatorApprovalRejectedError):
        repo.commit_operator_source_span(
            space_id=selection.space_id, operation_id=selection.operation_id,
            body_text=BODY, approval={"actor": "gm"},  # type: ignore[arg-type]
            domain_contract=domain,
        )
    assert repo.open_native_source_view(selection.space_id).epoch == epoch
    bad = selection.model_copy(deep=True)
    bad.native_policy.source_classification = "test.source:unknown"
    with pytest.raises(PersistenceIntegrityError):
        repo.prepare_operator_source_span(selection=bad, domain_contract=domain)
    approval = authority.mint_from_authenticated_host(
        space_id=selection.space_id, world_id=selection.legacy_world_id,
        operation_id=selection.operation_id,
        preparation_sha256=prepared.preparation_sha256,
        source_vocabulary_sha256=prepared.command.source_vocabulary_sha256,
        actor="local_operator", role="gm", auth_method="session_hmac",
    )
    with pytest.raises(PersistenceIntegrityError):
        repo.commit_operator_source_span(
            space_id=selection.space_id, operation_id=selection.operation_id,
            body_text=BODY.replace("amber", "silver"), approval=approval,
            domain_contract=domain,
        )
    assert repo.open_native_source_view(selection.space_id).epoch == epoch


@pytest.mark.parametrize("change", [
    "unknown_classification", "public_policy", "player_policy", "absent_gm_label",
    "conflicting_legacy_visibility", "inactive_legacy", "wrong_body",
    "ambiguous_passage", "wrong_evidence", "wrong_span",
])
def test_prepare_rejections_leave_all_authority_unmodified(change: str) -> None:
    repo, legacy, domain, _, selection = _fixture()
    before_head = repo.get_head(selection.space_id)
    before_epoch = repo.open_native_source_view(selection.space_id).epoch
    if change == "unknown_classification":
        selection.native_policy.source_classification = "test.source:unknown"
    elif change == "public_policy":
        selection.native_policy.visibility = PublicVisibility()
    elif change == "player_policy":
        selection.native_policy.visibility = LabelsAllVisibility(labels=[PLAYER])
    elif change == "absent_gm_label":
        domain.visibility_labels = [PLAYER]
    elif change == "conflicting_legacy_visibility":
        item = legacy.get_artifact(selection.source_artifact_id)
        assert item is not None
        legacy._artifacts[selection.source_artifact_id] = item.model_copy(
            update={"visibility": Visibility.PLAYER}
        )
    elif change == "inactive_legacy":
        item = legacy.get_artifact(selection.source_artifact_id)
        assert item is not None
        legacy._artifacts[selection.source_artifact_id] = item.model_copy(
            update={"status": SourceStatus.RETRACTED}
        )
    elif change == "wrong_body":
        selection.body_text = BODY.replace("amber", "silver")
    elif change == "ambiguous_passage":
        selection.passage_text = "a"
    elif change == "wrong_evidence":
        selection.evidence_ref_id = "ev:other"
    elif change == "wrong_span":
        selection.source_span_ref_id = "span:other"
    with pytest.raises(PersistenceIntegrityError):
        repo.prepare_operator_source_span(selection=selection, domain_contract=domain)
    assert repo.open_native_source_view(selection.space_id).epoch == before_epoch
    assert repo.get_head(selection.space_id) == before_head
    assert repo.get_operator_source_receipt(selection.space_id, selection.operation_id) is None
    assert not repo._operator_artifacts
    assert not repo._operator_spans


def test_tampered_prepared_display_and_wrong_world_approval_fail_closed() -> None:
    repo, _, domain, authority, selection = _fixture()
    prepared = repo.prepare_operator_source_span(selection=selection, domain_contract=domain)
    wrong_world = authority.mint_from_authenticated_host(
        space_id=selection.space_id, world_id="world:other",
        operation_id=selection.operation_id,
        preparation_sha256=prepared.preparation_sha256,
        source_vocabulary_sha256=prepared.command.source_vocabulary_sha256,
        actor="local_operator", role="gm", auth_method="session_hmac",
    )
    with pytest.raises(OperatorApprovalRejectedError):
        repo.commit_operator_source_span(
            space_id=selection.space_id, operation_id=selection.operation_id,
            body_text=BODY, approval=wrong_world, domain_contract=domain,
        )
    good = authority.mint_from_authenticated_host(
        space_id=selection.space_id, world_id=selection.legacy_world_id,
        operation_id=selection.operation_id,
        preparation_sha256=prepared.preparation_sha256,
        source_vocabulary_sha256=prepared.command.source_vocabulary_sha256,
        actor="local_operator", role="gm", auth_method="session_hmac",
    )
    key = (selection.space_id, selection.operation_id)
    repo._operator_prepared[key] = prepared.model_copy(update={"review_excerpt": "forged"})
    with pytest.raises(PersistenceIntegrityError):
        repo.commit_operator_source_span(
            space_id=selection.space_id, operation_id=selection.operation_id,
            body_text=BODY, approval=good, domain_contract=domain,
        )
    assert repo.open_native_source_view(selection.space_id).epoch == 0
    assert repo.get_operator_source_receipt(*key) is None


def test_core_verifier_cannot_mint_and_forged_host_claims_fail() -> None:
    repo, _, domain, host_issuer, selection = _fixture()
    verifier = repo._approval_authority
    assert not hasattr(verifier, "mint_from_authenticated_host")
    assert not hasattr(verifier, "new_for_process")

    fabricated = TrustedOperatorApproval(
        space_id=selection.space_id,
        world_id=selection.legacy_world_id,
        operation_id=selection.operation_id,
        preparation_sha256="0" * 64,
        source_vocabulary_sha256="0" * 64,
        actor="attacker-selected-actor",
        role="owner",
        auth_method="caller-asserted",
        approved_at=NOW,
        signature="00" * 64,
    )
    with pytest.raises(OperatorApprovalRejectedError):
        verifier.verify(
            fabricated,
            space_id=selection.space_id,
            world_id=selection.legacy_world_id,
            operation_id=selection.operation_id,
            preparation_sha256=fabricated.preparation_sha256,
            source_vocabulary_sha256=fabricated.source_vocabulary_sha256,
        )

    prepared = repo.prepare_operator_source_span(selection=selection, domain_contract=domain)
    approval = host_issuer.mint_from_authenticated_host(
        space_id=selection.space_id,
        world_id=selection.legacy_world_id,
        operation_id=selection.operation_id,
        preparation_sha256=prepared.preparation_sha256,
        source_vocabulary_sha256=prepared.command.source_vocabulary_sha256,
        actor="authenticated-operator",
        role="gm",
        auth_method="test-session",
    )
    for forged in (
        replace(approval, actor="attacker-selected-actor"),
        replace(approval, role="owner"),
        replace(approval, world_id="world:attacker-selected"),
    ):
        with pytest.raises(OperatorApprovalRejectedError):
            verifier.verify(
                forged,
                space_id=selection.space_id,
                world_id=selection.legacy_world_id,
                operation_id=selection.operation_id,
                preparation_sha256=prepared.preparation_sha256,
                source_vocabulary_sha256=prepared.command.source_vocabulary_sha256,
            )


def test_same_operation_concurrent_approvals_return_one_receipt() -> None:
    repo, _, domain, authority, selection = _fixture()
    prepared = repo.prepare_operator_source_span(selection=selection, domain_contract=domain)
    approval = authority.mint_from_authenticated_host(
        space_id=selection.space_id, world_id=selection.legacy_world_id,
        operation_id=selection.operation_id,
        preparation_sha256=prepared.preparation_sha256,
        source_vocabulary_sha256=prepared.command.source_vocabulary_sha256,
        actor="local_operator", role="gm", auth_method="session_hmac",
    )
    def commit(_: int):
        return repo.commit_operator_source_span(
            space_id=selection.space_id, operation_id=selection.operation_id,
            body_text=BODY, approval=approval, domain_contract=domain,
        )
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(commit, (1, 2)))
    assert receipts[0] == receipts[1]
    assert repo.open_native_source_view(selection.space_id).epoch == 1


def test_fault_after_artifact_insert_rolls_back_all_operator_authority() -> None:
    repo, _, domain, authority, selection = _fixture()
    prepared = repo.prepare_operator_source_span(selection=selection, domain_contract=domain)
    approval = authority.mint_from_authenticated_host(
        space_id=selection.space_id, world_id=selection.legacy_world_id,
        operation_id=selection.operation_id,
        preparation_sha256=prepared.preparation_sha256,
        source_vocabulary_sha256=prepared.command.source_vocabulary_sha256,
        actor="local_operator", role="gm", auth_method="session_hmac",
    )
    def fail() -> None:
        raise RuntimeError("injected after-artifact failure")
    repo._after_operator_artifact_insert = fail
    before_head = repo.get_head(selection.space_id)
    with pytest.raises(RuntimeError, match="injected"):
        repo.commit_operator_source_span(
            space_id=selection.space_id, operation_id=selection.operation_id,
            body_text=BODY, approval=approval, domain_contract=domain,
        )
    assert repo.open_native_source_view(selection.space_id).epoch == 0
    assert repo.get_head(selection.space_id) == before_head
    assert repo.get_operator_source_receipt(selection.space_id, selection.operation_id) is None
    assert not repo._operator_artifacts
    assert not repo._operator_spans
    repo._after_operator_artifact_insert = None
    assert repo.commit_operator_source_span(
        space_id=selection.space_id, operation_id=selection.operation_id,
        body_text=BODY, approval=approval, domain_contract=domain,
    ).source_authority_epoch == 1


def test_later_binding_cannot_replace_artifact_wide_policy() -> None:
    repo, _, domain, authority, selection = _fixture()
    prepared = repo.prepare_operator_source_span(selection=selection, domain_contract=domain)
    approval = authority.mint_from_authenticated_host(
        space_id=selection.space_id, world_id=selection.legacy_world_id,
        operation_id=selection.operation_id,
        preparation_sha256=prepared.preparation_sha256,
        source_vocabulary_sha256=prepared.command.source_vocabulary_sha256,
        actor="local_operator", role="gm", auth_method="session_hmac",
    )
    original = repo.commit_operator_source_span(
        space_id=selection.space_id, operation_id=selection.operation_id,
        body_text=BODY, approval=approval, domain_contract=domain,
    )
    later = selection.model_copy(deep=True)
    later.operation_id = "attest:later"
    later.native_policy.foreign_refs = ["ref:changed"]
    later_prepared = repo.prepare_operator_source_span(
        selection=later, domain_contract=domain,
    )
    later_approval = authority.mint_from_authenticated_host(
        space_id=later.space_id, world_id=later.legacy_world_id,
        operation_id=later.operation_id,
        preparation_sha256=later_prepared.preparation_sha256,
        source_vocabulary_sha256=later_prepared.command.source_vocabulary_sha256,
        actor="local_operator", role="gm", auth_method="session_hmac",
    )
    with pytest.raises(PersistenceIntegrityError, match="policy/body conflict"):
        repo.commit_operator_source_span(
            space_id=later.space_id, operation_id=later.operation_id,
            body_text=BODY, approval=later_approval, domain_contract=domain,
        )
    assert repo.open_native_source_view(selection.space_id).epoch == 1
    assert repo.get_operator_source_receipt(selection.space_id, selection.operation_id) == original
    assert repo.get_operator_source_receipt(later.space_id, later.operation_id) is None
