"""B.3a pinned Threat mechanics-resource contract and hash gates."""

from __future__ import annotations

import copy
import json
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from dungeonmind.application.graph_snapshot import UnionGraphV3SnapshotReader
from dungeonmind.contracts.graph import StoredGraphRevision, WorldGraphRevision
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor, SemanticProfileRef
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.revision_ids import compute_revision_id
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from dungeonmind_dnd.application.threat_mechanics import (
    derive_threat_mechanics_binding,
    derive_threat_mechanics_binding_id,
    hydrate_threat_mechanics,
)
from dungeonmind_dnd.contracts.mechanics_resources import (
    DndMechanicsResourceEnvelope,
    DndMechanicsResourceRef,
    DndThreatMechanicsBinding,
    DndThreatMechanicsHydration,
)
from dungeonmind_dnd.contracts.vocabulary import DndVocabularyRef
from dungeonmind_dnd.domain.errors import DndThreatMechanicsHydrationError

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "dungeonmind_dnd"
PROFILE_DESCRIPTOR = (
    Path(__file__).resolve().parents[2] / "src/dungeonmind_dnd/profiles/dnd5e-v2.json"
)
RESOURCE_FIXTURE = FIXTURES / "tripod-null-calf-mechanics-resource-v1.json"
BINDING_FIXTURE = FIXTURES / "tripod-null-calf-threat-mechanics-binding-v1.json"
HYDRATION_FIXTURE = FIXTURES / "tripod-null-calf-threat-mechanics-hydration-v1.json"
MATERIALIZED_GRAPH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "contribution_reviews/tripod-null-calf-materialized-world-graph-v3.json"
)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _profile() -> SemanticProfileRef:
    return SemanticProfileRef(
        profile_id="dungeonmind.dnd5e",
        profile_revision="dnd5e-profile-v2",
        descriptor_sha256=(
            "57de5bc922503571d781f0de00d0a26b7aabcb3c363518e269f6c7a52a6c0086"
        ),
    )


def _vocabulary() -> DndVocabularyRef:
    return DndVocabularyRef(
        vocabulary_id="dungeonmind.dnd5e.threat",
        vocabulary_revision="threat-v1",
        catalog_sha256=(
            "0edaeee9dc6ccb0c507e79339ce74cbea7e3734bb42ae00b4833d02ac8ea6047"
        ),
    )


def _stored_revision() -> StoredGraphRevision:
    graph = _json(MATERIALIZED_GRAPH)
    return StoredGraphRevision(
        revision=WorldGraphRevision(
            world_id="world:synthetic-gatewatch",
            revision_id="rev:6e02bd224f6b5616534f10026c8b9679",
            parent_revision_id="rev:f2d5164c176289c5f3df7e68b4f0e46d",
            created_at=datetime(2026, 8, 1, 18, 0, tzinfo=UTC),
            operation_ids=["reviewop:11111111111111111111111111111111"],
            graph_schema="dm_union_graph_v3",
            graph_payload_sha256=(
                "75dd4d9f3425e6646d9141fde1ceea48d4574057bc0b5aada32b165de978adc5"
            ),
        ),
        graph_payload=graph,
    )


def _reader() -> UnionGraphV3SnapshotReader:
    descriptor = SemanticProfileDescriptor.model_validate(
        json.loads(PROFILE_DESCRIPTOR.read_text(encoding="utf-8"))
    )
    return UnionGraphV3SnapshotReader(
        profile_registry=StaticSemanticProfileRegistry([descriptor])
    )


def _resource_ref() -> DndMechanicsResourceRef:
    return DndMechanicsResourceRef.model_validate(_json(RESOURCE_FIXTURE)["resource_ref"])


def _resource() -> DndMechanicsResourceEnvelope:
    return DndMechanicsResourceEnvelope.model_validate(_json(RESOURCE_FIXTURE))


def _binding() -> DndThreatMechanicsBinding:
    return DndThreatMechanicsBinding.model_validate(_json(BINDING_FIXTURE))


class _Resolver:
    def __init__(self, envelope: DndMechanicsResourceEnvelope) -> None:
        self.envelope = envelope
        self.calls: list[DndMechanicsResourceRef] = []

    def resolve(
        self, resource_ref: DndMechanicsResourceRef
    ) -> DndMechanicsResourceEnvelope:
        self.calls.append(resource_ref)
        return self.envelope


