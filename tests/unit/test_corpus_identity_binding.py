"""Synthetic falsifiers for the reviewed corpus identity preflight."""

import pytest
from pydantic import ValidationError

from dungeonmind.contracts.corpus_identity_binding import (
    CorpusIdentityAuthoritySnapshotV1,
    CorpusIdentityKeyV1,
    ObservedHubIdentityAssertionV1,
    ReviewedCorpusIdentityBindingV1,
    validate_reviewed_corpus_identity_binding,
)

SHA = "a" * 64
ASSERTION_SHA = "b" * 64


def _binding(**changes: object) -> ReviewedCorpusIdentityBindingV1:
    data = dict(
        world_id="world:test", campaign_id="campaign:test",
        source_artifact_id="hub:test", source_revision_id="hub-rev:1",
        source_body_sha256=SHA, hub_assertion_id="assertion:1",
        hub_assertion_sha256=ASSERTION_SHA,
        identity_key=CorpusIdentityKeyV1(namespace="buddy", key_type="pc", value="hero-7"),
        asserted_target_id="pc:hero-7", asserted_target_kind="pc",
        target_node_id="pc:hero-7", target_node_kind="pc",
        expected_graph_head_revision_id="graph-rev:1",
    )
    data.update(changes)
    return ReviewedCorpusIdentityBindingV1(**data)


def _observed(
    binding: ReviewedCorpusIdentityBindingV1, **changes: object
) -> CorpusIdentityAuthoritySnapshotV1:
    data = dict(
        world_id=binding.world_id, campaign_id=binding.campaign_id,
        source_artifact_id=binding.source_artifact_id,
        current_source_revision_id=binding.source_revision_id,
        source_body_sha256=binding.source_body_sha256,
        hub_assertions=(ObservedHubIdentityAssertionV1(
            assertion_id=binding.hub_assertion_id,
            assertion_sha256=binding.hub_assertion_sha256,
            identity_key=binding.identity_key,
            asserted_target_id=binding.asserted_target_id,
            asserted_target_kind=binding.asserted_target_kind,
        ),),
        graph_head_revision_id=binding.expected_graph_head_revision_id,
        target_node_id=binding.target_node_id, target_node_kind=binding.target_node_kind,
    )
    data.update(changes)
    return CorpusIdentityAuthoritySnapshotV1(**data)


def test_exact_typed_binding_passes_preflight() -> None:
    binding = _binding()
    validate_reviewed_corpus_identity_binding(binding, _observed(binding))


@pytest.mark.parametrize(
    ("change", "value"),
    [
        ("world_id", "world:other"),
        ("campaign_id", "campaign:other"),
        ("source_artifact_id", "hub:other"),
        ("current_source_revision_id", "hub-rev:2"),
        ("source_body_sha256", "c" * 64),
        ("graph_head_revision_id", "graph-rev:2"),
        ("target_node_id", "pc:other"),
        ("target_node_kind", "npc"),
        ("hub_assertions", ()),
    ],
)
def test_stale_or_missing_authority_rejected(change: str, value: object) -> None:
    binding = _binding()
    with pytest.raises(ValueError):
        validate_reviewed_corpus_identity_binding(binding, _observed(binding, **{change: value}))


def test_ambiguous_typed_key_rejected() -> None:
    binding = _binding()
    first = _observed(binding).hub_assertions[0]
    second = first.model_copy(update={"assertion_id": "assertion:2"})
    with pytest.raises(ValueError, match="ambiguous"):
        validate_reviewed_corpus_identity_binding(
            binding, _observed(binding, hub_assertions=(first, second))
        )


def test_competing_key_and_node_bindings_rejected() -> None:
    binding = _binding()
    for accepted in (
        _binding(target_node_id="pc:other", asserted_target_id="pc:other"),
        _binding(identity_key=CorpusIdentityKeyV1(namespace="buddy", key_type="pc", value="other")),
    ):
        with pytest.raises(ValueError, match="already binds"):
            validate_reviewed_corpus_identity_binding(
                binding, _observed(binding, existing_bindings=(accepted,))
            )


def test_same_typed_key_cannot_split_c1_c2_world_identity() -> None:
    binding = _binding(campaign_id="campaign:c2")
    accepted_c1 = _binding(
        campaign_id="campaign:c1", target_node_id="pc:other", asserted_target_id="pc:other"
    )
    with pytest.raises(ValueError, match="typed identity key already binds"):
        validate_reviewed_corpus_identity_binding(
            binding, _observed(binding, existing_bindings=(accepted_c1,))
        )


def test_same_key_and_node_id_cannot_change_accepted_target_kind() -> None:
    binding = _binding()
    accepted = _binding(target_node_kind="npc", asserted_target_kind="npc")
    with pytest.raises(ValueError, match="node identity or kind"):
        validate_reviewed_corpus_identity_binding(
            binding, _observed(binding, existing_bindings=(accepted,))
        )


def test_inconsistent_accepted_assertion_target_fails_closed() -> None:
    binding = _binding()
    accepted = _binding(asserted_target_kind="npc")
    with pytest.raises(ValueError, match="inconsistent assertion target"):
        validate_reviewed_corpus_identity_binding(
            binding, _observed(binding, existing_bindings=(accepted,))
        )


def test_world_owned_hub_has_explicit_null_campaign_scope() -> None:
    binding = _binding(campaign_id=None)
    validate_reviewed_corpus_identity_binding(binding, _observed(binding))
    assert binding.model_dump()["campaign_id"] is None


def test_name_only_or_alias_payload_cannot_enter_contract() -> None:
    binding = _binding()
    with pytest.raises(ValidationError, match="Extra inputs"):
        ReviewedCorpusIdentityBindingV1.model_validate({
            **binding.model_dump(), "display_name": "Hero Seven", "alias": "H7"
        })


def test_hub_assertion_target_must_equal_existing_node() -> None:
    binding = _binding(asserted_target_id="pc:other")
    with pytest.raises(ValueError, match="hub assertion target"):
        validate_reviewed_corpus_identity_binding(binding, _observed(binding))
