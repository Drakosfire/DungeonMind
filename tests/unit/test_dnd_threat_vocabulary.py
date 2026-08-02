"""Catalog, profile, and digest proofs for the D&D Threat vocabulary."""

from __future__ import annotations

import json
import traceback
from pathlib import Path

import pytest
from pydantic import ValidationError

from dungeonmind.application.semantic_profiles import descriptor_sha256
from dungeonmind.contracts.semantic_profile import (
    SemanticProfileDescriptor,
    SemanticProfileRef,
)
from dungeonmind.domain.canonical import canonical_sha256, sha256_text
from dungeonmind.infrastructure.semantic_profiles import (
    FilesystemSemanticProfileRegistry,
)
from dungeonmind_dnd.application import threat_candidates
from dungeonmind_dnd.application.threat_candidates import (
    builtin_threat_vocabulary_ref,
    load_builtin_threat_vocabulary,
    vocabulary_sha256,
)
from dungeonmind_dnd.contracts.vocabulary import (
    DndSemanticVocabulary,
    DndVocabularyObjectKind,
    DndVocabularyPredicate,
    DndVocabularyRef,
)
from dungeonmind_dnd.domain.errors import DndVocabularyIntegrityError

REPO_ROOT = Path(__file__).resolve().parents[2]
V1_DESCRIPTOR_PATH = REPO_ROOT / "src" / "dungeonmind_dnd" / "profiles" / "dnd5e-v1.json"
V2_DESCRIPTOR_PATH = REPO_ROOT / "src" / "dungeonmind_dnd" / "profiles" / "dnd5e-v2.json"
CATALOG_PATH = (
    REPO_ROOT / "src" / "dungeonmind_dnd" / "vocabularies" / "threat-v1.json"
)
EXAMPLE_REGISTRY = REPO_ROOT / "examples" / "semantic_profiles" / "registry.json"

V1_DESCRIPTOR_DIGEST = "582851c0fc41897fff5a57a4fd6dd7fb7078b865315a30bc21552c82e7596967"
V1_DESCRIPTOR_BYTES_SHA256 = "3ad9e1b5b0affac9d87265dbff691199ed5bc011dc52069321370ee25954d45e"
V2_DESCRIPTOR_DIGEST = "57de5bc922503571d781f0de00d0a26b7aabcb3c363518e269f6c7a52a6c0086"
CATALOG_DIGEST = "0edaeee9dc6ccb0c507e79339ce74cbea7e3734bb42ae00b4833d02ac8ea6047"

EXPECTED_KINDS = ["dnd5e:creature", "dnd5e:location", "dnd5e:faction", "dnd5e:encounter"]
EXPECTED_DIRECTION = {
    "dnd5e:located_at": (
        ["dnd5e:creature", "dnd5e:encounter"],
        ["dnd5e:location"],
    ),
    "dnd5e:member_of": (["dnd5e:creature"], ["dnd5e:faction"]),
    "dnd5e:participates_in": (["dnd5e:creature", "dnd5e:faction"], ["dnd5e:encounter"]),
    "dnd5e:threatens": (
        ["dnd5e:creature", "dnd5e:faction", "dnd5e:encounter"],
        ["dnd5e:location", "dnd5e:faction", "dnd5e:creature"],
    ),
}


def _full_traceback(exc: BaseException) -> str:
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


def test_v1_descriptor_is_byte_for_byte_unchanged() -> None:
    raw = V1_DESCRIPTOR_PATH.read_text(encoding="utf-8")
    assert sha256_text(raw) == V1_DESCRIPTOR_BYTES_SHA256
    descriptor = SemanticProfileDescriptor.model_validate(json.loads(raw))
    assert descriptor.profile_revision == "dnd5e-profile-v1"
    assert descriptor_sha256(descriptor) == V1_DESCRIPTOR_DIGEST


def test_v2_descriptor_validates_and_digest_is_pinned() -> None:
    raw = V2_DESCRIPTOR_PATH.read_text(encoding="utf-8")
    descriptor = SemanticProfileDescriptor.model_validate(json.loads(raw))
    assert descriptor.profile_id == "dungeonmind.dnd5e"
    assert descriptor.profile_revision == "dnd5e-profile-v2"
    assert descriptor.term_namespaces == ["dnd5e"]
    assert descriptor_sha256(descriptor) == V2_DESCRIPTOR_DIGEST


def test_example_registry_retains_v1_and_adds_v2() -> None:
    registry = FilesystemSemanticProfileRegistry.from_config_path(EXAMPLE_REGISTRY)
    v1 = registry.get("dungeonmind.dnd5e", "dnd5e-profile-v1")
    v2 = registry.get("dungeonmind.dnd5e", "dnd5e-profile-v2")
    assert v1 is not None and descriptor_sha256(v1) == V1_DESCRIPTOR_DIGEST
    assert v2 is not None and descriptor_sha256(v2) == V2_DESCRIPTOR_DIGEST


