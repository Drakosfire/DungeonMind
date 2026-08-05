"""Pure graph-pinned Threat mechanics binding and hydration.

The caller supplies one serialized graph revision, one graph reader, one
opaque resource ref, and one resolver.  This module performs no repository,
head, persistence, filesystem, network, or provider work.  Mechanics remain
external producer-owned bytes and are never copied into graph truth.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from typing import Any, NoReturn

from pydantic import ValidationError

from dungeonmind.application.graph_snapshot import GRAPH_SCHEMA_V3, GraphSnapshotReader
from dungeonmind.contracts.graph import StoredGraphRevision
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.domain.canonical import canonical_sha256

from ..contracts.mechanics_resources import (
    THREAT_MECHANICS_BINDING_SCHEMA,
    DndMechanicsResourceEnvelope,
    DndMechanicsResourceRef,
    DndMechanicsResourceResolver,
    DndThreatMechanicsBinding,
    DndThreatMechanicsHydration,
)
from ..contracts.vocabulary import DndVocabularyRef
from ..domain.errors import DndThreatMechanicsHydrationError

_BINDING_ID_SCHEMA = THREAT_MECHANICS_BINDING_SCHEMA
_BINDING_ID_HEX_LENGTH = 32
_THREAT_PREDICATE = "dnd5e:threatens"
_CREATURE_KIND = "dnd5e:creature"
_DND_PROFILE = SemanticProfileRef(
    profile_id="dungeonmind.dnd5e",
    profile_revision="dnd5e-profile-v2",
    descriptor_sha256="57de5bc922503571d781f0de00d0a26b7aabcb3c363518e269f6c7a52a6c0086",
)

# The catalog identity is intentionally represented as fixed profile-owned
# data rather than loaded from package data.  B.3a has no filesystem-backed
# implementation; the checked-in catalog remains the source of this pin.
_THREAT_VOCABULARY_ID = "dungeonmind.dnd5e.threat"
_THREAT_VOCABULARY_REVISION = "threat-v1"
_THREAT_VOCABULARY_SHA256 = (
    "0edaeee9dc6ccb0c507e79339ce74cbea7e3734bb42ae00b4833d02ac8ea6047"
)
_THREAT_VOCABULARY = DndVocabularyRef(
    vocabulary_id=_THREAT_VOCABULARY_ID,
    vocabulary_revision=_THREAT_VOCABULARY_REVISION,
    catalog_sha256=_THREAT_VOCABULARY_SHA256,
)
_SAFE_DETAIL_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_SAFE_DETAIL_REVISION = re.compile(r"^rev:[0-9a-f]{32}$")
_SAFE_DETAIL_OBJECT = re.compile(r"^obj:[A-Za-z0-9._:-]+$")
_SAFE_DETAIL_BINDING = re.compile(r"^mechbind:[0-9a-f]{32}$")
_FAILURE_REASONS = {
    "binding_reload_validation",
    "binding_identity_mismatch",
    "non_gm_admissibility",
    "graph_revision_reload_validation",
    "graph_revision_binding_mismatch",
    "graph_payload_digest_mismatch",
    "unsupported_graph_schema",
    "semantic_profile_mismatch",
    "threat_vocabulary_mismatch",
    "object_not_found",
    "object_kind_not_creature",
    "object_not_threatening",
    "resource_ref_validation",
    "resource_not_found",
    "resource_resolver_failure",
    "resource_envelope_reload_validation",
    "resource_identity_mismatch",
    "resource_payload_digest_mismatch",
    "hydration_contract_validation",
}


def _safe_detail_value(key: str, value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    if key == "graph_revision_id":
        return value if _SAFE_DETAIL_REVISION.fullmatch(value) else None
    if key == "object_id":
        return value if _SAFE_DETAIL_OBJECT.fullmatch(value) else None
    if key == "binding_id":
        return value if _SAFE_DETAIL_BINDING.fullmatch(value) else None
    return value if _SAFE_DETAIL_TOKEN.fullmatch(value) else None


def _failure(
    reason: str,
    *,
    world_id: str | None = None,
    graph_revision_id: str | None = None,
    object_id: str | None = None,
    binding_id: str | None = None,
    resource_id: str | None = None,
    resource_revision: str | None = None,
) -> NoReturn:
    """Raise one fixed-message, closed-reason failure without exception text."""
    details: dict[str, str] = {
        "reason": reason if reason in _FAILURE_REASONS else "hydration_contract_validation"
    }
    safe_ids = {
        "world_id": world_id,
        "graph_revision_id": graph_revision_id,
        "object_id": object_id,
        "binding_id": binding_id,
        "resource_id": resource_id,
        "resource_revision": resource_revision,
    }
    details.update(
        {
            key: safe_value
            for key, value in safe_ids.items()
            if (safe_value := _safe_detail_value(key, value)) is not None
        }
    )
    raise DndThreatMechanicsHydrationError(details=details) from None


def _reload_model(model: Any, model_type: Any, *, reason: str) -> Any:
    """Round-trip a model through its JSON representation before trusting it."""
    try:
        data = (
            model.model_dump(mode="json")
            if hasattr(model, "model_dump")
            else model
        )
        return model_type.model_validate(data)
    except Exception:
        _failure(reason)


def _reload_revision(stored_revision: StoredGraphRevision) -> StoredGraphRevision:
    try:
        data = stored_revision.model_dump(mode="json")
        return StoredGraphRevision.model_validate(data)
    except Exception:
        _failure("graph_revision_reload_validation")


def _verify_revision(
    stored_revision: StoredGraphRevision,
) -> StoredGraphRevision:
    """Verify the stored envelope and payload before graph parsing."""
    revision = stored_revision.revision
    try:
        payload_digest = canonical_sha256(stored_revision.graph_payload)
    except Exception:
        _failure(
            "graph_payload_digest_mismatch",
            world_id=revision.world_id,
            graph_revision_id=revision.revision_id,
        )
    if revision.graph_schema != GRAPH_SCHEMA_V3:
        _failure(
            "unsupported_graph_schema",
            world_id=revision.world_id,
            graph_revision_id=revision.revision_id,
        )
    if payload_digest != revision.graph_payload_sha256:
        _failure(
            "graph_payload_digest_mismatch",
            world_id=revision.world_id,
            graph_revision_id=revision.revision_id,
        )
    payload_world = stored_revision.graph_payload.get("world_id")
    if payload_world != revision.world_id:
        _failure(
            "graph_revision_binding_mismatch",
            world_id=revision.world_id,
            graph_revision_id=revision.revision_id,
        )
    if revision.status != "published":
        _failure(
            "graph_revision_binding_mismatch",
            world_id=revision.world_id,
            graph_revision_id=revision.revision_id,
        )
    return stored_revision


def _parse_snapshot(
    stored_revision: StoredGraphRevision,
    graph_reader: GraphSnapshotReader,
) -> Any:
    """Parse the complete raw payload through the one supplied reader."""
    try:
        return graph_reader.parse(
            graph_schema=stored_revision.revision.graph_schema,
            graph_payload=copy.deepcopy(stored_revision.graph_payload),
        )
    except Exception:
        # Reader/provider/parser diagnostics can contain graph prose or
        # evidence locators.  The public reason remains closed and opaque.
        _failure(
            "semantic_profile_mismatch",
            world_id=stored_revision.revision.world_id,
            graph_revision_id=stored_revision.revision.revision_id,
        )


def _verify_profile_and_vocabulary(
    snapshot: Any,
    *,
    world_id: str,
    graph_revision_id: str,
) -> None:
    try:
        profile_matches = (
            snapshot.world_id == world_id
            and snapshot.graph_schema == GRAPH_SCHEMA_V3
            and snapshot.semantic_profile_ref == _DND_PROFILE
        )
    except Exception:
        profile_matches = False
    if not profile_matches:
        _failure(
            "semantic_profile_mismatch",
            world_id=world_id,
            graph_revision_id=graph_revision_id,
        )
    # These are fixed pins of the bundled D&D profile package.  Keeping this
    # check explicit prevents a caller-owned catalog from widening eligibility.
    if DndVocabularyRef(
        vocabulary_id="dungeonmind.dnd5e.threat",
        vocabulary_revision="threat-v1",
        catalog_sha256="0edaeee9dc6ccb0c507e79339ce74cbea7e3734bb42ae00b4833d02ac8ea6047",
    ) != _THREAT_VOCABULARY:
        _failure(
            "threat_vocabulary_mismatch",
            world_id=world_id,
            graph_revision_id=graph_revision_id,
        )


def _binding_material(
    *,
    world_id: str,
    graph_revision_id: str,
    graph_payload_sha256: str,
    semantic_profile: SemanticProfileRef,
    threat_vocabulary: DndVocabularyRef,
    object_id: str,
    object_kind: str,
    threat_relationship_ids: list[str],
    visibility: str,
    resource_ref: DndMechanicsResourceRef,
) -> dict[str, Any]:
    return {
        "schema": _BINDING_ID_SCHEMA,
        "world_id": world_id,
        "graph_revision_id": graph_revision_id,
        "graph_payload_sha256": graph_payload_sha256,
        "semantic_profile": semantic_profile.model_dump(mode="json"),
        "threat_vocabulary": threat_vocabulary.model_dump(mode="json"),
        "object_id": object_id,
        "object_kind": object_kind,
        "threat_relationship_ids": list(threat_relationship_ids),
        "visibility": visibility,
        "resource_ref": resource_ref.model_dump(mode="json"),
    }


def derive_threat_mechanics_binding_id(
    *,
    world_id: str,
    graph_revision_id: str,
    graph_payload_sha256: str,
    semantic_profile: SemanticProfileRef,
    threat_vocabulary: DndVocabularyRef,
    object_id: str,
    object_kind: str,
    threat_relationship_ids: list[str],
    visibility: str,
    resource_ref: DndMechanicsResourceRef,
) -> str:
    """Derive the deterministic content address of one exact binding."""
    if (
        not threat_relationship_ids
        or len(threat_relationship_ids) != len(set(threat_relationship_ids))
        or threat_relationship_ids != sorted(threat_relationship_ids)
    ):
        raise ValueError(
            "threat_relationship_ids must be non-empty, sorted, and unique"
        )
    return (
        "mechbind:"
        + canonical_sha256(
            _binding_material(
                world_id=world_id,
                graph_revision_id=graph_revision_id,
                graph_payload_sha256=graph_payload_sha256,
                semantic_profile=semantic_profile,
                threat_vocabulary=threat_vocabulary,
                object_id=object_id,
                object_kind=object_kind,
                threat_relationship_ids=threat_relationship_ids,
                visibility=visibility,
                resource_ref=resource_ref,
            )
        )[:_BINDING_ID_HEX_LENGTH]
    )


def _reconstruct_resource_ref(
    resource_ref: DndMechanicsResourceRef,
    *,
    world_id: str | None = None,
    graph_revision_id: str | None = None,
    object_id: str | None = None,
) -> DndMechanicsResourceRef:
    try:
        return DndMechanicsResourceRef.model_validate(
            resource_ref.model_dump(mode="json")
        )
    except Exception:
        _failure(
            "resource_ref_validation",
            world_id=world_id,
            graph_revision_id=graph_revision_id,
            object_id=object_id,
        )


def derive_threat_mechanics_binding(
    object_id: str,
    resource_ref: DndMechanicsResourceRef,
    *,
    graph_revision: StoredGraphRevision,
    graph_reader: GraphSnapshotReader,
) -> DndThreatMechanicsBinding:
    """Bind one exact creature Threat to one opaque external resource."""
    stored = _verify_revision(_reload_revision(graph_revision))
    revision = stored.revision
    snapshot = _parse_snapshot(stored, graph_reader)
    _verify_profile_and_vocabulary(
        snapshot,
        world_id=revision.world_id,
        graph_revision_id=revision.revision_id,
    )

    graph_object = snapshot.objects.get(object_id)
    if graph_object is None:
        _failure(
            "object_not_found",
            world_id=revision.world_id,
            graph_revision_id=revision.revision_id,
            object_id=object_id,
        )
    if graph_object.kind != _CREATURE_KIND:
        _failure(
            "object_kind_not_creature",
            world_id=revision.world_id,
            graph_revision_id=revision.revision_id,
            object_id=object_id,
        )
    relationship_ids = sorted(
        relationship.relationship_id
        for relationship in snapshot.relationships.values()
        if (
            relationship.subject_object_id == object_id
            and relationship.predicate == _THREAT_PREDICATE
        )
    )
    if not relationship_ids or len(relationship_ids) != len(set(relationship_ids)):
        _failure(
            "object_not_threatening",
            world_id=revision.world_id,
            graph_revision_id=revision.revision_id,
            object_id=object_id,
        )

    ref = _reconstruct_resource_ref(
        resource_ref,
        world_id=revision.world_id,
        graph_revision_id=revision.revision_id,
        object_id=object_id,
    )
    binding_id = derive_threat_mechanics_binding_id(
        world_id=revision.world_id,
        graph_revision_id=revision.revision_id,
        graph_payload_sha256=revision.graph_payload_sha256,
        semantic_profile=_DND_PROFILE,
        threat_vocabulary=_THREAT_VOCABULARY,
        object_id=object_id,
        object_kind=graph_object.kind,
        threat_relationship_ids=relationship_ids,
        visibility="gm",
        resource_ref=ref,
    )
    try:
        return DndThreatMechanicsBinding(
            binding_id=binding_id,
            world_id=revision.world_id,
            graph_revision_id=revision.revision_id,
            graph_payload_sha256=revision.graph_payload_sha256,
            semantic_profile=_DND_PROFILE,
            threat_vocabulary=_THREAT_VOCABULARY,
            object_id=object_id,
            object_kind=graph_object.kind,
            threat_relationship_ids=relationship_ids,
            visibility="gm",
            resource_ref=ref,
        )
    except ValidationError:
        _failure(
            "hydration_contract_validation",
            world_id=revision.world_id,
            graph_revision_id=revision.revision_id,
            object_id=object_id,
            binding_id=binding_id,
            resource_id=ref.resource_id,
            resource_revision=ref.resource_revision,
        )


def _resolver_envelope(
    value: DndMechanicsResourceEnvelope | Mapping[str, Any],
    *,
    binding: DndThreatMechanicsBinding,
) -> DndMechanicsResourceEnvelope:
    try:
        data = (
            value.model_dump(mode="json")
            if isinstance(value, DndMechanicsResourceEnvelope)
            else value
        )
    except Exception:
        _failure(
            "resource_envelope_reload_validation",
            world_id=binding.world_id,
            graph_revision_id=binding.graph_revision_id,
            object_id=binding.object_id,
            binding_id=binding.binding_id,
            resource_id=binding.resource_ref.resource_id,
            resource_revision=binding.resource_ref.resource_revision,
        )
    if isinstance(data, Mapping):
        try:
            raw_ref = data.get("resource_ref")
            raw_payload = data.get("mechanics_payload")
            if isinstance(raw_ref, Mapping) and isinstance(raw_payload, dict):
                ref = DndMechanicsResourceRef.model_validate(copy.deepcopy(raw_ref))
                if canonical_sha256(raw_payload) != ref.payload_sha256:
                    _failure(
                        "resource_payload_digest_mismatch",
                        world_id=binding.world_id,
                        graph_revision_id=binding.graph_revision_id,
                        object_id=binding.object_id,
                        binding_id=binding.binding_id,
                        resource_id=binding.resource_ref.resource_id,
                        resource_revision=binding.resource_ref.resource_revision,
                    )
        except DndThreatMechanicsHydrationError:
            raise
        except Exception:
            pass
    try:
        return DndMechanicsResourceEnvelope.model_validate(copy.deepcopy(data))
    except Exception:
        _failure(
            "resource_envelope_reload_validation",
            world_id=binding.world_id,
            graph_revision_id=binding.graph_revision_id,
            object_id=binding.object_id,
            binding_id=binding.binding_id,
            resource_id=binding.resource_ref.resource_id,
            resource_revision=binding.resource_ref.resource_revision,
        )


def hydrate_threat_mechanics(
    binding: DndThreatMechanicsBinding,
    *,
    admissibility: Admissibility,
    graph_revision: StoredGraphRevision,
    graph_reader: GraphSnapshotReader,
    resource_resolver: DndMechanicsResourceResolver,
) -> DndThreatMechanicsHydration:
    """Resolve one exact GM binding once and return isolated verified bytes."""
    supplied_binding = _reload_model(
        binding,
        DndThreatMechanicsBinding,
        reason="binding_reload_validation",
    )
    if admissibility is not Admissibility.GM:
        _failure(
            "non_gm_admissibility",
            world_id=supplied_binding.world_id,
            graph_revision_id=supplied_binding.graph_revision_id,
            object_id=supplied_binding.object_id,
            binding_id=supplied_binding.binding_id,
            resource_id=supplied_binding.resource_ref.resource_id,
            resource_revision=supplied_binding.resource_ref.resource_revision,
        )

    expected = derive_threat_mechanics_binding(
        supplied_binding.object_id,
        supplied_binding.resource_ref,
        graph_revision=graph_revision,
        graph_reader=graph_reader,
    )
    if (
        supplied_binding.model_dump(mode="json")
        != expected.model_dump(mode="json")
    ):
        _failure(
            "binding_identity_mismatch",
            world_id=supplied_binding.world_id,
            graph_revision_id=supplied_binding.graph_revision_id,
            object_id=supplied_binding.object_id,
            binding_id=supplied_binding.binding_id,
            resource_id=supplied_binding.resource_ref.resource_id,
            resource_revision=supplied_binding.resource_ref.resource_revision,
        )

    resolver_ref = _reconstruct_resource_ref(supplied_binding.resource_ref)
    try:
        resolved = resource_resolver.resolve(resolver_ref)
    except Exception:
        _failure(
            "resource_resolver_failure",
            world_id=supplied_binding.world_id,
            graph_revision_id=supplied_binding.graph_revision_id,
            object_id=supplied_binding.object_id,
            binding_id=supplied_binding.binding_id,
            resource_id=supplied_binding.resource_ref.resource_id,
            resource_revision=supplied_binding.resource_ref.resource_revision,
        )
    if resolved is None:
        _failure(
            "resource_not_found",
            world_id=supplied_binding.world_id,
            graph_revision_id=supplied_binding.graph_revision_id,
            object_id=supplied_binding.object_id,
            binding_id=supplied_binding.binding_id,
            resource_id=supplied_binding.resource_ref.resource_id,
            resource_revision=supplied_binding.resource_ref.resource_revision,
        )
    envelope = _resolver_envelope(resolved, binding=supplied_binding)
    if envelope.resource_ref != supplied_binding.resource_ref:
        _failure(
            "resource_identity_mismatch",
            world_id=supplied_binding.world_id,
            graph_revision_id=supplied_binding.graph_revision_id,
            object_id=supplied_binding.object_id,
            binding_id=supplied_binding.binding_id,
            resource_id=supplied_binding.resource_ref.resource_id,
            resource_revision=supplied_binding.resource_ref.resource_revision,
        )
    try:
        payload_digest = canonical_sha256(envelope.mechanics_payload)
    except Exception:
        _failure(
            "resource_payload_digest_mismatch",
            world_id=supplied_binding.world_id,
            graph_revision_id=supplied_binding.graph_revision_id,
            object_id=supplied_binding.object_id,
            binding_id=supplied_binding.binding_id,
            resource_id=supplied_binding.resource_ref.resource_id,
            resource_revision=supplied_binding.resource_ref.resource_revision,
        )
    if payload_digest != supplied_binding.resource_ref.payload_sha256:
        _failure(
            "resource_payload_digest_mismatch",
            world_id=supplied_binding.world_id,
            graph_revision_id=supplied_binding.graph_revision_id,
            object_id=supplied_binding.object_id,
            binding_id=supplied_binding.binding_id,
            resource_id=supplied_binding.resource_ref.resource_id,
            resource_revision=supplied_binding.resource_ref.resource_revision,
        )
    try:
        return DndThreatMechanicsHydration(
            binding=DndThreatMechanicsBinding.model_validate(
                copy.deepcopy(supplied_binding.model_dump(mode="json"))
            ),
            mechanics_payload=copy.deepcopy(envelope.mechanics_payload),
        )
    except ValidationError:
        _failure(
            "hydration_contract_validation",
            world_id=supplied_binding.world_id,
            graph_revision_id=supplied_binding.graph_revision_id,
            object_id=supplied_binding.object_id,
            binding_id=supplied_binding.binding_id,
            resource_id=supplied_binding.resource_ref.resource_id,
            resource_revision=supplied_binding.resource_ref.resource_revision,
        )


__all__ = [
    "derive_threat_mechanics_binding",
    "derive_threat_mechanics_binding_id",
    "hydrate_threat_mechanics",
]
