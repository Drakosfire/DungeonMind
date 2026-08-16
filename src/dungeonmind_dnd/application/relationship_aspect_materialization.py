"""Pure adapter: Buddy dual-sense package → D&D v6 materialization plan.

The adapter independently recomputes predicate domain/range admission against
the bundled immutable ``world-object-v5`` catalog. A caller-supplied catalog is
only an explicit pin request: it must match
``builtin_world_object_v5_vocabulary_ref()`` on vocabulary id, revision, and
catalog digest, and admission always uses the loader result. Callers cannot
make a counterfeit catalog trusted by labeling it ``world-object-v5``. The
adapter does not import Buddy, call Git, mint durable aspect assertion IDs, or
treat parse success as attestation.
"""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from ..contracts.relationship_aspect_materialization import (
    SOURCE_PACKAGE_SCHEMA,
    BuddyDualSenseDecompositionPackageV1,
    BuddyEndpointAdmissionV1,
    DndRelationshipAspectDirectiveV1,
    DndRelationshipAspectEndpointDirectiveV1,
    DndRelationshipAspectMaterializationPlanV1,
)
from ..contracts.vocabulary import (
    DndSemanticVocabulary,
    DndVocabularyPredicate,
    DndVocabularyRef,
)
from ..domain.errors import DndError
from .world_object_vocabulary import (
    builtin_world_object_v5_vocabulary_ref,
    load_builtin_world_object_v5_vocabulary,
    vocabulary_sha256,
)


class DndRelationshipAspectMaterializationError(DndError):
    """Buddy dual-sense package cannot be mapped into a v6 materialization plan."""

    code = "dnd_relationship_aspect_materialization_error"


_BUDDY_KIND_TO_DM: dict[str, str] = {
    "location": "dnd5e:location",
    "faction": "dnd5e:faction",
    "party": "dnd5e:party",
    "group": "dnd5e:group",
    "event": "dnd5e:event",
    "npc": "dnd5e:npc",
    "pc": "dnd5e:player_character",
}

_BUDDY_PREDICATE_TO_DM: dict[str, str] = {
    "located_in": "dnd5e:located_in",
    "part_of": "dnd5e:part_of",
    "leads": "dnd5e:leads",
    "participates_in": "dnd5e:participates_in",
    "travels_to": "dnd5e:travels_to",
    "within": "dnd5e:located_in",
}


def _fail(message: str, *, reason: str) -> DndRelationshipAspectMaterializationError:
    return DndRelationshipAspectMaterializationError(
        message, details={"reason": reason}
    )