def test_builtin_catalog_loads_with_exact_term_inventory() -> None:
    catalog = load_builtin_threat_vocabulary()
    assert catalog.schema_version == "dmdnd_semantic_vocabulary_v1"
    assert catalog.vocabulary_id == "dungeonmind.dnd5e.threat"
    assert catalog.vocabulary_revision == "threat-v1"
    assert [kind.term for kind in catalog.object_kinds] == EXPECTED_KINDS
    assert [p.term for p in catalog.predicates] == list(EXPECTED_DIRECTION)
    for predicate in catalog.predicates:
        subjects, objects = EXPECTED_DIRECTION[predicate.term]
        assert predicate.subject_kinds == subjects
        assert predicate.object_kinds == objects


def test_builtin_catalog_pins_exact_v2_profile_ref() -> None:
    catalog = load_builtin_threat_vocabulary()
    assert catalog.semantic_profile == SemanticProfileRef(
        profile_id="dungeonmind.dnd5e",
        profile_revision="dnd5e-profile-v2",
        descriptor_sha256=V2_DESCRIPTOR_DIGEST,
    )


def test_builtin_catalog_digest_and_ref_are_pinned() -> None:
    catalog = load_builtin_threat_vocabulary()
    assert vocabulary_sha256(catalog) == CATALOG_DIGEST
    assert builtin_threat_vocabulary_ref() == DndVocabularyRef(
        vocabulary_id="dungeonmind.dnd5e.threat",
        vocabulary_revision="threat-v1",
        catalog_sha256=CATALOG_DIGEST,
    )


def test_catalog_file_matches_model_digest() -> None:
    raw = CATALOG_PATH.read_text(encoding="utf-8")
    catalog = DndSemanticVocabulary.model_validate(json.loads(raw))
    assert vocabulary_sha256(catalog) == CATALOG_DIGEST
    # Key order in the JSON document must not affect the digest.
    shuffled = json.loads(raw)
    shuffled["predicates"] = list(reversed(shuffled["predicates"]))
    reordered = DndSemanticVocabulary.model_validate(shuffled)
    assert vocabulary_sha256(reordered) != CATALOG_DIGEST  # content changed
    assert canonical_sha256(catalog.model_dump(mode="json")) == CATALOG_DIGEST


def _catalog_payload(**overrides: object) -> dict:
    return {
        "schema_version": "dmdnd_semantic_vocabulary_v1",
        "vocabulary_id": "dungeonmind.dnd5e.threat",
        "vocabulary_revision": "threat-v1",
        "semantic_profile": {
            "schema_version": "dm_semantic_profile_ref_v1",
            "profile_id": "dungeonmind.dnd5e",
            "profile_revision": "dnd5e-profile-v2",
            "descriptor_sha256": V2_DESCRIPTOR_DIGEST,
        },
        "object_kinds": [
            {"term": "dnd5e:creature", "label": "Creature", "description": "A creature."}
        ],
        "predicates": [
            {
                "term": "dnd5e:located_at",
                "label": "Located at",
                "description": "Situated at.",
                "subject_kinds": ["dnd5e:creature"],
                "object_kinds": ["dnd5e:creature"],
            }
        ],
        **overrides,
    }


