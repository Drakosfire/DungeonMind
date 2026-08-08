"""Parse, admission, and historical-lock proofs for ``dm_union_graph_v4``.

Every fixture here uses the synthetic ``test`` term namespace. The v4 proof
must not depend on D&D (or any other game system's) meaning, so the payload
carries no game-system vocabulary and a leak sentinel asserts as much.
"""

from __future__ import annotations

import copy
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from dungeonmind.application.graph_scope import project_scoped_snapshot
from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V1,
    GRAPH_SCHEMA_V2,
    GRAPH_SCHEMA_V3,
    GRAPH_SCHEMA_V4,
    UnionGraphV1SnapshotReader,
    UnionGraphV2SnapshotReader,
    UnionGraphV3SnapshotReader,
    VersionedUnionGraphSnapshotReader,
    collect_one_hop_object_ids,
)
from dungeonmind.application.graph_snapshot_v4 import UnionGraphV4SnapshotReader
from dungeonmind.application.semantic_profiles import descriptor_sha256
from dungeonmind.contracts.evidence import (
    SourceArtifact,
    SourceDomain,
    SourceRevision,
    SourceStatus,
)
from dungeonmind.contracts.knowledge_assertion import (
    EpistemicKindV2,
    KnowledgeAssertionMetadataV1,
    TemporalScopeKind,
    TemporalScopeRefV1,
)
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor
from dungeonmind.contracts.vocabulary import CanonState, EpistemicKind, Visibility
from dungeonmind.domain.errors import (
    PersistenceIntegrityError,
    SemanticProfileIntegrityError,
    SemanticProfileNotFoundError,
    SemanticTermValidationError,
)
from dungeonmind.infrastructure.memory import InMemorySourceRepository
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry

FIXED_NOW = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
WORLD_ID = "world:assertion-scoped-v4"
CAMPAIGN_ID = "camp:assertion-scoped-v4"
OTHER_CAMPAIGN_ID = "camp:parallel-table"

DESCRIPTOR_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "semantic_profiles"
    / "test-kernel-v1.json"
)

GM_ALIAS_EVIDENCE_GATED = "The Hollow Pen"
GM_ALIAS_SCOPE_GATED = "Pen of the Low Ward"
PLAYER_ALIAS = "Quill the Scribe"
HIDDEN_OBJECT_ALIAS = "Quiet One"