def _assert_failure(
    error: DndThreatMechanicsHydrationError,
    *,
    reason: str,
    secret: str | None = None,
) -> None:
    assert error.details["reason"] == reason
    assert str(error) == "D&D Threat mechanics hydration failed."
    surfaces = (
        str(error),
        repr(error),
        "".join(traceback.format_exception(error)),
        json.dumps(error.details, sort_keys=True),
    )
    if secret is not None:
        assert all(secret not in surface for surface in surfaces)
    assert error.__cause__ is None
    assert error.__suppress_context__ is True


def test_complete_fixture_hashes_and_nested_defaults_are_canonical() -> None:
    resource = _json(RESOURCE_FIXTURE)
    binding = _json(BINDING_FIXTURE)
    hydration = _json(HYDRATION_FIXTURE)

    assert canonical_sha256(resource["mechanics_payload"]) == (
        "11e6e581606ffdd1091cf6d515c1fd4288772451a74ec14a979660acdeffd932"
    )
    assert canonical_sha256(resource) == (
        "e5a36d1e74deecf7c256bffa0934911ee665c0d2d3d6a4b6bafa9d5bd95411ae"
    )
    assert canonical_sha256(binding) == (
        "82a6cc1b5df140013ff24cc6dc63721d5c421ee7d6e0c185b22d48d15879dddb"
    )
    assert canonical_sha256(hydration) == (
        "166dfe01ad0e2f4b57de3c74cfd50160e34a29591957f85b4a786c9f2edd6e16"
    )
    assert "schema_version" in binding["semantic_profile"]
    assert "schema_version" in binding["threat_vocabulary"]
    assert "schema_version" in binding["resource_ref"]


def test_binding_derivation_matches_complete_fixture() -> None:
    expected = DndThreatMechanicsBinding.model_validate(_json(BINDING_FIXTURE))

    actual = derive_threat_mechanics_binding(
        expected.object_id,
        _resource_ref(),
        graph_revision=_stored_revision(),
        graph_reader=_reader(),
    )

    assert actual.model_dump(mode="json") == expected.model_dump(mode="json")
    assert actual.binding_id == "mechbind:872167afbc6e6a6b242c6d93036767ab"
    assert canonical_sha256(actual.model_dump(mode="json")) == (
        "82a6cc1b5df140013ff24cc6dc63721d5c421ee7d6e0c185b22d48d15879dddb"
    )


def test_binding_id_helper_uses_complete_nested_contract_dumps() -> None:
    binding = DndThreatMechanicsBinding.model_validate(_json(BINDING_FIXTURE))

    assert derive_threat_mechanics_binding_id(
        world_id=binding.world_id,
        graph_revision_id=binding.graph_revision_id,
        graph_payload_sha256=binding.graph_payload_sha256,
        semantic_profile=binding.semantic_profile,
        threat_vocabulary=binding.threat_vocabulary,
        object_id=binding.object_id,
        object_kind=binding.object_kind,
        threat_relationship_ids=copy.deepcopy(binding.threat_relationship_ids),
        resource_ref=binding.resource_ref,
        visibility=binding.visibility,
    ) == binding.binding_id


def test_hydration_matches_fixture_and_resolves_once_with_isolated_payload() -> None:
    resource = _resource()
    binding = _binding()
    expected = DndThreatMechanicsHydration.model_validate(_json(HYDRATION_FIXTURE))
    resolver = _Resolver(resource)

    actual = hydrate_threat_mechanics(
        binding,
        admissibility=Admissibility.GM,
        graph_revision=_stored_revision(),
        graph_reader=_reader(),
        resource_resolver=resolver,
    )

    assert len(resolver.calls) == 1
    assert actual.model_dump(mode="json") == expected.model_dump(mode="json")
    assert canonical_sha256(actual.model_dump(mode="json")) == (
        "166dfe01ad0e2f4b57de3c74cfd50160e34a29591957f85b4a786c9f2edd6e16"
    )
    assert actual.mechanics_payload is not resource.mechanics_payload
    actual.mechanics_payload["name"] = "mutated"
    assert resource.mechanics_payload["name"] == "Tripod Null-Calf"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ruleset_id", "pathfinder"),
        ("provider_id", "fixture/provider"),
        ("provider_id", "https://provider.invalid/resource"),
        ("resource_id", "statblock/Tripod Null-Calf"),
        ("resource_revision", "tripod/null-calf-v1"),
        ("resource_schema", "fixture\\dnd5e_statblock_v1"),
        ("resource_schema", "latest"),
    ],
)
def test_resource_ref_rejects_locator_or_invalid_identity_tokens(
    field: str, value: str
) -> None:
    payload = _json(RESOURCE_FIXTURE)["resource_ref"]
    payload[field] = value

    with pytest.raises(ValidationError):
        DndMechanicsResourceRef.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider_id", "Fixture.dungeonmind.statblocks"),
        ("provider_id", "fixture:dungeonmind.statblocks"),
        ("resource_id", "Statblock:Tripod-Null-Calf"),
        ("resource_revision", "tripod:null-calf-v1"),
        ("resource_schema", "Fixture:dnd5e_statblock_v1."),
    ],
)
def test_resource_ref_accepts_opaque_non_locator_identity_tokens(
    field: str, value: str
) -> None:
    payload = _json(RESOURCE_FIXTURE)["resource_ref"]
    payload[field] = value

    reference = DndMechanicsResourceRef.model_validate(payload)

    assert getattr(reference, field) == value


