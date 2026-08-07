"""Pure graph-pinned world-object mechanics binding and hydration.

Hostility-independent: eligible ``dnd5e:threat`` / ``dnd5e:npc`` objects bind
exact external mechanics without requiring ``dnd5e:threatens``. Historical
B.3a Threat mechanics remain in ``threat_mechanics`` unchanged.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from typing import Any, Literal, NoReturn

from pydantic import ValidationError

from dungeonmind.application.graph_snapshot import GRAPH_SCHEMA_V3, GraphSnapshotReader
from dungeonmind.contracts.graph import StoredGraphRevision
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.revision_ids import compute_revision_id

from ..contracts.mechanics_resources import (
    DndMechanicsResourceEnvelope,
    DndMechanicsResourceRef,
    DndMechanicsResourceResolver,
)
from ..contracts.vocabulary import DndVocabularyRef
from ..contracts.world_object_mechanics import (
    WORLD_OBJECT_MECHANICS_ELIGIBLE_KINDS,
    DndWorldObjectMechanicsBinding,
    DndWorldObjectMechanicsHydration,
    derive_world_object_mechanics_binding_id,
)
from ..domain.errors import DndWorldObjectMechanicsHydrationError

_BINDING_ID_HEX_LENGTH = 32
_DND_PROFILE = SemanticProfileRef(
    profile_id="dungeonmind.dnd5e",
    profile_revision="dnd5e-profile-v3",
    descriptor_sha256="2199e8fb96e917c22718e6aec59cbbf55a37ee81575e1bcf16ce13fae0393496",
)
_WORLD_OBJECT_VOCABULARY = DndVocabularyRef(
    vocabulary_id="dungeonmind.dnd5e.world_object",
    vocabulary_revision="world-object-v1",
    catalog_sha256="7cc3b285611ed13eb01e0cdc8a963cfa0bea3130abe0ce816204ab67186cb880",
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
    "world_object_vocabulary_mismatch",
    "object_not_found",
    "object_kind_not_eligible",
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
            key: safe
            for key, raw in safe_ids.items()
            if (safe := _safe_detail_value(key, raw)) is not None
        }
    )
    raise DndWorldObjectMechanicsHydrationError(details=details) from None


def _reload_model(model: Any, model_type: Any, *, reason: str) -> Any:
    try:
        data = model.model_dump(mode="json") if hasattr(model, "model_dump") else model
        return model_type.model_validate(data)
    except Exception:
        _failure(reason)


def _reload_revision(graph_revision: StoredGraphRevision) -> StoredGraphRevision:
    try:
        return StoredGraphRevision.model_validate(graph_revision.model_dump(mode="json"))
    except Exception:
        _failure("graph_revision_reload_validation")


def _verify_revision(stored: StoredGraphRevision) -> StoredGraphRevision:
    revision = stored.revision
    try:
        payload_digest = canonical_sha256(stored.graph_payload)
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
    try:
        expected_revision_id = compute_revision_id(
            world_id=revision.world_id,
            parent_revision_id=revision.parent_revision_id,
            operation_ids=revision.operation_ids,
            graph_schema=revision.graph_schema,
            graph_payload_sha256=revision.graph_payload_sha256,
        )
    except Exception:
        _failure(
            "graph_revision_binding_mismatch",
            world_id=revision.world_id,
            graph_revision_id=revision.revision_id,
        )
    if revision.revision_id != expected_revision_id:
        _failure(
            "graph_revision_binding_mismatch",
            world_id=revision.world_id,
            graph_revision_id=revision.revision_id,
        )
    payload_world = stored.graph_payload.get("world_id")
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
    return stored


def _parse_snapshot(
    stored: StoredGraphRevision,
    graph_reader: GraphSnapshotReader,
) -> Any:
    try:
        return graph_reader.parse(
            graph_schema=stored.revision.graph_schema,
            graph_payload=copy.deepcopy(stored.graph_payload),
        )
    except Exception:
        _failure(
            "semantic_profile_mismatch",
            world_id=stored.revision.world_id,
            graph_revision_id=stored.revision.revision_id,
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
    if (
        DndVocabularyRef(
            vocabulary_id="dungeonmind.dnd5e.world_object",
            vocabulary_revision="world-object-v1",
            catalog_sha256=(
                "7cc3b285611ed13eb01e0cdc8a963cfa0bea3130abe0ce816204ab67186cb880"
            ),
        )
        != _WORLD_OBJECT_VOCABULARY
    ):
        _failure(
            "world_object_vocabulary_mismatch",
            world_id=world_id,
            graph_revision_id=graph_revision_id,
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


def derive_world_object_mechanics_binding(
    object_id: str,
    resource_ref: DndMechanicsResourceRef,
    *,
    graph_revision: StoredGraphRevision,
    graph_reader: GraphSnapshotReader,
) -> DndWorldObjectMechanicsBinding:
    """Bind one eligible world object to one opaque external resource.

    Does not require any ``dnd5e:threatens`` relationship.
    """
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
    if graph_object.kind not in WORLD_OBJECT_MECHANICS_ELIGIBLE_KINDS:
        _failure(
            "object_kind_not_eligible",
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
    object_kind: Literal["dnd5e:threat", "dnd5e:npc"] = graph_object.kind
    binding_id = derive_world_object_mechanics_binding_id(
        world_id=revision.world_id,
        graph_revision_id=revision.revision_id,
        graph_payload_sha256=revision.graph_payload_sha256,
        semantic_profile=_DND_PROFILE,
        world_object_vocabulary=_WORLD_OBJECT_VOCABULARY,
        object_id=object_id,
        object_kind=object_kind,
        visibility="gm",
        resource_ref=ref,
    )
    try:
        return DndWorldObjectMechanicsBinding(
            binding_id=binding_id,
            world_id=revision.world_id,
            graph_revision_id=revision.revision_id,
            graph_payload_sha256=revision.graph_payload_sha256,
            semantic_profile=_DND_PROFILE,
            world_object_vocabulary=_WORLD_OBJECT_VOCABULARY,
            object_id=object_id,
            object_kind=object_kind,
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
    binding: DndWorldObjectMechanicsBinding,
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


def hydrate_world_object_mechanics(
    binding: DndWorldObjectMechanicsBinding,
    *,
    admissibility: Admissibility,
    graph_revision: StoredGraphRevision,
    graph_reader: GraphSnapshotReader,
    resource_resolver: DndMechanicsResourceResolver,
) -> DndWorldObjectMechanicsHydration:
    """Resolve one exact GM binding once and return isolated verified bytes."""
    supplied_binding = _reload_model(
        binding,
        DndWorldObjectMechanicsBinding,
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

    expected = derive_world_object_mechanics_binding(
        supplied_binding.object_id,
        supplied_binding.resource_ref,
        graph_revision=graph_revision,
        graph_reader=graph_reader,
    )
    if supplied_binding.model_dump(mode="json") != expected.model_dump(mode="json"):
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
        return DndWorldObjectMechanicsHydration(
            binding=supplied_binding,
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


# Re-export schema constant for documentation/import stability.
__all__ = [
    "derive_world_object_mechanics_binding",
    "derive_world_object_mechanics_binding_id",
    "hydrate_world_object_mechanics",
]