def _descriptor() -> SemanticProfileDescriptor:
    return SemanticProfileDescriptor.model_validate(
        json.loads(DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    )


def _registry() -> StaticSemanticProfileRegistry:
    return StaticSemanticProfileRegistry([_descriptor()])


def _reader() -> UnionGraphV4SnapshotReader:
    return UnionGraphV4SnapshotReader(_registry())


def _profile_ref() -> dict[str, Any]:
    descriptor = _descriptor()
    return {
        "schema_version": "dm_semantic_profile_ref_v1",
        "profile_id": descriptor.profile_id,
        "profile_revision": descriptor.profile_revision,
        "descriptor_sha256": descriptor_sha256(descriptor),
    }


def _meta(
    assertion_id: str,
    *,
    campaign_scope: str | None = CAMPAIGN_ID,
    visibility: str = "player",
    evidence: tuple[str, ...] = ("ev:player",),
    epistemic_kind: str = "asserted",
    canon_state: str = "canonical",
    session_refs: tuple[str, ...] = (),
    temporal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "assertion_id": assertion_id,
        "campaign_scope": campaign_scope,
        "visibility": visibility,
        "epistemic_kind": epistemic_kind,
        "canon_state": canon_state,
        "evidence_ref_ids": list(evidence),
        "session_refs": list(session_refs),
        "temporal_scope": temporal if temporal is not None else {"kind": "unknown"},
    }


def _evidence_row(evidence_ref_id: str, source_artifact_id: str) -> dict[str, Any]:
    return {
        "evidence_ref_id": evidence_ref_id,
        "source_artifact_id": source_artifact_id,
        "source_revision_id": f"srcrev:{source_artifact_id.removeprefix('src:')}-v1",
        "source_domain": "worldbuilding",
        "evidence_role": "support",
    }


def _v4_payload() -> dict[str, Any]:
    """A five-object payload exercising every assertion family and gate."""
    payload: dict[str, Any] = {
        "world_id": WORLD_ID,
        "semantic_profile": _profile_ref(),
        "objects": [
            {
                "object_id": "obj:person-quill",
                "kind": "test:person",
                "label": "Quill",
                "assertion_metadata": _meta(
                    "asrt:quill-exists", session_refs=("ses:0007",)
                ),
                "aliases": [
                    {
                        "value": PLAYER_ALIAS,
                        "assertion_metadata": _meta("asrt:quill-alias-public"),
                    },
                    {
                        # Hidden by its evidence chain (GM-only source).
                        "value": GM_ALIAS_EVIDENCE_GATED,
                        "assertion_metadata": _meta(
                            "asrt:quill-alias-secret",
                            visibility="gm",
                            evidence=("ev:gm",),
                        ),
                    },
                    {
                        # Hidden by its own assertion visibility, not evidence.
                        "value": GM_ALIAS_SCOPE_GATED,
                        "assertion_metadata": _meta(
                            "asrt:quill-alias-gated", visibility="gm"
                        ),
                    },
                ],
                "summary": {
                    "value": "a public archivist of the low ward",
                    "assertion_metadata": _meta("asrt:quill-summary"),
                },
                "properties": [
                    {
                        "property_term": "test:role",
                        "value": "archivist",
                        "assertion_metadata": _meta("asrt:quill-role-open"),
                    },
                    {
                        # Same property_term as above: no implicit winner.
                        "property_term": "test:role",
                        "value": "informant",
                        "assertion_metadata": _meta(
                            "asrt:quill-role-hidden", visibility="gm"
                        ),
                    },
                    {
                        "property_term": "test:tally",
                        "value": 3,
                        "assertion_metadata": _meta("asrt:quill-tally"),
                    },
                ],
            },
            {
                "object_id": "obj:place-low-ward",
                "kind": "test:place",
                "label": "Low Ward",
                "assertion_metadata": _meta(
                    "asrt:ward-exists", temporal={"kind": "world_timeless"}
                ),
                "aliases": [],
                "summary": None,
                "properties": [],
            },
            {
                # Existence hidden from players by assertion visibility alone;
                # its own alias/property are player-visible and must vanish too.
                "object_id": "obj:person-shade",
                "kind": "test:person",
                "label": "Shade",
                "assertion_metadata": _meta("asrt:shade-exists", visibility="gm"),
                "aliases": [
                    {
                        "value": HIDDEN_OBJECT_ALIAS,
                        "assertion_metadata": _meta("asrt:shade-alias"),
                    }
                ],
                "summary": None,
                "properties": [
                    {
                        "property_term": "test:role",
                        "value": "watcher",
                        "assertion_metadata": _meta("asrt:shade-role"),
                    }
                ],
            },
            {
                # Another campaign's knowledge. World-scoped evidence, so only
                # campaign_scope can be responsible for hiding it.
                "object_id": "obj:person-foreign",
                "kind": "test:person",
                "label": "Foreign Contact",
                "assertion_metadata": _meta(
                    "asrt:foreign-exists",
                    campaign_scope=OTHER_CAMPAIGN_ID,
                    evidence=("ev:world",),
                ),
                "aliases": [],
                "summary": None,
                "properties": [],
            },
            {
                "object_id": "obj:place-void",
                "kind": "test:place",
                "label": "The Void",
                "assertion_metadata": _meta(
                    "asrt:void-exists",
                    campaign_scope=None,
                    evidence=("ev:world",),
                    temporal={"kind": "world_timeless"},
                ),
                "aliases": [],
                "summary": None,
                "properties": [],
            },
        ],
        "relationships": [
            {
                "relationship_id": "rel:quill-in-ward",
                "source_object_id": "obj:person-quill",
                "target_object_id": "obj:place-low-ward",
                "predicate": "test:located_in",
                "assertion_metadata": _meta(
                    "asrt:rel-quill-ward",
                    temporal={
                        "kind": "fictional_time_ref",
                        "fictional_time_ref": "ftime:anchor-first-light",
                    },
                ),
            },
            {
                # Both endpoints are player-visible; only the relationship
                # assertion's visibility hides this edge.
                "relationship_id": "rel:quill-secret-tie",
                "source_object_id": "obj:person-quill",
                "target_object_id": "obj:place-low-ward",
                "predicate": "test:allied_with",
                "assertion_metadata": _meta(
                    "asrt:rel-quill-secret", visibility="gm"
                ),
            },
            {
                "relationship_id": "rel:shade-in-ward",
                "source_object_id": "obj:person-shade",
                "target_object_id": "obj:place-low-ward",
                "predicate": "test:located_in",
                "assertion_metadata": _meta("asrt:rel-shade-ward"),
            },
        ],
        "evidence_refs": [
            _evidence_row("ev:player", "src:player-notes"),
            _evidence_row("ev:gm", "src:gm-notes"),
            _evidence_row("ev:world", "src:world-notes"),
        ],
    }
    return copy.deepcopy(payload)


def _sources() -> InMemorySourceRepository:
    sources = InMemorySourceRepository()
    specs = (
        ("src:player-notes", CAMPAIGN_ID, Visibility.PLAYER),
        ("src:gm-notes", CAMPAIGN_ID, Visibility.GM),
        ("src:world-notes", None, Visibility.PLAYER),
    )
    for source_artifact_id, campaign_id, visibility in specs:
        revision_id = f"srcrev:{source_artifact_id.removeprefix('src:')}-v1"
        sources.put_artifact(
            SourceArtifact(
                source_artifact_id=source_artifact_id,
                source_domain=SourceDomain.WORLDBUILDING,
                world_id=WORLD_ID,
                campaign_id=campaign_id,
                current_revision_id=revision_id,
                authority="primary",
                visibility=visibility,
                status=SourceStatus.ACTIVE,
                created_at=FIXED_NOW,
            )
        )
        sources.put_revision(
            SourceRevision(
                source_revision_id=revision_id,
                source_artifact_id=source_artifact_id,
                content_sha256="c" * 64,
                body_storage="external",
                locator=f"fixture://v4/{source_artifact_id}",
                created_at=FIXED_NOW,
            )
        )
    return sources


def _parse(payload: dict[str, Any] | None = None):
    return _reader().parse(
        graph_schema=GRAPH_SCHEMA_V4,
        graph_payload=payload if payload is not None else _v4_payload(),
    )


def _scoped(
    *,
    admissibility: Admissibility = Admissibility.PLAYER,
    campaign_id: str | None = CAMPAIGN_ID,
    payload: dict[str, Any] | None = None,
):
    return project_scoped_snapshot(
        _parse(payload),
        sources=_sources(),
        world_id=WORLD_ID,
        campaign_id=campaign_id,
        admissibility=admissibility,
    )


def _existence_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    return payload["objects"][0]["assertion_metadata"]


# --------------------------------------------------------------------------
# Parse: shape, terms, and profile pinning
# --------------------------------------------------------------------------


def test_v4_parse_admits_every_assertion_family() -> None:
    snapshot = _parse()
    assert snapshot.world_id == WORLD_ID
    assert snapshot.graph_schema == GRAPH_SCHEMA_V4
    assert set(snapshot.objects) == {
        "obj:person-quill",
        "obj:place-low-ward",
        "obj:person-shade",
        "obj:person-foreign",
        "obj:place-void",
    }
    quill = snapshot.objects["obj:person-quill"]
    assert quill.object_field_schema == "v4"
    assert quill.kind == "test:person"
    assert quill.existence_assertion_metadata is not None
    assert quill.existence_assertion_metadata.assertion_id == "asrt:quill-exists"
    assert quill.aliases == [
        PLAYER_ALIAS,
        GM_ALIAS_EVIDENCE_GATED,
        GM_ALIAS_SCOPE_GATED,
    ]
    assert quill.summary == "a public archivist of the low ward"
    assert [item.assertion_id for item in quill.admitted_property_assertions] == [
        "asrt:quill-role-open",
        "asrt:quill-role-hidden",
        "asrt:quill-tally",
    ]
    assert set(snapshot.relationships) == {
        "rel:quill-in-ward",
        "rel:quill-secret-tie",
        "rel:shade-in-ward",
    }
    edge = snapshot.relationships["rel:quill-in-ward"]
    assert edge.subject_object_id == "obj:person-quill"
    assert edge.object_object_id == "obj:place-low-ward"
    assert edge.assertion_metadata is not None
    assert edge.assertion_metadata.assertion_id == "asrt:rel-quill-ward"


def test_v4_parse_pins_the_semantic_profile() -> None:
    snapshot = _parse()
    assert snapshot.semantic_profile_ref is not None
    assert snapshot.semantic_profile_ref.profile_id == "test.kernel"
    assert snapshot.semantic_profile_descriptor is not None
    assert snapshot.semantic_profile_descriptor.term_namespaces == ["test"]


def test_v4_proof_fixture_carries_no_game_system_vocabulary() -> None:
    serialized = json.dumps(_v4_payload()).casefold()
    for sentinel in ("dnd", "dnd5e", "creature", "statblock", "spell", "monster"):
        assert sentinel not in serialized


def test_v4_property_assertions_have_no_implicit_winner() -> None:
    quill = _parse().objects["obj:person-quill"]
    roles = [
        item
        for item in quill.admitted_property_assertions
        if item.property_term == "test:role"
    ]
    assert [item.value for item in roles] == ["archivist", "informant"]


def test_v4_versioned_reader_dispatches_v4() -> None:
    reader = VersionedUnionGraphSnapshotReader(profile_registry=_registry())
    snapshot = reader.parse(graph_schema=GRAPH_SCHEMA_V4, graph_payload=_v4_payload())
    assert snapshot.graph_schema == GRAPH_SCHEMA_V4


def test_v4_requires_semantic_profile() -> None:
    payload = _v4_payload()
    del payload["semantic_profile"]
    with pytest.raises(PersistenceIntegrityError, match="requires semantic_profile"):
        _parse(payload)


def test_v4_fails_closed_without_a_configured_registry() -> None:
    reader = VersionedUnionGraphSnapshotReader()
    with pytest.raises(SemanticProfileNotFoundError):
        reader.parse(graph_schema=GRAPH_SCHEMA_V4, graph_payload=_v4_payload())


def test_v4_rejects_profile_digest_mismatch() -> None:
    payload = _v4_payload()
    payload["semantic_profile"]["descriptor_sha256"] = "0" * 64
    with pytest.raises(SemanticProfileIntegrityError):
        _parse(payload)


def test_v4_rejects_unadmitted_namespace() -> None:
    payload = _v4_payload()
    payload["objects"][0]["kind"] = "dnd5e:creature"
    with pytest.raises(SemanticTermValidationError):
        _parse(payload)


@pytest.mark.parametrize(
    ("field_path", "bad_term"),
    [
        pytest.param(("objects", 0, "kind"), "person", id="kind"),
        pytest.param(
            ("relationships", 0, "predicate"), "located_in", id="predicate"
        ),
        pytest.param(
            ("objects", 0, "properties", 0, "property_term"), "role", id="property_term"
        ),
    ],
)
def test_v4_rejects_unqualified_terms(
    field_path: tuple[Any, ...], bad_term: str
) -> None:
    payload = _v4_payload()
    target: Any = payload
    for key in field_path[:-1]:
        target = target[key]
    target[field_path[-1]] = bad_term
    with pytest.raises(SemanticTermValidationError):
        _parse(payload)


# --------------------------------------------------------------------------
# Parse: fail-closed assertion metadata
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param({"pop": "assertion_id"}, id="assertion_id_missing"),
        pytest.param({"set": ("assertion_id", "  ")}, id="assertion_id_blank"),
        pytest.param({"pop": "campaign_scope"}, id="campaign_scope_missing"),
        pytest.param({"set": ("campaign_scope", "")}, id="campaign_scope_blank"),
        pytest.param({"set": ("campaign_scope", "   ")}, id="campaign_scope_spaces"),
        pytest.param({"pop": "visibility"}, id="visibility_missing"),
        pytest.param({"set": ("visibility", "everyone")}, id="visibility_unknown"),
        pytest.param({"pop": "epistemic_kind"}, id="epistemic_kind_missing"),
        pytest.param({"set": ("epistemic_kind", "vibes")}, id="epistemic_kind_unknown"),
        pytest.param({"pop": "canon_state"}, id="canon_state_missing"),
        pytest.param({"set": ("canon_state", "maybe")}, id="canon_state_unknown"),
        pytest.param({"pop": "evidence_ref_ids"}, id="evidence_missing"),
        pytest.param({"set": ("evidence_ref_ids", [])}, id="evidence_empty"),
        pytest.param({"set": ("evidence_ref_ids", ["ev:nope"])}, id="evidence_dangling"),
        pytest.param(
            {"set": ("evidence_ref_ids", ["ev:player", "ev:player"])},
            id="evidence_duplicate",
        ),
        pytest.param({"pop": "session_refs"}, id="session_refs_missing"),
        pytest.param({"set": ("session_refs", [" "])}, id="session_ref_blank"),
        pytest.param({"pop": "temporal_scope"}, id="temporal_scope_missing"),
        pytest.param({"set": ("who", "me")}, id="unknown_metadata_key"),
    ],
)
def test_v4_metadata_fails_closed(mutation: dict[str, Any]) -> None:
    payload = _v4_payload()
    metadata = _existence_metadata(payload)
    if "pop" in mutation:
        metadata.pop(mutation["pop"])
    else:
        key, value = mutation["set"]
        metadata[key] = value
    with pytest.raises(PersistenceIntegrityError):
        _parse(payload)