def _canonical_json(payload: Any) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_bytes(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def recompute_package_canonical_payload_sha256(
    package: BuddyDualSenseDecompositionPackageV1,
) -> str:
    payload = package.model_dump(mode="json", by_alias=True)
    payload["canonical_payload_sha256"] = ""
    return sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def plan_canonical_bytes(plan: DndRelationshipAspectMaterializationPlanV1) -> bytes:
    payload = plan.model_dump(mode="json", by_alias=True)
    payload["plan_sha256"] = ""
    digest = sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    payload["plan_sha256"] = digest
    return (_canonical_json(payload) + "\n").encode("utf-8")


def _vocabulary_ref(vocabulary: DndSemanticVocabulary) -> DndVocabularyRef:
    return DndVocabularyRef(
        vocabulary_id=vocabulary.vocabulary_id,
        vocabulary_revision=vocabulary.vocabulary_revision,
        catalog_sha256=vocabulary_sha256(vocabulary),
    )


def _bind_bundled_world_object_v5(
    offered: DndSemanticVocabulary,
) -> DndSemanticVocabulary:
    """Return the bundled v5 catalog after proving ``offered`` is that pin.

    Admission never uses the caller object. The caller must still present the
    exact bundled identity so a counterfeit catalog labeled world-object-v5
    cannot widen predicates under a stolen revision token.
    """
    pinned = load_builtin_world_object_v5_vocabulary()
    pinned_ref = builtin_world_object_v5_vocabulary_ref()
    if _vocabulary_ref(offered) != pinned_ref:
        raise _fail(
            "caller vocabulary is not the immutable bundled world-object-v5 catalog",
            reason="vocabulary_pin_mismatch",
        )
    if _vocabulary_ref(pinned) != pinned_ref:
        raise _fail(
            "bundled world-object-v5 loader/ref disagree",
            reason="vocabulary_pin_mismatch",
        )
    return pinned


def _kind_in_vocabulary(vocabulary: DndSemanticVocabulary, kind: str) -> bool:
    return any(item.term == kind for item in vocabulary.object_kinds)


def _predicate_in_vocabulary(
    vocabulary: DndSemanticVocabulary, predicate: str
) -> DndVocabularyPredicate | None:
    for item in vocabulary.predicates:
        if item.term == predicate:
            return item
    return None


def _locally_admitted(
    vocabulary: DndSemanticVocabulary,
    *,
    dm_predicate: str,
    source_dm_kind: str,
    target_dm_kind: str,
) -> bool:
    predicate = _predicate_in_vocabulary(vocabulary, dm_predicate)
    if predicate is None:
        return False
    return source_dm_kind in predicate.subject_kinds and target_dm_kind in predicate.object_kinds


def _map_buddy_predicate(buddy_predicate: str) -> str:
    mapped = _BUDDY_PREDICATE_TO_DM.get(buddy_predicate)
    if not mapped:
        raise _fail(
            f"buddy predicate {buddy_predicate!r} has no D&D adapter",
            reason="buddy_predicate_unmapped",
        )
    return mapped


def _map_buddy_kind(buddy_kind: str) -> str:
    mapped = _BUDDY_KIND_TO_DM.get(buddy_kind)
    if not mapped:
        raise _fail(
            f"buddy kind {buddy_kind!r} has no D&D adapter",
            reason="buddy_kind_unmapped",
        )
    return mapped


def _admissions_by_edge(
    rows: list[BuddyEndpointAdmissionV1],
) -> dict[str, BuddyEndpointAdmissionV1]:
    indexed: dict[str, BuddyEndpointAdmissionV1] = {}
    for row in rows:
        if row.edge_id in indexed:
            raise _fail(
                f"duplicate admission for {row.edge_id}",
                reason="duplicate_admission",
            )
        indexed[row.edge_id] = row
    return indexed


def materialize_relationship_aspect_plan_v1(
    raw_package: bytes,
    *,
    world_object_vocabulary: DndSemanticVocabulary,
) -> DndRelationshipAspectMaterializationPlanV1:
    """Map strict package bytes into a deterministic v6 materialization plan.

    The adapter hashes ``raw_package`` itself. Callers cannot supply the digest
    that would make the bytes trusted. Local admission uses the bundled
    world-object-v5 loader, not the caller-supplied catalog object.
    """
    if not isinstance(raw_package, (bytes, bytearray)):
        raise _fail("package input must be raw bytes", reason="package_unattested")
    raw = bytes(raw_package)
    source_package_sha256 = sha256_bytes(raw)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _fail(f"package is not JSON: {exc}", reason="package_invalid") from exc
    if not isinstance(payload, dict):
        raise _fail("package payload must be an object", reason="package_invalid")
    try:
        package = BuddyDualSenseDecompositionPackageV1.model_validate(payload)
    except Exception as exc:
        raise _fail("package failed strict shape validation", reason="package_invalid") from exc

    recomputed = recompute_package_canonical_payload_sha256(package)
    if not package.canonical_payload_sha256 or package.canonical_payload_sha256 != recomputed:
        raise _fail(
            "package canonical_payload_sha256 does not match recomputed digest",
            reason="package_canonical_tampered",
        )

    projection = package.package_projection
    if projection.passed is not True:
        raise _fail("package_projection.passed is not true", reason="package_projection_failed")
    if projection.retained_regressions:
        raise _fail("package retained regressions are nonempty", reason="package_projection_failed")
    if projection.uncovered_current_residual_edge_ids:
        raise _fail("package uncovered residuals are nonempty", reason="package_projection_failed")
    if projection.extra_package_edge_assignments:
        raise _fail("package extra assignments are nonempty", reason="package_projection_failed")
    pinned_vocabulary = _bind_bundled_world_object_v5(world_object_vocabulary)
    if package.world_object_revision_label != pinned_vocabulary.vocabulary_revision:
        raise _fail(
            "package vocabulary revision does not match bundled world-object-v5",
            reason="vocabulary_revision_mismatch",
        )

    source_ids = [row.source_node_id for row in package.decomposition_rows]
    if len(source_ids) != len(set(source_ids)):
        raise _fail("duplicate decomposition source object ids", reason="duplicate_source_object")
    rows_by_source = {row.source_node_id: row for row in package.decomposition_rows}
    assigned_ids = [row.edge_id for row in package.endpoint_assignments]
    if len(assigned_ids) != len(set(assigned_ids)):
        raise _fail("duplicate endpoint assignments", reason="duplicate_assignment")

    assigned_admissions = _admissions_by_edge(projection.assigned_admissions)
    retained_admissions = _admissions_by_edge(projection.retained_admissions)
    assignment_set = set(assigned_ids)
    if set(assigned_admissions) != assignment_set:
        raise _fail(
            "assigned admissions do not join endpoint assignments by edge_id",
            reason="assignment_admission_mismatch",
        )

    deferred_to_row: dict[str, str] = {}
    retained_ids: set[str] = set()
    for row in package.decomposition_rows:
        for edge_id in row.deferred_edge_ids:
            if edge_id in deferred_to_row:
                raise _fail("deferred edge assigned to two rows", reason="duplicate_assignment")
            deferred_to_row[edge_id] = row.source_node_id
        for edge_id in row.retained_edge_ids:
            if edge_id in retained_ids or edge_id in deferred_to_row:
                raise _fail(
                    "retained edge collides with another assignment",
                    reason="duplicate_assignment",
                )
            retained_ids.add(edge_id)
            if edge_id not in retained_admissions:
                raise _fail(
                    f"retained edge {edge_id} missing retained admission",
                    reason="retained_admission_missing",
                )

    if set(deferred_to_row) != assignment_set:
        raise _fail(
            "endpoint assignments do not join exactly one decomposition row",
            reason="assignment_row_mismatch",
        )

    aspect_directives: list[DndRelationshipAspectDirectiveV1] = []
    for row in package.decomposition_rows:
        projected = row.projected_dm_kind
        if not _kind_in_vocabulary(pinned_vocabulary, projected):
            raise _fail(
                f"projected kind {projected!r} is absent from world-object-v5",
                reason="projected_kind_absent",
            )
        primary = _map_buddy_kind(row.stored_buddy_kind)
        if not _kind_in_vocabulary(pinned_vocabulary, primary):
            raise _fail(
                f"primary kind {primary!r} is absent from world-object-v5",
                reason="primary_kind_absent",
            )
        aspect_directives.append(
            DndRelationshipAspectDirectiveV1(
                source_object_id=row.source_node_id,
                aspect_key=row.aspect_key,
                projected_kind=projected,
            )
        )

    endpoint_directives: list[DndRelationshipAspectEndpointDirectiveV1] = []
    for assignment in package.endpoint_assignments:
        row = rows_by_source[deferred_to_row[assignment.edge_id]]
        aspect = assignment.aspect_ref
        endpoint_object = (
            assignment.source_node_id
            if assignment.assigned_endpoint == "source"
            else assignment.target_node_id
        )
        if aspect.source_node_id != endpoint_object:
            raise _fail(
                f"{assignment.edge_id} aspect source does not match assigned endpoint",
                reason="aspect_endpoint_mismatch",
            )
        if aspect.source_node_id != row.source_node_id:
            raise _fail(
                f"{assignment.edge_id} aspect source does not match decomposition row",
                reason="aspect_source_mismatch",
            )
        if aspect.aspect_key != row.aspect_key or aspect.projected_dm_kind != row.projected_dm_kind:
            raise _fail(
                f"{assignment.edge_id} aspect key/kind does not match decomposition row",
                reason="aspect_row_mismatch",
            )
        admission = assigned_admissions[assignment.edge_id]
        dm_predicate = _map_buddy_predicate(assignment.buddy_predicate)
        if admission.dm_predicate != dm_predicate:
            raise _fail(
                f"{assignment.edge_id} claimed dm_predicate does not match local mapping",
                reason="dm_predicate_mismatch",
            )
        if assignment.assigned_endpoint == "source":
            source_kind = aspect.projected_dm_kind
            target_kind = admission.target_dm_kind or ""
        else:
            source_kind = admission.source_dm_kind or ""
            target_kind = aspect.projected_dm_kind
        if not source_kind or not target_kind:
            raise _fail(
                f"{assignment.edge_id} missing effective endpoint kinds",
                reason="endpoint_kind_missing",
            )
        local_ok = _locally_admitted(
            pinned_vocabulary,
            dm_predicate=dm_predicate,
            source_dm_kind=source_kind,
            target_dm_kind=target_kind,
        )
        if not local_ok:
            raise _fail(
                f"{assignment.edge_id} is not admitted by world-object-v5"
                + (" (foreign admitted=true)" if admission.admitted is True else ""),
                reason="local_predicate_rejected",
            )
        if admission.admitted is not True:
            raise _fail(
                f"{assignment.edge_id} assigned admission is not admitted",
                reason="assignment_not_admitted",
            )
        if admission.source_dm_kind != source_kind or admission.target_dm_kind != target_kind:
            raise _fail(
                f"{assignment.edge_id} admission kinds do not match computed effective kinds",
                reason="admission_kind_mismatch",
            )
        endpoint_directives.append(
            DndRelationshipAspectEndpointDirectiveV1(
                source_edge_id=assignment.edge_id,
                assigned_endpoint=assignment.assigned_endpoint,
                source_object_id=assignment.source_node_id,
                target_object_id=assignment.target_node_id,
                aspect_key=aspect.aspect_key,
                projected_kind=aspect.projected_dm_kind,
                dm_predicate=dm_predicate,
                source_dm_kind=source_kind,
                target_dm_kind=target_kind,
            )
        )

    for edge_id, admission in retained_admissions.items():
        dm_predicate = admission.dm_predicate or ""
        source_kind = admission.source_dm_kind or ""
        target_kind = admission.target_dm_kind or ""
        if not dm_predicate or not source_kind or not target_kind:
            raise _fail(
                f"retained admission {edge_id} missing predicate or kinds",
                reason="retained_admission_incomplete",
            )
        if not _kind_in_vocabulary(pinned_vocabulary, source_kind):
            raise _fail(
                f"retained kind {source_kind!r} is absent from world-object-v5",
                reason="retained_kind_absent",
            )
        if not _kind_in_vocabulary(pinned_vocabulary, target_kind):
            raise _fail(
                f"retained kind {target_kind!r} is absent from world-object-v5",
                reason="retained_kind_absent",
            )
        if not _locally_admitted(
            pinned_vocabulary,
            dm_predicate=dm_predicate,
            source_dm_kind=source_kind,
            target_dm_kind=target_kind,
        ):
            raise _fail(
                f"retained edge {edge_id} is not admitted by world-object-v5",
                reason="retained_local_predicate_rejected",
            )
        if admission.admitted is not True:
            raise _fail(
                f"retained edge {edge_id} admission is not admitted",
                reason="retained_not_admitted",
            )

    plan = DndRelationshipAspectMaterializationPlanV1(
        source_package_schema=SOURCE_PACKAGE_SCHEMA,
        source_package_sha256=source_package_sha256,
        source_package_canonical_payload_sha256=recomputed,
        source_world_id=package.world_id,
        source_revision_id=package.canonical_revision_id,
        source_graph_payload_sha256=package.canonical_graph_payload_sha256,
        source_dungeonmind_dependency_ref=package.dungeonmind_dependency_ref,
        world_object_vocabulary=_vocabulary_ref(pinned_vocabulary),
        aspect_directives=sorted(
            aspect_directives,
            key=lambda item: (item.source_object_id, item.aspect_key, item.projected_kind),
        ),
        endpoint_directives=sorted(
            endpoint_directives,
            key=lambda item: item.source_edge_id,
        ),
    )
    sealed = DndRelationshipAspectMaterializationPlanV1.model_validate(
        json.loads(plan_canonical_bytes(plan).decode("utf-8"))
    )
    if any(
        "node:aspect:" in item.source_object_id or "synthetic" in item.source_object_id
        for item in sealed.aspect_directives
    ) or any(
        getattr(item, "aspect_assertion_id", None)
        for item in [*sealed.aspect_directives, *sealed.endpoint_directives]
    ):
        raise _fail("plan invented durable aspect assertion identity", reason="durable_id_invented")
    return sealed
