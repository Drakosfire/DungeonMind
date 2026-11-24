from __future__ import annotations

from datetime import timedelta

import pytest

from dungeonmind.application.vnext.errors import KnowledgePublicationIdempotencyConflictError
from dungeonmind.application.vnext.native_source_access import (
    open_admitted_native_text,
    open_native_text_source_access_context,
)
from dungeonmind.application.vnext.native_source_admission import (
    publish_native_text_source_evidence,
)
from dungeonmind.application.vnext.publication import _publish_validated_command
from dungeonmind.application.vnext.world_copy import (
    NativeWorldCopyError,
    _command,
    copy_native_world,
)
from dungeonmind.contracts.vnext.common import (
    EpistemicBasis,
    KnowledgeStanding,
    LabelsAnyVisibility,
    PublicVisibility,
    UnknownTemporalScope,
)
from dungeonmind.contracts.vnext.domain import (
    Assertion,
    AssertionMetadata,
    Entity,
    EntityRefValue,
    LiteralValue,
)
from dungeonmind.contracts.vnext.knowledge import IdentityAlias
from tests.unit.test_vnext_native_source_admission import BODY, NOW, _initialized, _request


def _source(initialized=None):
    repo, domain, profile, genesis = initialized or _initialized()
    source = _request(parent_revision_id=genesis.published_revision_id)
    admission = publish_native_text_source_evidence(
        repository=repo, request=source, domain_contract=domain, semantic_profile=profile
    )
    evidence = admission.bindings[0].evidence_ref_id
    parent = repo.get_revision(source.space_id, admission.published_revision_id)
    graph = parent.graph_payload
    graph["entities"] = [
        Entity(entity_id="entity:a").model_dump(mode="json"),
        Entity(entity_id="entity:b").model_dump(mode="json"),
    ]
    metadata = AssertionMetadata(
        visibility=PublicVisibility(),
        epistemic_basis=EpistemicBasis.ASSERTED,
        claim_mode="test:fact",
        standing=KnowledgeStanding.ESTABLISHED,
        temporal_scope=UnknownTemporalScope(),
        evidence_ref_ids=[evidence],
    )
    graph["assertions"] = [
        Assertion(
            assertion_id="assertion:name",
            subject_entity_id="entity:a",
            predicate="test:name",
            value=LiteralValue(value="Sizzek"),
            metadata=metadata,
        ).model_dump(mode="json"),
        Assertion(
            assertion_id="assertion:link",
            subject_entity_id="entity:a",
            predicate="test:knows",
            value=EntityRefValue(entity_id="entity:b"),
            metadata=metadata,
        ).model_dump(mode="json"),
    ]
    graph["aliases"] = [
        IdentityAlias(
            alias_id="alias:a",
            entity_id="entity:a",
            alias_text="Sizzek",
            evidence_ref_ids=[evidence],
            standing=KnowledgeStanding.ESTABLISHED,
        ).model_dump(mode="json")
    ]
    original = _publish_validated_command(
        _command(source.space_id, parent, graph, "fixture:graph", NOW + timedelta(minutes=2)),
        publication_id="fixture:graph",
        repository=repo,
    )
    return repo, domain, profile, source, admission, original


def _copy(
    repo, domain, profile, original, *, operation="session:one", when=NOW + timedelta(minutes=3)
):
    return copy_native_world(
        repository=repo,
        operation_id=operation,
        source_space_id="space:native-source",
        source_revision_id=original.published_revision_id,
        created_at=when,
        domain_contract=domain,
        semantic_profile=profile,
    )


def test_copy_preserves_graph_alias_and_verified_text_in_a_distinct_space():
    repo, domain, profile, source, admission, original = _source()
    before = repo.get_revision(source.space_id, original.published_revision_id).graph_payload
    copied = _copy(repo, domain, profile, original)
    assert copied.space_id != source.space_id
    after = repo.get_revision(copied.space_id, copied.revision_id).graph_payload
    assert after["entities"] == before["entities"]
    assert len(after["assertions"]) == len(before["assertions"]) == 2
    assert len(after["aliases"]) == 1
    assert after["aliases"][0]["alias_text"] == before["aliases"][0]["alias_text"]
    old_evidence = admission.bindings[0].evidence_ref_id
    new_evidence = after["evidence"][0]["evidence_ref_id"]
    assert new_evidence != old_evidence
    for assertion in after["assertions"]:
        assert assertion["metadata"]["evidence_ref_ids"] == [new_evidence]
        prior = next(
            a for a in before["assertions"] if a["assertion_id"] == assertion["assertion_id"]
        )
        assert assertion["value"] == prior["value"]
        assert assertion["metadata"]["temporal_scope"] == prior["metadata"]["temporal_scope"]
    assert after["aliases"][0]["evidence_ref_ids"] == [new_evidence]
    context = open_native_text_source_access_context(
        repository=repo,
        space_id=copied.space_id,
        revision_id=copied.revision_id,
        domain_contract=domain,
    )
    opened = open_admitted_native_text(context, new_evidence)
    assert opened.status == "available" and opened.body_text == BODY
    assert (
        repo.get_revision(source.space_id, original.published_revision_id).graph_payload == before
    )
    assert repo.get_head(source.space_id).head_revision_id == original.published_revision_id