def test_v4_accepts_null_campaign_scope_as_world_universal() -> None:
    void = _parse().objects["obj:place-void"]
    assert void.existence_assertion_metadata is not None
    assert void.existence_assertion_metadata.campaign_scope is None


@pytest.mark.parametrize(
    "epistemic_kind",
    ["asserted", "inferred", "speculative", "fact", "source_derived_candidate"],
)
def test_v4_accepts_the_full_versioned_epistemic_vocabulary(
    epistemic_kind: str,
) -> None:
    payload = _v4_payload()
    _existence_metadata(payload)["epistemic_kind"] = epistemic_kind
    metadata = _parse(payload).objects["obj:person-quill"].existence_assertion_metadata
    assert metadata is not None
    assert metadata.epistemic_kind is EpistemicKindV2(epistemic_kind)


def test_versioned_epistemic_vocabulary_does_not_collapse_into_history() -> None:
    # The historical enum is untouched, and the v2 vocabulary never equates
    # fact with asserted or source_derived_candidate with inferred.
    assert [member.value for member in EpistemicKind] == [
        "asserted",
        "inferred",
        "speculative",
    ]
    assert EpistemicKindV2.FACT is not EpistemicKindV2.ASSERTED
    assert EpistemicKindV2.FACT.value != EpistemicKindV2.ASSERTED.value
    assert EpistemicKindV2.SOURCE_DERIVED_CANDIDATE is not EpistemicKindV2.INFERRED
    assert (
        EpistemicKindV2.SOURCE_DERIVED_CANDIDATE.value
        != EpistemicKindV2.INFERRED.value
    )