@pytest.mark.parametrize(
    "overrides",
    [
        # Duplicate kind term.
        {
            "object_kinds": [
                {"term": "dnd5e:creature", "label": "Creature", "description": "A."},
                {"term": "dnd5e:creature", "label": "Again", "description": "B."},
            ]
        },
        # Kind/predicate term collision (categories must be disjoint).
        {
            "predicates": [
                {
                    "term": "dnd5e:creature",
                    "label": "Creature",
                    "description": "C.",
                    "subject_kinds": ["dnd5e:creature"],
                    "object_kinds": ["dnd5e:creature"],
                }
            ]
        },
        # Predicate references a kind absent from the same catalog.
        {
            "predicates": [
                {
                    "term": "dnd5e:located_at",
                    "label": "Located at",
                    "description": "D.",
                    "subject_kinds": ["dnd5e:creature"],
                    "object_kinds": ["dnd5e:location"],
                }
            ]
        },
        # Unqualified term.
        {
            "object_kinds": [
                {"term": "creature", "label": "Creature", "description": "E."}
            ]
        },
        # Locator-like vocabulary identity.
        {"vocabulary_id": "dungeonmind/dnd5e"},
        {"vocabulary_revision": "latest"},
    ],
)
def test_malformed_catalogs_fail_closed(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        DndSemanticVocabulary.model_validate(_catalog_payload(**overrides))


def test_vocabulary_ref_rejects_locators_and_bad_digests() -> None:
    with pytest.raises(ValidationError):
        DndVocabularyRef(
            vocabulary_id="dungeonmind.dnd5e.threat",
            vocabulary_revision="threat-v1",
            catalog_sha256="not-a-digest",
        )
    with pytest.raises(ValidationError):
        DndVocabularyRef(
            vocabulary_id="dungeonmind.dnd5e.threat",
            vocabulary_revision="https://example.com/threat",
            catalog_sha256=CATALOG_DIGEST,
        )


def _tamper_resource(
    monkeypatch: pytest.MonkeyPatch,
    *,
    directory: str,
    name: str,
    replacement: str,
) -> None:
    real_read = threat_candidates._read_resource_text

    def _fake(directory_arg: str, name_arg: str) -> str:
        if directory_arg == directory and name_arg == name:
            return replacement
        return real_read(directory_arg, name_arg)

    monkeypatch.setattr(threat_candidates, "_read_resource_text", _fake)


def test_catalog_with_wrong_profile_digest_fails_integrity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    payload["semantic_profile"]["descriptor_sha256"] = "0" * 64
    _tamper_resource(
        monkeypatch,
        directory="vocabularies",
        name="threat-v1.json",
        replacement=json.dumps(payload),
    )
    with pytest.raises(DndVocabularyIntegrityError) as exc_info:
        load_builtin_threat_vocabulary()
    assert exc_info.value.code == "dnd_vocabulary_integrity_error"
    assert "digest" in str(exc_info.value)


def test_catalog_with_foreign_namespace_term_fails_integrity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    payload["object_kinds"].append(
        {"term": "generic:creature", "label": "Creature", "description": "Foreign."}
    )
    _tamper_resource(
        monkeypatch,
        directory="vocabularies",
        name="threat-v1.json",
        replacement=json.dumps(payload),
    )
    with pytest.raises(DndVocabularyIntegrityError) as exc_info:
        load_builtin_threat_vocabulary()
    assert "namespace" in str(exc_info.value)
    assert "generic:creature" in str(exc_info.value.details)


def test_catalog_with_profile_identity_drift_fails_integrity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    payload["semantic_profile"]["profile_revision"] = "dnd5e-profile-v1"
    _tamper_resource(
        monkeypatch,
        directory="vocabularies",
        name="threat-v1.json",
        replacement=json.dumps(payload),
    )
    with pytest.raises(DndVocabularyIntegrityError):
        load_builtin_threat_vocabulary()


def test_missing_catalog_fails_without_path_leak(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    local_path = str(tmp_path / "private" / "threat-v1.json")

    def _raise(directory: str, name: str) -> str:
        raise FileNotFoundError(f"No such file or directory: {local_path!r}")

    monkeypatch.setattr(threat_candidates, "_read_resource_text", _raise)
    with pytest.raises(DndVocabularyIntegrityError) as exc_info:
        load_builtin_threat_vocabulary()
    exc = exc_info.value
    assert exc.details == {"reason": "FileNotFoundError"}
    blob = _full_traceback(exc)
    assert local_path not in blob
    assert str(tmp_path) not in blob
    assert exc.__cause__ is None
    assert exc.__suppress_context__ is True


def test_malformed_catalog_json_suppresses_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _tamper_resource(
        monkeypatch,
        directory="vocabularies",
        name="threat-v1.json",
        replacement="{not json",
    )
    with pytest.raises(DndVocabularyIntegrityError) as exc_info:
        load_builtin_threat_vocabulary()
    exc = exc_info.value
    assert "not valid JSON" in str(exc)
    assert "{not json" not in _full_traceback(exc)
    assert exc.__cause__ is None
    assert exc.__suppress_context__ is True


def test_tampered_v2_descriptor_fails_integrity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = json.loads(V2_DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    payload["term_namespaces"] = ["dnd5e", "other"]
    _tamper_resource(
        monkeypatch,
        directory="profiles",
        name="dnd5e-v2.json",
        replacement=json.dumps(payload),
    )
    with pytest.raises(DndVocabularyIntegrityError):
        load_builtin_threat_vocabulary()


def test_catalog_term_shape_helpers() -> None:
    kind = DndVocabularyObjectKind(
        term="dnd5e:creature", label="Creature", description="A creature."
    )
    assert kind.term == "dnd5e:creature"
    with pytest.raises(ValidationError):
        DndVocabularyPredicate(
            term="dnd5e:located_at",
            label="Located at",
            description="Situated.",
            subject_kinds=[],
            object_kinds=["dnd5e:location"],
        )
