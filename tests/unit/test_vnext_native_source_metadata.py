"""Metadata discovery is authorized navigation, never a body verification receipt."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from dungeonmind.application.vnext import (
    initialize_empty_knowledge_space,
    list_admitted_native_text_sources,
    open_admitted_native_text,
    open_native_text_source_access_context,
    publish_native_text_source_evidence,
)
from dungeonmind.application.vnext.errors import NativeTextSourceAccessIntegrityError
from dungeonmind.contracts.vnext.common import LabelsAnyVisibility
from dungeonmind.domain.errors import PersistenceIntegrityError, PersistenceUnavailableError
from tests.unit.test_vnext_native_source_admission import (
    NOW,
    _domain,
    _initialized,
    _request,
)


def source_case(*, hidden=False):
    repo, domain, profile, genesis = _initialized()
    if hidden:
        domain = _domain(visibility_labels=["test:gm"])
        repo, _, _, _ = _initialized()
        # A distinct source-only knowledge space with declared visibility.
        genesis = initialize_empty_knowledge_space(
            repository=repo,
            space_id="space:hidden",
            initialization_id="init:hidden",
            created_at=NOW,
            domain_contract=domain,
            semantic_profile=profile,
        )
    space = "space:hidden" if hidden else "space:native-source"
    request = _request(
        space_id=space,
        parent_revision_id=genesis.published_revision_id,
        visibility=LabelsAnyVisibility(kind="labels_any", labels=["test:gm"]) if hidden else None,
    )
    receipt = publish_native_text_source_evidence(
        repository=repo, request=request, domain_contract=domain, semantic_profile=profile
    )
    context = open_native_text_source_access_context(
        repository=repo,
        space_id=space,
        revision_id=receipt.published_revision_id,
        domain_contract=domain,
        audience_labels=["test:gm"] if hidden else [],
    )
    return repo, domain, profile, context, receipt


def test_source_only_metadata_is_complete_and_reads_no_body(monkeypatch):
    _, _, _, context, receipt = source_case()
    assert not context.parsed.entities_by_id and not context.parsed.assertions_by_id

    def forbidden(*args, **kwargs):
        pytest.fail("Metadata discovery attempted a body read")

    monkeypatch.setattr(type(context.source_view), "get_native_text_source", forbidden)
    result = list_admitted_native_text_sources(context)
    assert result.complete and len(result.sources) == 1
    assert (result.space_id, result.revision_id, result.source_authority_epoch) == (
        context.space_id,
        context.revision_id,
        context.source_view.epoch,
    )
    item = result.sources[0]
    assert item.source_artifact.source_artifact_id == receipt.source_artifact_id
    assert item.source_revision.source_revision_id == receipt.source_revision_id
    assert item.evidence_ref_ids == tuple(binding.evidence_ref_id for binding in receipt.bindings)
    assert not hasattr(item, "body_text")


def test_discovery_and_body_reader_share_visibility_and_copied_metadata():
    _, _, _, context, receipt = source_case(hidden=True)
    evidence_id = receipt.bindings[0].evidence_ref_id
    forbidden = replace(context, audience_labels=frozenset())
    assert list_admitted_native_text_sources(forbidden).sources == ()
    assert list_admitted_native_text_sources(forbidden).complete
    assert open_admitted_native_text(forbidden, evidence_id).status == "unavailable"
    metadata = list_admitted_native_text_sources(context).sources[0]
    metadata.source_artifact.status = "retracted"
    metadata.source_revision.content_sha256 = "0" * 64
    assert list_admitted_native_text_sources(context).sources[0].source_artifact.status == "active"
    assert open_admitted_native_text(context, evidence_id).status == "available"


def test_discovery_keeps_revision_membership_after_later_admission():
    repo, domain, profile, context, first = source_case()
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
    assert len(list_admitted_native_text_sources(context).sources) == 1
    fresh = open_native_text_source_access_context(
        repository=repo,
        space_id=context.space_id,
        revision_id=second.published_revision_id,
        domain_contract=domain,
    )
    assert len(list_admitted_native_text_sources(fresh).sources) == 2
    assert fresh.source_view.epoch > context.source_view.epoch


def snapshot_context(context, *, artifact=None, revision=None, failure=None):
    def snapshot(**kwargs):
        if failure:
            raise failure
        return SimpleNamespace(get_artifact=lambda _: artifact, get_revision=lambda _: revision)

    return replace(
        context,
        source_view=SimpleNamespace(
            epoch=context.source_view.epoch, get_provenance_snapshot=snapshot
        ),
    )


def test_missing_metadata_is_partial_not_a_complete_empty_catalogue():
    _, _, _, context, _ = source_case()
    result = list_admitted_native_text_sources(snapshot_context(context))
    assert not result.complete and result.sources == ()


@pytest.mark.parametrize(
    "failure", [PersistenceUnavailableError("offline"), PersistenceIntegrityError("corrupt")]
)
def test_storage_failures_do_not_become_complete_empty(failure):
    _, _, _, context, _ = source_case()
    with pytest.raises(type(failure)):
        list_admitted_native_text_sources(snapshot_context(context, failure=failure))


@pytest.mark.parametrize("field", ["artifact", "revision", "revision_artifact", "storage"])
def test_foreign_metadata_and_storage_substitutions_fail_closed(field):
    _, _, _, context, _ = source_case()
    item = list_admitted_native_text_sources(context).sources[0]
    artifact, revision = item.source_artifact, item.source_revision
    if field == "artifact":
        artifact = artifact.model_copy(update={"source_artifact_id": "other"})
    elif field == "revision":
        revision = revision.model_copy(update={"source_revision_id": "other"})
        artifact = artifact.model_copy(update={"current_revision_id": "other"})
    elif field == "revision_artifact":
        revision = revision.model_copy(update={"source_artifact_id": "other"})
    else:
        revision = revision.model_copy(update={"body_storage": "other"})
    with pytest.raises(NativeTextSourceAccessIntegrityError):
        list_admitted_native_text_sources(
            snapshot_context(context, artifact=artifact, revision=revision)
        )


@pytest.mark.parametrize("status", ["retracted", "superseded"])
def test_inactive_sources_are_not_discovered(status):
    _, _, _, context, _ = source_case()
    item = list_admitted_native_text_sources(context).sources[0]
    result = list_admitted_native_text_sources(
        snapshot_context(
            context,
            artifact=item.source_artifact.model_copy(update={"status": status}),
            revision=item.source_revision,
        )
    )
    assert result.complete and not result.sources


def test_source_less_revision_is_complete_empty():
    repo, domain, _, genesis = _initialized()
    context = open_native_text_source_access_context(
        repository=repo,
        space_id="space:native-source",
        revision_id=genesis.published_revision_id,
        domain_contract=domain,
    )
    result = list_admitted_native_text_sources(context)
    assert result.complete and not result.sources


def test_multiple_admitted_evidence_refs_group_one_source_without_a_result_cap():
    repo, domain, profile, genesis = _initialized()
    request = _request(parent_revision_id=genesis.published_revision_id)
    request = request.model_copy(
        update={
            "spans": [
                request.spans[0],
                request.spans[0].model_copy(update={"client_ref": "another-span"}),
            ]
        }
    )
    receipt = publish_native_text_source_evidence(
        repository=repo, request=request, domain_contract=domain, semantic_profile=profile
    )
    context = open_native_text_source_access_context(
        repository=repo,
        space_id=request.space_id,
        revision_id=receipt.published_revision_id,
        domain_contract=domain,
    )
    result = list_admitted_native_text_sources(context)
    assert len(result.sources) == 1
    assert result.sources[0].evidence_ref_ids == tuple(
        sorted(b.evidence_ref_id for b in receipt.bindings)
    )


@pytest.mark.parametrize(
    "field", ["can_open_source", "can_highlight_span", "source_revision_id", "source_span_ref_id"]
)
def test_ineligible_evidence_is_not_exposed_or_opened(field):
    from dungeonmind.application.vnext.frozen_json import FrozenDict

    _, _, _, context, receipt = source_case()
    evidence_id = receipt.bindings[0].evidence_ref_id
    evidence = context.parsed.get_evidence(evidence_id)
    changed = replace(evidence, **{field: False if field.startswith("can_") else None})
    context = replace(
        context, parsed=replace(context.parsed, evidence_by_id=FrozenDict({evidence_id: changed}))
    )
    assert list_admitted_native_text_sources(context).sources == ()
    assert open_admitted_native_text(context, evidence_id).status == "unavailable"


def test_undeclared_evidence_annotation_is_not_navigation_or_read_authority():
    from dungeonmind.application.vnext.frozen_json import FrozenDict
    from dungeonmind.application.vnext.records import ParsedDomainMetadataEntry

    _, _, _, context, receipt = source_case()
    evidence_id = receipt.bindings[0].evidence_ref_id
    evidence = context.parsed.get_evidence(evidence_id)
    changed = replace(
        evidence,
        domain_metadata=(
            ParsedDomainMetadataEntry(schema_term="test:undeclared", payload=FrozenDict({})),
        ),
    )
    context = replace(
        context, parsed=replace(context.parsed, evidence_by_id=FrozenDict({evidence_id: changed}))
    )
    assert list_admitted_native_text_sources(context).sources == ()
    assert open_admitted_native_text(context, evidence_id).status == "unavailable"


def test_undeclared_source_annotation_is_not_navigation_authority():
    from dungeonmind.contracts.vnext.common import DomainMetadataEntry

    _, _, _, context, _ = source_case()
    item = list_admitted_native_text_sources(context).sources[0]
    artifact = item.source_artifact.model_copy(
        update={
            "domain_metadata": [
                DomainMetadataEntry(schema_term="test:undeclared", payload={}),
            ]
        }
    )
    assert not list_admitted_native_text_sources(
        snapshot_context(context, artifact=artifact, revision=item.source_revision)
    ).sources
