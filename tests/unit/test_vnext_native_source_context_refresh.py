"""Fresh source authority must not rebuild or widen pinned Graph membership."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from dungeonmind.application.vnext import (
    open_admitted_native_text,
    open_native_text_source_access_context,
    publish_native_text_source_evidence,
    refresh_native_text_source_access_context,
)
from dungeonmind.application.vnext.errors import KnowledgeReadContextIntegrityError
from dungeonmind.contracts.vnext.common import LabelsAnyVisibility
from dungeonmind.domain.errors import PersistenceUnavailableError
from tests.unit.test_vnext_native_source_admission import _request
from tests.unit.test_vnext_native_source_metadata import source_case


def test_open_context_resolves_domain_from_one_pinned_revision(monkeypatch):
    repo, domain, _, original, first = source_case(hidden=True)
    get_revision = repo.get_revision
    calls = []

    def counted(space_id, revision_id):
        calls.append((space_id, revision_id))
        return get_revision(space_id, revision_id)

    def resolve(ref):
        assert ref.domain_id == domain.domain_id
        assert ref.domain_revision == domain.domain_revision
        return domain

    monkeypatch.setattr(repo, "get_revision", counted)
    context = open_native_text_source_access_context(
        repository=repo,
        space_id=original.space_id,
        revision_id=original.revision_id,
        domain_contract=resolve,
        audience_labels=("test:gm",),
    )
    assert calls == [(original.space_id, original.revision_id)]
    assert open_admitted_native_text(context, first.bindings[0].evidence_ref_id).status == "available"


def test_refresh_reuses_exact_parsed_revision_after_later_publication(monkeypatch):
    repo, domain, profile, context, first = source_case(hidden=True)
    second = publish_native_text_source_evidence(
        repository=repo,
        request=_request(
            space_id=context.space_id,
            admission_id="admit:later",
            parent_revision_id=first.published_revision_id,
            body="A later source.\n",
        ),
        domain_contract=domain,
        semantic_profile=profile,
    )

    def forbidden(*args, **kwargs):
        pytest.fail("Refresh reloaded immutable Graph membership")

    monkeypatch.setattr(repo, "get_revision", forbidden)
    refreshed = refresh_native_text_source_access_context(repository=repo, context=context)
    assert refreshed.parsed is context.parsed
    assert refreshed.revision_id == first.published_revision_id
    assert refreshed.audience_labels == context.audience_labels == frozenset({"test:gm"})
    assert refreshed.declared_visibility_labels is context.declared_visibility_labels
    assert refreshed.source_annotation_schemas is context.source_annotation_schemas
    assert refreshed.source_view is not context.source_view
    assert refreshed.source_view.epoch == second.source_authority_epoch
    assert refreshed.source_view.epoch > context.source_view.epoch
    assert (
        open_admitted_native_text(refreshed, first.bindings[0].evidence_ref_id).status
        == "available"
    )
    assert (
        open_admitted_native_text(refreshed, second.bindings[0].evidence_ref_id).status
        == "unavailable"
    )


@pytest.mark.parametrize("change", ["retracted", "new_revision", "private", "missing"])
def test_refresh_uses_new_authority_for_normal_admission(monkeypatch, change):
    repo, _, _, context, receipt = source_case()
    evidence_id = receipt.bindings[0].evidence_ref_id
    evidence = context.parsed.evidence_by_id[evidence_id]
    source = context.source_view.get_native_text_source(
        source_artifact_id=evidence.source_artifact_id,
        source_revision_id=evidence.source_revision_id,
        span_id=evidence.source_span_ref_id,
    )
    assert source is not None
    artifact = source.source_artifact
    if change == "retracted":
        artifact = artifact.model_copy(update={"status": "retracted"})
    elif change == "new_revision":
        artifact = artifact.model_copy(update={"current_revision_id": "revision:new"})
    elif change == "private":
        artifact = artifact.model_copy(
            update={"visibility": LabelsAnyVisibility(kind="labels_any", labels=["test:gm"])}
        )
    changed = None if change == "missing" else replace(source, source_artifact=artifact)
    new_view = SimpleNamespace(
        epoch=context.source_view.epoch + 1,
        get_native_text_source=lambda **kwargs: changed,
    )
    monkeypatch.setattr(repo, "open_native_source_view", lambda space: new_view)
    refreshed = refresh_native_text_source_access_context(repository=repo, context=context)
    assert open_admitted_native_text(context, evidence_id).status == "available"
    result = open_admitted_native_text(refreshed, evidence_id)
    assert result.status == "unavailable"
    assert result.body_text is None
    assert refreshed.parsed is context.parsed


@pytest.mark.parametrize("field", ["space_id", "revision_id"])
def test_refresh_rejects_context_identity_substitution(monkeypatch, field):
    repo, _, _, context, _ = source_case()

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid context reached source authority")

    monkeypatch.setattr(repo, "open_native_source_view", forbidden)
    with pytest.raises(KnowledgeReadContextIntegrityError, match="identity mismatch"):
        refresh_native_text_source_access_context(
            repository=repo, context=replace(context, **{field: "foreign"})
        )


def test_refresh_rejects_backwards_source_epoch(monkeypatch):
    repo, _, _, context, _ = source_case()
    monkeypatch.setattr(
        repo,
        "open_native_source_view",
        lambda _: SimpleNamespace(epoch=context.source_view.epoch - 1),
    )
    with pytest.raises(KnowledgeReadContextIntegrityError, match="epoch moved backwards"):
        refresh_native_text_source_access_context(repository=repo, context=context)


def test_refresh_preserves_storage_failure(monkeypatch):
    repo, _, _, context, _ = source_case()

    def offline(*args, **kwargs):
        raise PersistenceUnavailableError("offline")

    monkeypatch.setattr(repo, "open_native_source_view", offline)
    with pytest.raises(PersistenceUnavailableError, match="offline"):
        refresh_native_text_source_access_context(repository=repo, context=context)


def test_persisted_withdrawal_changes_source_epoch_without_graph_publication():
    repo, _, _, context, receipt = source_case()
    space_id = receipt.space_id
    evidence_id = receipt.bindings[0].evidence_ref_id
    identity = dict(
        space_id=space_id,
        source_artifact_id=receipt.source_artifact_id,
        source_revision_id=receipt.source_revision_id,
    )
    head = repo.get_head(space_id)
    events = repo.head_events(space_id)
    assert open_admitted_native_text(context, evidence_id).status == "available"
    with pytest.raises(ValueError):
        repo.withdraw_native_source(**{**identity, "space_id": "other"})
    epoch = repo.withdraw_native_source(**identity)
    assert epoch == context.source_view.epoch + 1
    assert repo.withdraw_native_source(**identity) == epoch
    refreshed = refresh_native_text_source_access_context(repository=repo, context=context)
    assert refreshed.source_view.epoch == epoch
    assert open_admitted_native_text(refreshed, evidence_id).status == "unavailable"
    assert open_admitted_native_text(context, evidence_id).status == "available"
    assert repo.get_head(space_id) == head
    assert repo.head_events(space_id) == events