# --------------------------------------------------------------------------
# Parse: temporal scope rules
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "temporal",
    [
        pytest.param({"kind": "fictional_time_ref"}, id="ref_kind_without_ref"),
        pytest.param(
            {"kind": "fictional_time_ref", "fictional_time_ref": "  "},
            id="ref_kind_blank_ref",
        ),
        pytest.param(
            {"kind": "unknown", "fictional_time_ref": "ftime:anchor"},
            id="unknown_with_ref",
        ),
        pytest.param(
            {"kind": "world_timeless", "fictional_time_ref": "ftime:anchor"},
            id="timeless_with_ref",
        ),
        pytest.param({"kind": "someday"}, id="unknown_kind"),
        pytest.param({}, id="kind_missing"),
    ],
)
def test_v4_temporal_scope_fails_closed(temporal: dict[str, Any]) -> None:
    payload = _v4_payload()
    _existence_metadata(payload)["temporal_scope"] = temporal
    with pytest.raises(PersistenceIntegrityError):
        _parse(payload)


def test_v4_unknown_temporal_scope_is_not_world_timeless() -> None:
    snapshot = _parse()
    quill = snapshot.objects["obj:person-quill"].existence_assertion_metadata
    ward = snapshot.objects["obj:place-low-ward"].existence_assertion_metadata
    assert quill is not None
    assert ward is not None
    assert quill.temporal_scope.kind is TemporalScopeKind.UNKNOWN
    assert ward.temporal_scope.kind is TemporalScopeKind.WORLD_TIMELESS
    assert quill.temporal_scope.kind is not ward.temporal_scope.kind
    assert TemporalScopeKind.UNKNOWN.value != TemporalScopeKind.WORLD_TIMELESS.value