def test_replay_returns_original_copy_without_overwriting_later_edits():
    repo, domain, profile, source, _, original = _source()
    one = _copy(repo, domain, profile, original)
    prior = repo.get_revision(one.space_id, one.revision_id)
    edited = _publish_validated_command(
        _command(
            one.space_id, prior, prior.graph_payload, "visitor:edit", NOW + timedelta(minutes=4)
        ),
        publication_id="visitor:edit",
        repository=repo,
    )
    assert _copy(repo, domain, profile, original) == one
    assert repo.get_head(one.space_id).head_revision_id == edited.published_revision_id
    two = _copy(repo, domain, profile, original, operation="session:two")
    assert two.space_id != one.space_id and two.space_id != source.space_id


def test_same_operation_with_different_binding_fails_without_changing_copy():
    repo, domain, profile, _, _, original = _source()
    copied = _copy(repo, domain, profile, original)
    with pytest.raises(KnowledgePublicationIdempotencyConflictError):
        _copy(repo, domain, profile, original, when=NOW + timedelta(minutes=5))
    assert repo.get_head(copied.space_id).head_revision_id == copied.revision_id


def test_completed_copy_survives_source_withdrawal_and_replays():
    repo, domain, profile, source, admission, original = _source()
    copied = _copy(repo, domain, profile, original)
    repo.withdraw_native_source(
        space_id=source.space_id,
        source_artifact_id=admission.source_artifact_id,
        source_revision_id=admission.source_revision_id,
    )
    assert _copy(repo, domain, profile, original) == copied
    graph = repo.get_revision(copied.space_id, copied.revision_id).graph_payload
    context = open_native_text_source_access_context(
        repository=repo,
        space_id=copied.space_id,
        revision_id=copied.revision_id,
        domain_contract=domain,
    )
    assert (
        open_admitted_native_text(context, graph["evidence"][0]["evidence_ref_id"]).body_text
        == BODY
    )


def test_unavailable_source_fails_before_allocating():
    repo, domain, profile, source, admission, original = _source()
    repo.withdraw_native_source(
        space_id=source.space_id,
        source_artifact_id=admission.source_artifact_id,
        source_revision_id=admission.source_revision_id,
    )
    with pytest.raises(NativeWorldCopyError, match="unavailable"):
        _copy(repo, domain, profile, original)
    assert repo.get_space_provisioning_receipt("native-world-copy:session:one") is None


def test_private_assertion_requires_authorized_audience_before_allocation():
    from dungeonmind.application.vnext.initialization import initialize_empty_knowledge_space
    from dungeonmind.infrastructure.memory.vnext_sources import (
        InMemoryNativeSourceEvidenceRepository,
    )
    from tests.unit.test_vnext_native_source_admission import _domain, _profile

    repo, domain, profile = (
        InMemoryNativeSourceEvidenceRepository(),
        _domain(visibility_labels=["test:private"]),
        _profile(),
    )
    genesis = initialize_empty_knowledge_space(
        repository=repo,
        space_id="space:native-source",
        initialization_id="init:native-source",
        created_at=NOW,
        domain_contract=domain,
        semantic_profile=profile,
    )
    repo, domain, profile, _, _, original = _source((repo, domain, profile, genesis))
    parent = repo.get_revision("space:native-source", original.published_revision_id)
    graph = parent.graph_payload
    graph["assertions"][0]["metadata"]["visibility"] = LabelsAnyVisibility(
        kind="labels_any", labels=["test:private"]
    ).model_dump(mode="json")
    private = _publish_validated_command(
        _command(
            "space:native-source", parent, graph, "fixture:private", NOW + timedelta(minutes=3)
        ),
        publication_id="fixture:private",
        repository=repo,
    )
    with pytest.raises(NativeWorldCopyError, match="authorized audience"):
        _copy(repo, domain, profile, private)
    assert repo.get_space_provisioning_receipt("native-world-copy:session:one") is None
    copied = copy_native_world(
        repository=repo,
        operation_id="session:one",
        source_space_id="space:native-source",
        source_revision_id=private.published_revision_id,
        created_at=NOW + timedelta(minutes=4),
        domain_contract=domain,
        semantic_profile=profile,
        audience_labels=["test:private"],
    )
    assert repo.get_revision(copied.space_id, copied.revision_id).graph_payload["assertions"][0][
        "metadata"
    ]["visibility"]["labels"] == ["test:private"]


def test_interrupted_source_admission_replays_without_duplicate_or_source_mutation(monkeypatch):
    from dungeonmind.application.vnext import world_copy

    repo, domain, profile, source, _, original = _source()
    real = world_copy.publish_native_text_source_evidence
    calls = 0

    def interrupt_once(**kwargs):
        nonlocal calls
        result = real(**kwargs)
        calls += 1
        if calls == 1:
            raise RuntimeError("lost response")
        return result

    monkeypatch.setattr(world_copy, "publish_native_text_source_evidence", interrupt_once)
    with pytest.raises(RuntimeError, match="lost response"):
        _copy(repo, domain, profile, original)
    copied = _copy(repo, domain, profile, original)
    assert (
        len(repo.get_revision(copied.space_id, copied.revision_id).graph_payload["evidence"]) == 1
    )
    assert repo.get_head(source.space_id).head_revision_id == original.published_revision_id
