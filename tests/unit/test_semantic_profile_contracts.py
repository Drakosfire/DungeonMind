"""Contract validation and digest stability for semantic profiles."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from dungeonmind.application.semantic_profiles import descriptor_sha256
from dungeonmind.contracts.semantic_profile import (
    SemanticProfileDescriptor,
    SemanticProfileRef,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "semantic_profiles"
DND_DESCRIPTOR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "dungeonmind_dnd"
    / "profiles"
    / "dnd5e-v1.json"
)

NARRATIVE_DIGEST = "95edd343644e7a8dad7416d0002e6788c3782108f558f9b326550b4f2205ee78"
DND5E_DIGEST = "582851c0fc41897fff5a57a4fd6dd7fb7078b865315a30bc21552c82e7596967"


def test_ref_accepts_pinned_identity() -> None:
    ref = SemanticProfileRef(
        profile_id="test.narrative",
        profile_revision="narrative-profile-v1",
        descriptor_sha256=NARRATIVE_DIGEST,
    )
    assert ref.schema_version == "dm_semantic_profile_ref_v1"
    assert ref.descriptor_sha256 == NARRATIVE_DIGEST


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "profile_id": "has space",
            "profile_revision": "narrative-profile-v1",
            "descriptor_sha256": NARRATIVE_DIGEST,
        },
        {
            "profile_id": "path/like",
            "profile_revision": "narrative-profile-v1",
            "descriptor_sha256": NARRATIVE_DIGEST,
        },
        {
            "profile_id": "https://example.com/profile",
            "profile_revision": "narrative-profile-v1",
            "descriptor_sha256": NARRATIVE_DIGEST,
        },
        {
            "profile_id": "test.narrative",
            "profile_revision": "latest",
            "descriptor_sha256": NARRATIVE_DIGEST,
        },
        {
            "profile_id": "test.narrative",
            "profile_revision": "narrative-profile-v1",
            "descriptor_sha256": "not-a-digest",
        },
        {
            "profile_id": "Test.Narrative",
            "profile_revision": "narrative-profile-v1",
            "descriptor_sha256": NARRATIVE_DIGEST,
        },
    ],
)
def test_ref_rejects_locator_like_or_malformed(kwargs: dict) -> None:
    with pytest.raises(ValidationError):
        SemanticProfileRef.model_validate(kwargs)


def test_descriptor_requires_unique_lowercase_namespaces() -> None:
    descriptor = SemanticProfileDescriptor(
        profile_id="test.narrative",
        profile_revision="narrative-profile-v1",
        term_namespaces=["narrative"],
    )
    assert descriptor.term_namespaces == ["narrative"]
    with pytest.raises(ValidationError):
        SemanticProfileDescriptor(
            profile_id="test.narrative",
            profile_revision="narrative-profile-v1",
            term_namespaces=["narrative", "narrative"],
        )
    with pytest.raises(ValidationError):
        SemanticProfileDescriptor(
            profile_id="test.narrative",
            profile_revision="narrative-profile-v1",
            term_namespaces=["bad:ns"],
        )


def test_descriptor_digest_stability_for_fixtures() -> None:
    narrative = SemanticProfileDescriptor.model_validate(
        json.loads((FIXTURES / "test-narrative-v1.json").read_text(encoding="utf-8"))
    )
    dnd = SemanticProfileDescriptor.model_validate(
        json.loads(DND_DESCRIPTOR.read_text(encoding="utf-8"))
    )
    assert descriptor_sha256(narrative) == NARRATIVE_DIGEST
    assert descriptor_sha256(dnd) == DND5E_DIGEST
    # Key order must not affect digest.
    reshuffled = {
        "term_namespaces": ["narrative"],
        "profile_revision": "narrative-profile-v1",
        "schema_version": "dm_semantic_profile_v1",
        "profile_id": "test.narrative",
    }
    assert descriptor_sha256(SemanticProfileDescriptor.model_validate(reshuffled)) == (
        NARRATIVE_DIGEST
    )