def test_v4_session_refs_never_derive_temporal_scope() -> None:
    quill = _parse().objects["obj:person-quill"].existence_assertion_metadata
    assert quill is not None
    assert quill.session_refs == ["ses:0007"]
    assert quill.temporal_scope.kind is TemporalScopeKind.UNKNOWN
    assert quill.temporal_scope.fictional_time_ref is None


def test_v4_fictional_time_ref_is_an_opaque_string() -> None:
    edge = _parse().relationships["rel:quill-in-ward"]
    assert edge.assertion_metadata is not None
    temporal = edge.assertion_metadata.temporal_scope
    assert temporal.kind is TemporalScopeKind.FICTIONAL_TIME_REF
    assert temporal.fictional_time_ref == "ftime:anchor-first-light"


# --------------------------------------------------------------------------
# Parse: structural integrity
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("endpoint", "match"),
    [
        pytest.param("source_object_id", "dangling relationship subject", id="source"),
        pytest.param("target_object_id", "dangling relationship object", id="target"),
    ],
)
def test_v4_rejects_missing_relationship_endpoints(endpoint: str, match: str) -> None:
    payload = _v4_payload()
    payload["relationships"][0][endpoint] = "obj:absent"
    with pytest.raises(PersistenceIntegrityError, match=match):
        _parse(payload)


def test_v4_rejects_duplicate_object_id() -> None:
    payload = _v4_payload()
    clone = copy.deepcopy(payload["objects"][1])
    clone["assertion_metadata"]["assertion_id"] = "asrt:ward-exists-clone"
    payload["objects"].append(clone)
    with pytest.raises(PersistenceIntegrityError, match="duplicate object_id"):
        _parse(payload)


def test_v4_rejects_duplicate_relationship_id() -> None:
    payload = _v4_payload()
    clone = copy.deepcopy(payload["relationships"][0])
    clone["assertion_metadata"]["assertion_id"] = "asrt:rel-quill-ward-clone"
    payload["relationships"].append(clone)
    with pytest.raises(PersistenceIntegrityError, match="duplicate relationship_id"):
        _parse(payload)


@pytest.mark.parametrize(
    "target_path",
    [
        pytest.param(("objects", 1, "assertion_metadata"), id="existence_vs_existence"),
        pytest.param(("objects", 0, "aliases", 0, "assertion_metadata"), id="alias"),
        pytest.param(("objects", 0, "summary", "assertion_metadata"), id="summary"),
        pytest.param(
            ("objects", 0, "properties", 0, "assertion_metadata"), id="property"
        ),
        pytest.param(("relationships", 0, "assertion_metadata"), id="relationship"),
    ],
)
def test_v4_assertion_ids_are_globally_unique(target_path: tuple[Any, ...]) -> None:
    payload = _v4_payload()
    target: Any = payload
    for key in target_path:
        target = target[key]
    target["assertion_id"] = "asrt:quill-exists"
    with pytest.raises(PersistenceIntegrityError, match="duplicate assertion_id"):
        _parse(payload)


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(datetime(2026, 1, 1, tzinfo=UTC), id="datetime"),
        pytest.param({1, 2}, id="set"),
        pytest.param(math.nan, id="nan"),
        pytest.param(math.inf, id="infinity"),
        pytest.param({"nested": {1: "int-key"}}, id="non_string_object_key"),
        pytest.param([object()], id="opaque_object_in_list"),
    ],
)
def test_v4_rejects_non_json_property_values(value: Any) -> None:
    payload = _v4_payload()
    payload["objects"][0]["properties"][0]["value"] = value
    with pytest.raises(PersistenceIntegrityError):
        _parse(payload)


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(None, id="null"),
        pytest.param(True, id="bool"),
        pytest.param(7, id="int"),
        pytest.param(1.5, id="float"),
        pytest.param(["a", 1, None], id="list"),
        pytest.param({"a": [1, {"b": False}]}, id="nested_object"),
    ],
)
def test_v4_accepts_json_property_values(value: Any) -> None:
    payload = _v4_payload()
    payload["objects"][0]["properties"][0]["value"] = value
    admitted = _parse(payload).objects["obj:person-quill"].admitted_property_assertions
    assert admitted[0].value == value


@pytest.mark.parametrize(
    "blank_path",
    [
        pytest.param(("objects", 0, "label"), id="object_label"),
        pytest.param(("objects", 0, "aliases", 0, "value"), id="alias_value"),
        pytest.param(("objects", 0, "summary", "value"), id="summary_value"),
        pytest.param(("relationships", 0, "relationship_id"), id="relationship_id"),
    ],
)
def test_v4_rejects_blank_required_strings(blank_path: tuple[Any, ...]) -> None:
    payload = _v4_payload()
    target: Any = payload
    for key in blank_path[:-1]:
        target = target[key]
    target[blank_path[-1]] = "   "
    with pytest.raises(PersistenceIntegrityError):
        _parse(payload)