def test_resource_envelope_rejects_payload_digest_mismatch() -> None:
    payload = _json(RESOURCE_FIXTURE)
    payload["mechanics_payload"]["armor_class"] = 16

    with pytest.raises(ValidationError):
        DndMechanicsResourceEnvelope.model_validate(payload)


def test_hydration_contract_rejects_payload_digest_mismatch() -> None:
    payload = _json(HYDRATION_FIXTURE)
    payload["mechanics_payload"]["armor_class"] = 16

    with pytest.raises(ValidationError):
        DndThreatMechanicsHydration.model_validate(payload)


def test_binding_contract_rejects_nonderived_binding_id() -> None:
    payload = _json(BINDING_FIXTURE)
    payload["binding_id"] = "mechbind:" + ("0" * 32)

    with pytest.raises(ValidationError):
        DndThreatMechanicsBinding.model_validate(payload)


def test_binding_id_helper_rejects_unsorted_or_duplicate_relationship_ids() -> None:
    binding = _binding()
    for relationship_ids in (
        ["rel:z", "rel:a"],
        ["rel:a", "rel:a"],
        [],
    ):
        with pytest.raises(ValueError):
            derive_threat_mechanics_binding_id(
                world_id=binding.world_id,
                graph_revision_id=binding.graph_revision_id,
                graph_payload_sha256=binding.graph_payload_sha256,
                semantic_profile=binding.semantic_profile,
                threat_vocabulary=binding.threat_vocabulary,
                object_id=binding.object_id,
                object_kind=binding.object_kind,
                threat_relationship_ids=relationship_ids,
                resource_ref=binding.resource_ref,
                visibility=binding.visibility,
            )


class _SpoofedAdmissibility:
    def __str__(self) -> str:
        return "gm"


class _GuardedReader:
    def __init__(self) -> None:
        self.calls = 0

    def parse(self, **_: Any) -> None:
        self.calls += 1
        raise AssertionError("graph parsing must not occur")


class _GuardedResolver:
    def __init__(self) -> None:
        self.calls = 0

    def resolve(self, _: DndMechanicsResourceRef) -> None:
        self.calls += 1
        raise AssertionError("resource resolution must not occur")


def test_gm_gate_requires_enum_identity_before_graph_or_resource_access() -> None:
    reader = _GuardedReader()
    resolver = _GuardedResolver()

    with pytest.raises(DndThreatMechanicsHydrationError) as exc_info:
        hydrate_threat_mechanics(
            _binding(),
            admissibility=cast(Admissibility, _SpoofedAdmissibility()),
            graph_revision=_stored_revision(),
            graph_reader=cast(Any, reader),
            resource_resolver=cast(Any, resolver),
        )

    _assert_failure(exc_info.value, reason="non_gm_admissibility")
    assert reader.calls == 0
    assert resolver.calls == 0


def test_graph_payload_mutation_fails_before_reader_access() -> None:
    stored = _stored_revision()
    mutated_payload = copy.deepcopy(stored.graph_payload)
    mutated_payload["nodes"][0]["label"] = "SENTINEL_GRAPH_LABEL"
    mutated = StoredGraphRevision(
        revision=stored.revision,
        graph_payload=mutated_payload,
    )
    reader = _GuardedReader()

    with pytest.raises(DndThreatMechanicsHydrationError) as exc_info:
        derive_threat_mechanics_binding(
            _binding().object_id,
            _resource_ref(),
            graph_revision=mutated,
            graph_reader=cast(Any, reader),
        )

    _assert_failure(exc_info.value, reason="graph_payload_digest_mismatch")
    assert reader.calls == 0


def test_graph_revision_parent_mutation_fails_before_reader_access() -> None:
    stored = _stored_revision()
    mutated_revision = stored.revision.model_copy(update={"parent_revision_id": None})
    mutated = StoredGraphRevision(
        revision=mutated_revision,
        graph_payload=copy.deepcopy(stored.graph_payload),
    )
    reader = _GuardedReader()

    with pytest.raises(DndThreatMechanicsHydrationError) as exc_info:
        derive_threat_mechanics_binding(
            _binding().object_id,
            _resource_ref(),
            graph_revision=mutated,
            graph_reader=cast(Any, reader),
        )

    _assert_failure(exc_info.value, reason="graph_revision_binding_mismatch")
    assert reader.calls == 0