def test_v4_rejects_blank_world_id() -> None:
    payload = _v4_payload()
    payload["world_id"] = " "
    with pytest.raises(PersistenceIntegrityError):
        _parse(payload)


def test_v4_rejects_duplicate_evidence_rows_with_differing_payloads() -> None:
    payload = _v4_payload()
    conflicting = _evidence_row("ev:player", "src:gm-notes")
    payload["evidence_refs"].append(conflicting)
    with pytest.raises(PersistenceIntegrityError, match="duplicate evidence_ref_id"):
        _parse(payload)


# --------------------------------------------------------------------------
# Scope: campaign, visibility, and assertion-grain omission
# --------------------------------------------------------------------------


def test_v4_player_read_omits_gm_assertions() -> None:
    scoped = _scoped()
    quill = scoped.snapshot.objects["obj:person-quill"]
    assert quill.aliases == [PLAYER_ALIAS]
    assert quill.summary == "a public archivist of the low ward"
    assert [item.assertion_id for item in quill.admitted_property_assertions] == [
        "asrt:quill-role-open",
        "asrt:quill-tally",
    ]
    assert "quill the scribe" in scoped.snapshot.alias_index
    assert GM_ALIAS_EVIDENCE_GATED.casefold() not in scoped.snapshot.alias_index
    assert GM_ALIAS_SCOPE_GATED.casefold() not in scoped.snapshot.alias_index
    assert scoped.omitted_alias_index[GM_ALIAS_EVIDENCE_GATED.casefold()] == [
        "obj:person-quill"
    ]
    assert scoped.omitted_alias_index[GM_ALIAS_SCOPE_GATED.casefold()] == [
        "obj:person-quill"
    ]
    assert set(scoped.assertion_exclusions) >= {
        "asrt:quill-alias-secret",
        "asrt:quill-alias-gated",
        "asrt:quill-role-hidden",
    }


def test_v4_gm_read_admits_every_in_campaign_assertion() -> None:
    scoped = _scoped(admissibility=Admissibility.GM)
    quill = scoped.snapshot.objects["obj:person-quill"]
    assert quill.aliases == [
        PLAYER_ALIAS,
        GM_ALIAS_EVIDENCE_GATED,
        GM_ALIAS_SCOPE_GATED,
    ]
    assert len(quill.admitted_property_assertions) == 3
    assert "obj:person-shade" in scoped.snapshot.objects
    assert set(scoped.snapshot.relationships) == {
        "rel:quill-in-ward",
        "rel:quill-secret-tie",
        "rel:shade-in-ward",
    }


def test_v4_hidden_summary_leaves_the_object_standing() -> None:
    payload = _v4_payload()
    payload["objects"][0]["summary"]["assertion_metadata"]["visibility"] = "gm"
    scoped = _scoped(payload=payload)
    quill = scoped.snapshot.objects["obj:person-quill"]
    assert quill.summary is None
    assert quill.aliases == [PLAYER_ALIAS]
    assert "asrt:quill-summary" in scoped.assertion_exclusions


def test_v4_hidden_object_existence_removes_object_and_everything_on_it() -> None:
    scoped = _scoped()
    assert "obj:person-shade" not in scoped.snapshot.objects
    assert "rel:shade-in-ward" not in scoped.snapshot.relationships
    assert "shade" not in scoped.snapshot.label_index
    assert HIDDEN_OBJECT_ALIAS.casefold() not in scoped.snapshot.alias_index
    assert collect_one_hop_object_ids(scoped.snapshot, ["obj:place-low-ward"]) == [
        "obj:person-quill",
        "obj:place-low-ward",
    ]
    serialized = json.dumps(
        {
            "objects": [
                obj.model_dump(mode="json")
                for obj in scoped.snapshot.objects.values()
            ],
            "relationships": [
                rel.model_dump(mode="json")
                for rel in scoped.snapshot.relationships.values()
            ],
        }
    )
    assert "Shade" not in serialized
    assert HIDDEN_OBJECT_ALIAS not in serialized
    assert "watcher" not in serialized


def test_v4_other_campaign_assertions_never_leak() -> None:
    for admissibility in (Admissibility.PLAYER, Admissibility.GM):
        scoped = _scoped(admissibility=admissibility)
        assert "obj:person-foreign" not in scoped.snapshot.objects
        assert "foreign contact" not in scoped.snapshot.label_index


def test_v4_campaign_gate_is_campaign_specific_not_a_blanket_hide() -> None:
    scoped = _scoped(
        admissibility=Admissibility.GM,
        campaign_id=OTHER_CAMPAIGN_ID,
    )
    assert "obj:person-foreign" in scoped.snapshot.objects
    # The other table's read never sees this campaign's knowledge either.
    assert "obj:person-quill" not in scoped.snapshot.objects


def test_v4_world_universal_assertions_survive_both_read_shapes() -> None:
    in_campaign = _scoped()
    assert "obj:place-void" in in_campaign.snapshot.objects

    world_only = _scoped(admissibility=Admissibility.GM, campaign_id=None)
    assert "obj:place-void" in world_only.snapshot.objects
    assert "obj:person-quill" not in world_only.snapshot.objects


def test_v4_hidden_relationship_is_not_traversed() -> None:
    player = _scoped()
    assert "rel:quill-secret-tie" not in player.snapshot.relationships
    assert [
        rel.relationship_id
        for rel in player.snapshot.relationships.values()
        if rel.subject_object_id == "obj:person-quill"
    ] == ["rel:quill-in-ward"]
    assert player.relationship_exclusions["rel:quill-secret-tie"].out_of_scope is True
    assert player.relationship_exclusions["rel:quill-secret-tie"].rejections == []

    gm = _scoped(admissibility=Admissibility.GM)
    assert "rel:quill-secret-tie" in gm.snapshot.relationships


def test_v4_scoped_evidence_drops_omitted_assertion_evidence() -> None:
    scoped = _scoped()
    assert "ev:gm" not in scoped.snapshot.evidence
    assert "ev:player" in scoped.snapshot.evidence


def test_v4_scope_preserves_pinned_profile_fields() -> None:
    snapshot = _parse()
    scoped = project_scoped_snapshot(
        snapshot,
        sources=_sources(),
        world_id=WORLD_ID,
        campaign_id=CAMPAIGN_ID,
        admissibility=Admissibility.PLAYER,
    )
    assert scoped.snapshot.semantic_profile_ref == snapshot.semantic_profile_ref
    assert (
        scoped.snapshot.semantic_profile_descriptor
        == snapshot.semantic_profile_descriptor
    )


def test_v4_scope_exclusions_stay_silent_for_campaign_and_visibility() -> None:
    scoped = _scoped()
    shade = scoped.object_exclusions["obj:person-shade"]
    foreign = scoped.object_exclusions["obj:person-foreign"]
    for exclusion in (shade, foreign):
        assert exclusion.out_of_scope is True
        assert exclusion.scope_unknown is False
        assert exclusion.rejections == []


def test_v4_public_object_dump_never_carries_assertion_metadata() -> None:
    scoped = _scoped()
    quill = scoped.snapshot.objects["obj:person-quill"]
    assert set(quill.model_dump()) == {
        "object_id",
        "kind",
        "label",
        "aliases",
        "evidence_ref_ids",
        "summary",
    }
    edge = scoped.snapshot.relationships["rel:quill-in-ward"]
    assert set(edge.model_dump()) == {
        "relationship_id",
        "subject_object_id",
        "predicate",
        "object_object_id",
        "evidence_ref_ids",
    }


# --------------------------------------------------------------------------
# Historical locks: v1/v2/v3 stay exactly as they were
# --------------------------------------------------------------------------


def _v1_payload() -> dict[str, Any]:
    return {
        "world_id": "world:demo",
        "nodes": [
            {
                "object_id": "obj:a",
                "kind": "location",
                "label": "A",
                "aliases": ["Ay"],
                "evidence_ref_ids": ["ev:a"],
            }
        ],
        "relationships": [],
        "evidence_refs": [
            {
                "evidence_ref_id": "ev:a",
                "source_artifact_id": "src:a",
                "source_domain": "worldbuilding",
                "evidence_role": "support",
            }
        ],
    }


def _v2_payload() -> dict[str, Any]:
    return {
        "world_id": "world:demo",
        "nodes": [
            {
                "object_id": "obj:a",
                "kind": "location",
                "label": "A",
                "evidence_ref_ids": ["ev:a"],
                "alias_assertions": [
                    {
                        "assertion_id": "asrt:a",
                        "alias": "Ay",
                        "evidence_ref_ids": ["ev:a"],
                    }
                ],
                "summary_assertion": None,
            }
        ],
        "relationships": [],
        "evidence_refs": [
            {
                "evidence_ref_id": "ev:a",
                "source_artifact_id": "src:a",
                "source_domain": "worldbuilding",
                "evidence_role": "support",
            }
        ],
    }


def test_v1_v2_v3_readers_reject_the_v4_schema_label() -> None:
    with pytest.raises(PersistenceIntegrityError, match="unsupported graph schema"):
        UnionGraphV1SnapshotReader().parse(
            graph_schema=GRAPH_SCHEMA_V4, graph_payload=_v1_payload()
        )
    with pytest.raises(PersistenceIntegrityError, match="unsupported graph schema"):
        UnionGraphV2SnapshotReader().parse(
            graph_schema=GRAPH_SCHEMA_V4, graph_payload=_v2_payload()
        )
    with pytest.raises(PersistenceIntegrityError, match="unsupported graph schema"):
        UnionGraphV3SnapshotReader(_registry()).parse(
            graph_schema=GRAPH_SCHEMA_V4, graph_payload=_v4_payload()
        )


@pytest.mark.parametrize(
    "graph_schema", [GRAPH_SCHEMA_V1, GRAPH_SCHEMA_V2, GRAPH_SCHEMA_V3]
)
def test_v4_reader_rejects_older_schema_labels(graph_schema: str) -> None:
    with pytest.raises(PersistenceIntegrityError, match="unsupported graph schema"):
        _reader().parse(graph_schema=graph_schema, graph_payload=_v4_payload())