def test_graph_revision_operation_mutation_fails_before_reader_access() -> None:
    stored = _stored_revision()
    mutated_revision = stored.revision.model_copy(
        update={"operation_ids": ["op:materialize-tripod-null-calf-v1"]}
    )
    mutated = StoredGraphRevision(
        revision=mutated_revision,
        graph_payload=copy.deepcopy(stored.graph_payload),
    )
    reader = _GuardedReader()

    with pytest.raises(DndThreatMechanicsHydrationError) as exc_info:
        derive_threat_mechanics_binding(
            _binding().object_id,
            _resource_ref(),
            graph_revision=mutated,
            graph_reader=cast(Any, reader),
        )

    _assert_failure(exc_info.value, reason="graph_revision_binding_mismatch")
    assert reader.calls == 0


def test_revision_fixture_identity_is_verified_by_compute_revision_id() -> None:
    revision = _stored_revision().revision

    assert compute_revision_id(
        world_id=revision.world_id,
        parent_revision_id=revision.parent_revision_id,
        operation_ids=revision.operation_ids,
        graph_schema=revision.graph_schema,
        graph_payload_sha256=revision.graph_payload_sha256,
    ) == revision.revision_id


def test_resolver_returns_none_after_exactly_one_call() -> None:
    class _MissingResolver:
        def __init__(self) -> None:
            self.calls = 0

        def resolve(self, _: DndMechanicsResourceRef) -> None:
            self.calls += 1
            return None

    resolver = _MissingResolver()
    with pytest.raises(DndThreatMechanicsHydrationError) as exc_info:
        hydrate_threat_mechanics(
            _binding(),
            admissibility=Admissibility.GM,
            graph_revision=_stored_revision(),
            graph_reader=_reader(),
            resource_resolver=cast(Any, resolver),
        )

    _assert_failure(exc_info.value, reason="resource_not_found")
    assert resolver.calls == 1


def test_resolver_resource_identity_mutation_fails_after_one_call() -> None:
    resource = _resource()
    changed_ref = resource.resource_ref.model_copy(
        update={"resource_id": "statblock:other-creature"}
    )
    changed_resource = DndMechanicsResourceEnvelope(
        resource_ref=changed_ref,
        mechanics_payload=copy.deepcopy(resource.mechanics_payload),
    )
    resolver = _Resolver(changed_resource)

    with pytest.raises(DndThreatMechanicsHydrationError) as exc_info:
        hydrate_threat_mechanics(
            _binding(),
            admissibility=Admissibility.GM,
            graph_revision=_stored_revision(),
            graph_reader=_reader(),
            resource_resolver=resolver,
        )

    _assert_failure(exc_info.value, reason="resource_identity_mismatch")
    assert len(resolver.calls) == 1


def test_resolver_payload_mutation_reports_digest_failure_after_one_call() -> None:
    resource = _resource()
    changed_payload = copy.deepcopy(resource.mechanics_payload)
    changed_payload["armor_class"] = 16
    resolver = _Resolver(
        cast(
            Any,
            {
                "schema_version": resource.schema_version,
                "resource_ref": resource.resource_ref.model_dump(mode="json"),
                "mechanics_payload": changed_payload,
            },
        )
    )

    with pytest.raises(DndThreatMechanicsHydrationError) as exc_info:
        hydrate_threat_mechanics(
            _binding(),
            admissibility=Admissibility.GM,
            graph_revision=_stored_revision(),
            graph_reader=_reader(),
            resource_resolver=cast(Any, resolver),
        )

    _assert_failure(exc_info.value, reason="resource_payload_digest_mismatch")
    assert len(resolver.calls) == 1


def test_resolver_exception_is_sanitized_and_suppressed() -> None:
    secret = "https://provider.invalid/token=SECRET_PATH"

    class _ExplodingResolver:
        def resolve(self, _: DndMechanicsResourceRef) -> None:
            raise RuntimeError(secret)

    with pytest.raises(DndThreatMechanicsHydrationError) as exc_info:
        hydrate_threat_mechanics(
            _binding(),
            admissibility=Admissibility.GM,
            graph_revision=_stored_revision(),
            graph_reader=_reader(),
            resource_resolver=cast(Any, _ExplodingResolver()),
        )

    _assert_failure(
        exc_info.value,
        reason="resource_resolver_failure",
        secret=secret,
    )