def test_v1_and_v2_reject_v4_only_node_fields() -> None:
    v1 = _v1_payload()
    v1["nodes"][0]["assertion_metadata"] = _meta("asrt:leak")
    with pytest.raises(PersistenceIntegrityError):
        UnionGraphV1SnapshotReader().parse(
            graph_schema=GRAPH_SCHEMA_V1, graph_payload=v1
        )

    v2 = _v2_payload()
    v2["nodes"][0]["alias_assertions"][0]["assertion_metadata"] = _meta("asrt:leak")
    with pytest.raises(PersistenceIntegrityError):
        UnionGraphV2SnapshotReader().parse(
            graph_schema=GRAPH_SCHEMA_V2, graph_payload=v2
        )

    v2_properties = _v2_payload()
    v2_properties["nodes"][0]["properties"] = []
    with pytest.raises(PersistenceIntegrityError):
        UnionGraphV2SnapshotReader().parse(
            graph_schema=GRAPH_SCHEMA_V2, graph_payload=v2_properties
        )


def test_v3_reader_rejects_a_v4_shaped_payload() -> None:
    # V4 uses ``objects``; a v3 reader finds no nodes and every relationship
    # endpoint dangles, so the read fails closed rather than half-parsing.
    with pytest.raises(PersistenceIntegrityError):
        UnionGraphV3SnapshotReader(_registry()).parse(
            graph_schema=GRAPH_SCHEMA_V3, graph_payload=_v4_payload()
        )


def test_v4_reader_rejects_v1_v2_payload_keys() -> None:
    payload = _v4_payload()
    payload["nodes"] = payload.pop("objects")
    with pytest.raises(PersistenceIntegrityError):
        _parse(payload)


def test_v4_reader_rejects_unknown_top_level_keys() -> None:
    payload = _v4_payload()
    payload["properties"] = []
    with pytest.raises(PersistenceIntegrityError):
        _parse(payload)


def test_v1_v2_views_keep_null_v4_fields_and_stable_dumps() -> None:
    v1 = UnionGraphV1SnapshotReader().parse(
        graph_schema=GRAPH_SCHEMA_V1, graph_payload=_v1_payload()
    )
    obj = v1.objects["obj:a"]
    assert obj.object_field_schema == "v1"
    assert obj.existence_assertion_metadata is None
    assert obj.admitted_property_assertions == []
    assert set(obj.model_dump()) == {
        "object_id",
        "kind",
        "label",
        "aliases",
        "evidence_ref_ids",
        "summary",
    }

    v2 = UnionGraphV2SnapshotReader().parse(
        graph_schema=GRAPH_SCHEMA_V2, graph_payload=_v2_payload()
    )
    v2_obj = v2.objects["obj:a"]
    assert v2_obj.object_field_schema == "v2"
    assert v2_obj.existence_assertion_metadata is None
    assert v2_obj.admitted_alias_assertions[0].assertion_metadata is None


# --------------------------------------------------------------------------
# Contract-level guards
# --------------------------------------------------------------------------


def test_temporal_scope_contract_rules() -> None:
    unknown = TemporalScopeRefV1(kind=TemporalScopeKind.UNKNOWN)
    assert unknown.fictional_time_ref is None
    anchored = TemporalScopeRefV1(
        kind=TemporalScopeKind.FICTIONAL_TIME_REF,
        fictional_time_ref="ftime:anchor",
    )
    assert anchored.fictional_time_ref == "ftime:anchor"
    with pytest.raises(ValueError, match="requires fictional_time_ref"):
        TemporalScopeRefV1(kind=TemporalScopeKind.FICTIONAL_TIME_REF)
    with pytest.raises(ValueError, match="must not carry fictional_time_ref"):
        TemporalScopeRefV1(
            kind=TemporalScopeKind.WORLD_TIMELESS,
            fictional_time_ref="ftime:anchor",
        )


def test_knowledge_assertion_metadata_requires_every_field() -> None:
    metadata = KnowledgeAssertionMetadataV1(
        assertion_id="asrt:x",
        campaign_scope=None,
        visibility=Visibility.PLAYER,
        epistemic_kind=EpistemicKindV2.FACT,
        canon_state=CanonState.PROVISIONAL,
        evidence_ref_ids=["ev:x"],
        session_refs=[],
        temporal_scope=TemporalScopeRefV1(kind=TemporalScopeKind.UNKNOWN),
    )
    assert metadata.campaign_scope is None
    base = metadata.model_dump(mode="json")

    with pytest.raises(ValidationError, match="campaign_scope"):
        KnowledgeAssertionMetadataV1.model_validate({**base, "campaign_scope": " "})

    for required in (
        "assertion_id",
        "campaign_scope",
        "visibility",
        "epistemic_kind",
        "canon_state",
        "evidence_ref_ids",
        "session_refs",
        "temporal_scope",
    ):
        incomplete = {key: value for key, value in base.items() if key != required}
        with pytest.raises(ValidationError):
            KnowledgeAssertionMetadataV1.model_validate(incomplete)
