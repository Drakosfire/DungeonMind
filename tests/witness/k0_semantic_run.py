"""Execute the K0.2 golden semantic witness scenario."""

from __future__ import annotations

import copy
import json
from typing import Any, Literal

from dungeonmind.application.existing_world_adoption import adopt_existing_world
from dungeonmind.application.existing_world_adoption_repair import (
    repair_existing_world_adoption_source_classification,
)
from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V1,
    GRAPH_SCHEMA_V3,
    GRAPH_SCHEMA_V4,
    GRAPH_SCHEMA_V5,
    GRAPH_SCHEMA_V6,
    VersionedUnionGraphSnapshotReader,
)
from dungeonmind.application.review_publication import publish_finalized_review
from dungeonmind.application.reviewed_world_initialization import (
    initialize_reviewed_world,
    reviewed_world_initialization_replay_identity,
)
from dungeonmind.application.world_graph_projection import WorldGraphProjectionService
from dungeonmind.application.world_graph_retrieval import (
    EvidenceTarget,
    WorldGraphRetrievalService,
)
from dungeonmind.contracts.evidence import SourceDomain
from dungeonmind.contracts.existing_world_adoption_repair import (
    ExistingWorldAdoptionSourceArtifactClassificationRepairIntentV1,
    ExistingWorldAdoptionSourceClassificationRepairIntentV1,
)
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.projection_v2 import ScopeModeV2, WorldGraphProjectionRequestV2
from dungeonmind.domain.errors import (
    FinalizedReviewPublicationOutcomeUnknownError,
    HeadNotFoundError,
    RevisionNotFoundError,
    StaleParentRevisionError,
)
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from tests.witness.k0_semantic_fixture import (
    CAMPAIGN_A,
    NOW,
    FixedClock,
    WitnessStores,
    fixture_manifest,
    make_memory_stores,
    make_services,
    publish_synthetic_ancestor,
    publish_synthetic_head,
    request,
    synthetic_graph_payload,
)
from tests.witness.k0_semantic_normalize import (
    BASE_TREE_SHA,
    INVENTORY_PATH,
    K0_INVENTORY_SCHEMA,
    LANDED_BASE_SHA,
    NORMALIZATION_POLICY,
    REPO_ROOT,
    REQUIRED_OPERATION_IDS,
    WITNESS_SCHEMA,
    aggregate_semantic_sha256,
    dump_canonical_json,
    file_digest,
    make_operation,
    normalization_policy_digest,
    normalize_error,
    normalize_semantic,
    sha256_canonical,
    validate_witness,
)

FIXTURES = REPO_ROOT / "tests" / "fixtures"
GATEWATCH_GRAPH = FIXTURES / "dungeonmind_dnd" / "gatewatch-world-graph-v3.json"
PLAYER_FORBIDDEN = ("obj:alpha-secret", "Hidden Cache", "Traitor's Keep")
NEVER_PUBLISHED_WORLD = "world:never-published"
REPAIRED_AT = NOW  # pinned; observation clocks must not affect semantic digests


def _eldyrwild_classification_repair(stores: WitnessStores, *, raw: bytes, bundle: Any) -> Any:
    """Corrupt then repair Eldyrwild source classification (matches unit fixture lane).

    The corruption seam is adapter-private: in-memory stores mutate repository
    internals; PostgreSQL stores rewrite durable rows. Both converge on the same
    semantic pre-repair state, so the repair receipt is adapter-identical.
    """
    unnamed = next(artifact for artifact in bundle.source_artifacts if artifact.visibility is None)
    intent = ExistingWorldAdoptionSourceClassificationRepairIntentV1(
        world_id=bundle.world_id,
        adoption_id=bundle.adoption_id,
        repairs=[
            ExistingWorldAdoptionSourceArtifactClassificationRepairIntentV1(
                source_artifact_id=unnamed.source_artifact_id,
                set_visibility_to_gm=True,
            )
        ],
    )
    if stores.corrupt_source_classification is None:
        raise RuntimeError("stores do not provide the source-classification corruption seam")
    stores.corrupt_source_classification(bundle.world_id, unnamed.source_artifact_id)
    from tests.unit.test_eldyrwild_existing_world_adoption_bundle_v2 import (
        eldyrwild_graph_reader,
    )

    return repair_existing_world_adoption_source_classification(
        raw,
        repair_intent=intent,
        repaired_at=REPAIRED_AT,
        adoption_repository=stores.adoptions,
        graph_reader=eldyrwild_graph_reader(),
        apply=True,
    )


def _all_builtin_descriptors() -> list[Any]:
    from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor
    from dungeonmind_dnd.application.world_object_vocabulary import load_builtin_v3_descriptor

    profiles = REPO_ROOT / "src" / "dungeonmind_dnd" / "profiles"
    descriptors: list[Any] = []
    for name in ("dnd5e-v1.json", "dnd5e-v2.json"):
        descriptors.append(
            SemanticProfileDescriptor.model_validate(
                json.loads((profiles / name).read_text(encoding="utf-8"))
            )
        )
    descriptors.append(load_builtin_v3_descriptor())
    kernel = REPO_ROOT / "tests" / "fixtures" / "semantic_profiles" / "test-kernel-v1.json"
    descriptors.append(
        SemanticProfileDescriptor.model_validate(json.loads(kernel.read_text(encoding="utf-8")))
    )
    return descriptors


def _reader() -> VersionedUnionGraphSnapshotReader:
    return VersionedUnionGraphSnapshotReader(
        profile_registry=StaticSemanticProfileRegistry(_all_builtin_descriptors())
    )


def _snap(result: Any) -> dict[str, Any]:
    snap = getattr(result, "snapshot", result)
    objects = list(getattr(result, "objects", ()) or ())
    if not objects and hasattr(result, "object") and result.object is not None:
        objects = [result.object]
    rels = list(getattr(result, "relationships", ()) or ())
    # Projection results carry the admitted graph under scoped_graph.snapshot;
    # surface it so scope/projection digests reflect the admitted content.
    scoped_snapshot = getattr(getattr(result, "scoped_graph", None), "snapshot", None)
    if scoped_snapshot is not None and isinstance(getattr(scoped_snapshot, "objects", None), dict):
        objects = list(scoped_snapshot.objects.values())
        rels = list(scoped_snapshot.relationships.values())
    # Object/relationship id lists are unordered sets semantically; sort at the
    # extraction site. Ranking-ordered lists (matched_object_ids) keep order.
    object_ids = sorted(o.object_id for o in objects if getattr(o, "object_id", None))
    labels = sorted(o.label for o in objects if getattr(o, "label", None))
    coverage = getattr(result, "coverage", None)
    return normalize_semantic(
        {
            "world_id": getattr(snap, "world_id", None),
            "campaign_id": getattr(snap, "campaign_id", None),
            "scope_mode": str(getattr(snap, "scope_mode", None)),
            "admissibility": str(getattr(snap, "admissibility", None)),
            "revision_id": getattr(snap, "revision_id", None),
            "head_revision_id": getattr(snap, "head_revision_id", None),
            "is_head": getattr(snap, "is_head", None),
            "found": getattr(result, "found", None),
            "object_ids": object_ids,
            "labels": labels,
            "relationship_ids": sorted(r.relationship_id for r in rels),
            "matched_object_ids": list(getattr(result, "matched_object_ids", ()) or ()),
            "object_depths": dict(getattr(result, "object_depths", {}) or {}),
            "coverage": {
                "gap_codes": list(getattr(coverage, "gap_codes", ()) or ()),
                "missing_ids": list(getattr(coverage, "missing_ids", ()) or ()),
            }
            if coverage is not None
            else None,
        }
    )


def _anchors(result: Any) -> list[dict[str, Any]]:
    return normalize_semantic(
        [
            {
                "anchor_id": a.anchor_id,
                "evidence_ref_id": a.evidence_ref_id,
                "source_artifact_id": a.source_artifact_id,
                "source_revision_id": a.source_revision_id,
            }
            for a in (getattr(result, "anchors", ()) or ())
        ]
    )


def _player_safe(semantic: Any) -> None:
    blob = dump_canonical_json(semantic)
    for token in PLAYER_FORBIDDEN:
        if token in blob:
            raise AssertionError(f"PLAYER semantic leak of {token!r}")


def _run_reads(stores: WitnessStores, head: str, ancestor: str) -> list[dict[str, Any]]:
    projection, retrieval = make_services(stores)
    ops: list[dict[str, Any]] = []
    gm = request(
        scope_mode=ScopeModeV2.CAMPAIGN, campaign_id=CAMPAIGN_A, admissibility=Admissibility.GM
    )
    player = request(
        scope_mode=ScopeModeV2.CAMPAIGN, campaign_id=CAMPAIGN_A, admissibility=Admissibility.PLAYER
    )
    world = request(scope_mode=ScopeModeV2.WORLD, admissibility=Admissibility.GM)
    cross = request(scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN, admissibility=Admissibility.GM)

    ops.append(
        make_operation(
            operation_id="read.head_projection",
            family="read",
            request_identity={"scope": "gm_campaign_a"},
            status="ok",
            semantic_result=_snap(projection.project(gm)),
        )
    )

    # Pin the non-head historical ancestor: the pinned projection must return the
    # older, smaller world state, not the current head.
    pinned = request(
        scope_mode=ScopeModeV2.CAMPAIGN,
        campaign_id=CAMPAIGN_A,
        admissibility=Admissibility.GM,
        revision_pin=ancestor,
    )
    pinned_sem = _snap(projection.project(pinned))
    if pinned_sem.get("revision_id") != ancestor or pinned_sem.get("is_head") is not False:
        raise AssertionError("pinned historical read did not resolve the ancestor revision")
    if pinned_sem.get("revision_id") == head:
        raise AssertionError("pinned historical read resolved the head revision")
    ops.append(
        make_operation(
            operation_id="read.exact_historical_revision",
            family="read",
            request_identity={"revision_pin": ancestor},
            status="ok",
            semantic_result=pinned_sem,
        )
    )

    ops.append(
        make_operation(
            operation_id="read.exact_object",
            family="read",
            request_identity={"object_id": "obj:alpha-keep"},
            status="ok",
            semantic_result=_snap(retrieval.get_object(gm, object_id="obj:alpha-keep")),
        )
    )

    search = retrieval.search(player, query_text="Keep")
    search_sem = _snap(search)
    _player_safe(search_sem)
    ops.append(
        make_operation(
            operation_id="read.deterministic_search",
            family="read",
            request_identity={"query_text": "Keep", "admissibility": "player"},
            status="ok",
            semantic_result=search_sem,
        )
    )

    # PLAYER neighborhood traversal must fail closed: the GM-only neighbor
    # (obj:alpha-secret, one hop from the seed) must never be admitted.
    for depth in (1, 2):
        neighborhood = retrieval.get_neighborhood(
            player, seed_object_ids=["obj:alpha-keep"], depth=depth
        )
        neighborhood_sem = _snap(neighborhood)
        _player_safe(neighborhood_sem)
        ops.append(
            make_operation(
                operation_id=f"read.neighborhood.depth_{depth}",
                family="read",
                request_identity={
                    "seed": "obj:alpha-keep",
                    "depth": depth,
                    "admissibility": "player",
                },
                status="ok",
                semantic_result={
                    **neighborhood_sem,
                    "player_traversal_fail_closed": "obj:alpha-secret"
                    not in neighborhood_sem["object_ids"],
                },
            )
        )

    evidence = retrieval.get_evidence(
        gm, target=EvidenceTarget(kind="object", target_id="obj:alpha-keep")
    )
    ops.append(
        make_operation(
            operation_id="read.evidence",
            family="read",
            request_identity={"target": "obj:alpha-keep"},
            status="ok",
            semantic_result={**_snap(evidence), "anchors": _anchors(evidence)},
        )
    )

    tavern = retrieval.get_object(gm, object_id="obj:world-tavern")
    anchors = _anchors(tavern)
    ops.append(
        make_operation(
            operation_id="read.source_anchor.emit",
            family="read",
            request_identity={"object_id": "obj:world-tavern"},
            status="ok",
            semantic_result={"anchors": anchors},
        )
    )
    if not anchors:
        raise RuntimeError("expected anchors on world-tavern")
    resolved = retrieval.resolve_source_anchor(gm, anchor_id=anchors[0]["anchor_id"])
    ops.append(
        make_operation(
            operation_id="read.source_anchor.revalidate",
            family="read",
            request_identity={"anchor_id": anchors[0]["anchor_id"]},
            status="ok",
            semantic_result=normalize_semantic(
                {
                    "anchor_id": anchors[0]["anchor_id"],
                    "found": getattr(resolved, "found", True),
                    "evidence_ref_id": getattr(
                        getattr(resolved, "anchor", None), "evidence_ref_id", None
                    )
                    or anchors[0]["evidence_ref_id"],
                }
            ),
        )
    )

    for op_id, req, label in (
        ("scope.gm_campaign", gm, "gm"),
        ("scope.player_campaign", player, "player"),
        ("scope.world_owned", world, "world"),
        ("scope.cross_campaign", cross, "cross"),
    ):
        sem = _snap(projection.project(req))
        if label == "player":
            _player_safe(sem)
        ops.append(
            make_operation(
                operation_id=op_id,
                family="scope",
                request_identity={"scope_label": label},
                status="ok",
                semantic_result=sem,
            )
        )

    miss = retrieval.get_object(gm, object_id="obj:does-not-exist")
    ops.append(
        make_operation(
            operation_id="failure.missing_object",
            family="failure",
            request_identity={"object_id": "obj:does-not-exist"},
            status="miss",
            semantic_result=_snap(miss),
        )
    )

    try:
        projection.project(
            request(
                scope_mode=ScopeModeV2.CAMPAIGN,
                campaign_id=CAMPAIGN_A,
                admissibility=Admissibility.GM,
                revision_pin="rev:missing",
            )
        )
        raise AssertionError("expected RevisionNotFoundError")
    except RevisionNotFoundError as exc:
        ops.append(
            make_operation(
                operation_id="failure.missing_revision",
                family="failure",
                request_identity={"revision_pin": "rev:missing"},
                status="error",
                semantic_result=normalize_error(exc, bound={"revision_id": "rev:missing"}),
            )
        )

    # Missing-head proof runs on the adapter stores against a world that was
    # never published, so PostgreSQL exercises the same error path.
    never_published = WorldGraphProjectionRequestV2(
        world_id=NEVER_PUBLISHED_WORLD,
        campaign_id=None,
        admissibility=Admissibility.GM,
        revision_pin=None,
        scope_mode=ScopeModeV2.WORLD,
    )
    try:
        projection.project(never_published)
        raise AssertionError("expected HeadNotFoundError")
    except HeadNotFoundError as exc:
        ops.append(
            make_operation(
                operation_id="failure.missing_head",
                family="failure",
                request_identity={"world_id": NEVER_PUBLISHED_WORLD},
                status="error",
                semantic_result=normalize_error(exc, bound={"world_id": NEVER_PUBLISHED_WORLD}),
            )
        )

    broken = retrieval.get_evidence(
        gm, target=EvidenceTarget(kind="object", target_id="obj:broken-lore")
    )
    ops.append(
        make_operation(
            operation_id="failure.provenance_invalid_fail_closed",
            family="failure",
            request_identity={"object_id": "obj:broken-lore"},
            status="ok",
            semantic_result={
                **_snap(broken),
                "fail_closed": True,
                "excluded_knowledge_stays_excluded": "evidence_source_revision_missing"
                in (broken.coverage.gap_codes if broken.coverage else ()),
            },
        )
    )
    return ops


def _run_writes(stores: WitnessStores) -> list[dict[str, Any]]:
    """Governed write/publication cases executed on the adapter stores.

    Every case runs against the caller-provided stores so the PostgreSQL parity
    lane proves write/governance semantics, not just reads.
    """
    from tests.conformance import test_review_publication as pub
    from tests.unit.test_reviewed_world_initialization_materialization_v6 import (
        graph_reader as init_reader,
    )
    from tests.unit.test_reviewed_world_initialization_materialization_v6 import (
        make_command,
    )

    ops: list[dict[str, Any]] = []

    # Reviewed first-world initialization (governed genesis write).
    command = make_command()
    init_result = initialize_reviewed_world(
        command, initialization_repository=stores.initializations, graph_reader=init_reader()
    )
    ops.append(
        make_operation(
            operation_id="write.reviewed_first_world_initialization",
            family="write",
            request_identity={"initialization_id": command.initialization_id},
            status="ok",
            semantic_result={
                "initialization_id": command.initialization_id,
                "world_id": command.world_id,
                "published_revision_id": init_result.published_revision_id,
                "disposition": type(init_result).__name__,
            },
        )
    )

    # Finalized-review publication lane. Review A is the happy path; review B is
    # pinned to the same parent and serves the failure lanes.
    parent, reader = pub._seed_graph(stores.world_graph)
    stores.reviews.finalize(pub._state())
    review_b = pub.review_state_for_operation("2" * 32)
    stores.reviews.finalize(review_b)
    review_b_id = review_b.record.review_id
    parent_id = parent.revision.revision_id

    def _publish(review_id: str, *, publication_repository: Any, graph_reader: Any) -> Any:
        return publish_finalized_review(
            pub.WORLD_ID,
            review_id,
            published_at=pub.PUBLISHED_AT,
            review_repository=stores.reviews,
            world_graph_repository=stores.world_graph,
            publication_repository=publication_repository,
            graph_reader=graph_reader,
        )

    # Stale parent: a competing writer advances the head, so review B's pinned
    # parent is stale at publish time. The head is then rolled back so later
    # cases keep their own durable boundaries.
    stores.world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=pub.WORLD_ID,
            parent_revision_id=parent_id,
            expected_parent_revision_id=parent_id,
            operation_ids=["op:competing-writer"],
            graph_schema=parent.revision.graph_schema,
            graph_payload=copy.deepcopy(parent.graph_payload),
            created_at=pub.PUBLISHED_AT,
        )
    )
    try:
        _publish(
            review_b_id,
            publication_repository=stores.publications,
            graph_reader=reader,
        )
        raise AssertionError("expected StaleParentRevisionError")
    except StaleParentRevisionError as exc:
        ops.append(
            make_operation(
                operation_id="write.stale_parent_rejection",
                family="write",
                request_identity={"review_id": review_b_id},
                status="error",
                semantic_result=normalize_error(exc),
            )
        )
    stores.world_graph.rollback_head(pub.WORLD_ID, parent_id, updated_at=pub.PUBLISHED_AT)

    # Outcome-unknown: the publication commits durably but the response is lost
    # and the recovery probe fails. The follow-up publish must recover the
    # durable record without rematerialization.
    spy_pubs = pub._SpyPublicationRepository(
        stores.publications,
        raise_after_publish=True,
        fail_recovery_probe=True,
    )
    unknown_error: dict[str, Any] | None = None
    try:
        _publish(review_b_id, publication_repository=spy_pubs, graph_reader=reader)
        raise AssertionError("expected FinalizedReviewPublicationOutcomeUnknownError")
    except FinalizedReviewPublicationOutcomeUnknownError as exc:
        unknown_error = normalize_error(exc)
    recovered = _publish(
        review_b_id,
        publication_repository=pub._SpyPublicationRepository(stores.publications),
        graph_reader=pub._RejectingReader(),
    )
    ops.append(
        make_operation(
            operation_id="write.outcome_unknown_recovery",
            family="write",
            request_identity={"review_id": review_b_id},
            status="error",
            semantic_result={
                "error": unknown_error,
                "durable_recovery": {
                    "recovered": True,
                    "review_id": review_b_id,
                    "published_revision_id": recovered.published_revision_id,
                    "replay_without_rematerialization": True,
                },
            },
        )
    )
    stores.world_graph.rollback_head(pub.WORLD_ID, parent_id, updated_at=pub.PUBLISHED_AT)

    # Happy path: exact-parent publication of review A, then exact replay.
    published = _publish(
        pub.REVIEW_ID,
        publication_repository=stores.publications,
        graph_reader=reader,
    )
    ops.append(
        make_operation(
            operation_id="write.exact_parent_publication",
            family="write",
            request_identity={"review_id": pub.REVIEW_ID},
            status="ok",
            semantic_result={
                "published_revision_id": published.published_revision_id,
                "expected_parent_revision_id": published.expected_parent_revision_id,
                "parent_revision_id": parent_id,
                "disposition": type(published).__name__,
            },
        )
    )

    replayed = _publish(
        pub.REVIEW_ID,
        publication_repository=stores.publications,
        graph_reader=reader,
    )
    ops.append(
        make_operation(
            operation_id="write.exact_replay_idempotency",
            family="write",
            request_identity={"review_id": pub.REVIEW_ID, "mode": "replay"},
            status="ok",
            semantic_result={
                "published_revision_id": replayed.published_revision_id,
                "matches_first_publish": replayed.published_revision_id
                == published.published_revision_id,
                "disposition": type(replayed).__name__,
            },
        )
    )

    # Correction/retraction: Eldyrwild sealed-bundle adoption, adapter-private
    # classification corruption, then the governed repair.
    from tests.unit.test_eldyrwild_existing_world_adoption_bundle_v2 import (
        eldyrwild_graph_reader,
        parse_sealed_bundle,
        raw_bundle,
    )

    adopt_raw = raw_bundle()
    adopt_bundle = parse_sealed_bundle()
    adopt_existing_world(
        adopt_raw,
        adopted_at=NOW,
        adoption_repository=stores.adoptions,
        graph_reader=eldyrwild_graph_reader(),
    )
    repair = _eldyrwild_classification_repair(stores, raw=adopt_raw, bundle=adopt_bundle)
    ops.append(
        make_operation(
            operation_id="write.correction_or_retraction",
            family="write",
            request_identity={
                "mechanism": "adoption_source_classification_repair",
                "world_id": adopt_bundle.world_id,
                "adoption_id": adopt_bundle.adoption_id,
            },
            status="ok",
            semantic_result={
                "mechanism": "existing_world_adoption_source_classification_repair",
                "disposition": type(repair).__name__,
                "world_id": adopt_bundle.world_id,
                "membership_sha256": repair.membership_sha256,
                "effective_membership_sha256": repair.effective_membership_sha256,
                "schema_version": getattr(repair, "schema_version", None),
            },
        )
    )

    # Source/evidence binding integrity through the governed path: read an object
    # published by the reviewed first-world initialization above and prove its
    # evidence binds to the durable source records that write persisted.
    init_projection = WorldGraphProjectionService(
        world_graph=stores.world_graph,
        sources=stores.sources,
        graph_reader=init_reader(),
        reviewed_world_initializations=stores.initializations,
        clock=FixedClock(),
    )
    init_retrieval = WorldGraphRetrievalService(projection=init_projection, sources=stores.sources)
    init_request = WorldGraphProjectionRequestV2(
        world_id=command.world_id,
        campaign_id=command.campaign_id,
        admissibility=Admissibility.GM,
        revision_pin=None,
        scope_mode=ScopeModeV2.CAMPAIGN,
    )
    view = init_retrieval.get_object(init_request, object_id="obj:college")
    obj = view.object
    bound_anchors = _anchors(view)
    if not bound_anchors:
        raise RuntimeError("governed publication produced no resolvable source anchors")
    ops.append(
        make_operation(
            operation_id="write.source_evidence_binding_integrity",
            family="write",
            request_identity={
                "object_id": "obj:college",
                "world_id": command.world_id,
                "governed_by": "reviewed_world_initialization",
                "initialization_id": command.initialization_id,
            },
            status="ok",
            semantic_result={
                "governed_by": "reviewed_world_initialization",
                "initialization_id": command.initialization_id,
                "published_revision_id": init_result.published_revision_id,
                "object_id": "obj:college",
                "found": bool(getattr(view, "found", obj is not None)),
                "evidence_ref_ids": list(obj.evidence_ref_ids if obj is not None else []),
                "anchors": bound_anchors,
                "source_artifact_persisted": stores.sources.get_artifact("src:notes-a") is not None,
                "source_revision_persisted": stores.sources.get_revision("srcrev:notes-a-v1")
                is not None,
                "binding_integrity": "governed_publication_evidence_bound_to_durable_source",
            },
        )
    )
    return ops


def _run_historical(stores: WitnessStores) -> list[dict[str, Any]]:
    from tests.unit.test_eldyrwild_existing_world_adoption_bundle_v2 import (
        BUNDLE_SHA256,
        PUBLISHED_REVISION_ID,
        eldyrwild_graph_reader,
        parse_sealed_bundle,
        raw_bundle,
    )
    from tests.unit.test_eldyrwild_existing_world_adoption_bundle_v2 import (
        WORLD_ID as ELDYR_WORLD,
    )
    from tests.unit.test_graph_snapshot_reader import _payload as v1_payload
    from tests.unit.test_reviewed_world_initialization import make_stores as make_init_stores
    from tests.unit.test_reviewed_world_initialization_materialization_v6 import (
        CAMPAIGN_ID as INIT_CAMPAIGN_ID,
    )
    from tests.unit.test_reviewed_world_initialization_materialization_v6 import (
        FAMILY_EVIDENCE_ID,
        graph_reader,
        make_command,
        make_first_world_family_command,
        make_non_family_other_evidence_command,
    )

    reader = _reader()
    historical: list[dict[str, Any]] = []

    def add(schema: str, payload: dict[str, Any], path: str, case_id: str) -> None:
        parsed = reader.parse(graph_schema=schema, graph_payload=payload)
        summary = normalize_semantic(
            {
                "world_id": getattr(parsed, "world_id", None),
                "object_count": len(getattr(parsed, "objects", ()) or ()),
                "relationship_count": len(getattr(parsed, "relationships", ()) or ()),
                "evidence_count": len(getattr(parsed, "evidence_refs", ()) or ()),
            }
        )
        historical.append(
            {
                "case_id": case_id,
                "stored_schema_version": schema,
                "reader_path": path,
                "semantic_result": summary,
                "semantic_sha256": sha256_canonical(summary),
            }
        )

    add(
        GRAPH_SCHEMA_V1,
        v1_payload(),
        "VersionedUnionGraphSnapshotReader.parse v1",
        "graph.dm_union_graph_v1",
    )

    from dungeonmind.application.graph_snapshot import GRAPH_SCHEMA_V2
    from tests.unit.test_assertion_scoped_graph import _v2_payload

    add(
        GRAPH_SCHEMA_V2,
        _v2_payload(),
        "VersionedUnionGraphSnapshotReader.parse v2",
        "graph.dm_union_graph_v2",
    )

    gate = json.loads(GATEWATCH_GRAPH.read_text(encoding="utf-8"))
    add(
        gate.get("graph_schema", GRAPH_SCHEMA_V3),
        gate["graph_payload"],
        "VersionedUnionGraphSnapshotReader.parse gatewatch-world-graph-v3.json",
        "graph.dm_union_graph_v3",
    )

    from tests.unit.test_union_graph_v4 import _v4_payload
    from tests.unit.test_union_graph_v5 import _v5_payload

    add(
        GRAPH_SCHEMA_V4,
        _v4_payload(),
        "VersionedUnionGraphSnapshotReader.parse v4",
        "graph.dm_union_graph_v4",
    )
    add(
        GRAPH_SCHEMA_V5,
        _v5_payload(),
        "VersionedUnionGraphSnapshotReader.parse v5",
        "graph.dm_union_graph_v5",
    )

    add(
        GRAPH_SCHEMA_V6,
        synthetic_graph_payload(),
        "VersionedUnionGraphSnapshotReader.parse synthetic v6 witness payload",
        "graph.dm_union_graph_v6",
    )

    adopt_raw = raw_bundle()
    adopt_bundle = parse_sealed_bundle()
    # Historical adoption/repair lane is adapter-neutral: always use the in-memory
    # reference path so the golden digest stays comparable under PostgreSQL parity.
    eldyr_stores = make_memory_stores()
    adopt_result = adopt_existing_world(
        adopt_raw,
        adopted_at=NOW,
        adoption_repository=eldyr_stores.adoptions,
        graph_reader=eldyrwild_graph_reader(),
    )
    adopt_sem = normalize_semantic(
        {
            "world_id": ELDYR_WORLD,
            "bundle_sha256": BUNDLE_SHA256,
            "published_revision_id": PUBLISHED_REVISION_ID,
            "disposition": type(adopt_result).__name__,
            "membership_sha256": getattr(adopt_result, "membership_sha256", None),
        }
    )
    historical.append(
        {
            "case_id": "adoption.eldyrwild_bundle_v2",
            "stored_schema_version": "dm_existing_world_adoption_bundle_v2",
            "reader_path": "adopt_existing_world(eldyrwild_existing_world_adoption_bundle_v2.json)",
            "semantic_result": adopt_sem,
            "semantic_sha256": sha256_canonical(adopt_sem),
        }
    )

    repair = _eldyrwild_classification_repair(eldyr_stores, raw=adopt_raw, bundle=adopt_bundle)
    repair_sem = normalize_semantic(
        {
            "world_id": ELDYR_WORLD,
            "mechanism": "repair_existing_world_adoption_source_classification",
            "disposition": type(repair).__name__,
            "membership_sha256": repair.membership_sha256,
            "effective_membership_sha256": repair.effective_membership_sha256,
            "schema_version": getattr(repair, "schema_version", None),
        }
    )
    historical.append(
        {
            "case_id": "adoption.eldyrwild_source_classification_repair",
            "stored_schema_version": "dm_existing_world_adoption_repair",
            "reader_path": "repair_existing_world_adoption_source_classification",
            "semantic_result": repair_sem,
            "semantic_sha256": sha256_canonical(repair_sem),
        }
    )

    _g, _s, _c, _i, inits, _a = make_init_stores()
    command = make_command()
    initialize_reviewed_world(command, initialization_repository=inits, graph_reader=graph_reader())
    receipt = inits.get_for_world(command.world_id)
    compat = normalize_semantic(
        {
            "world_id": command.world_id,
            "initialization_id": command.initialization_id,
            "has_receipt": receipt is not None,
            "compatibility": "reviewed_first_world_provenance",
        }
    )
    historical.append(
        {
            "case_id": "reviewed_init.receipt_roundtrip",
            "stored_schema_version": "dm_reviewed_world_initialization_v1",
            "reader_path": "initialize_reviewed_world + get_for_world",
            "semantic_result": compat,
            "semantic_sha256": sha256_canonical(compat),
        }
    )

    # ADR-0023: historical #645-family OTHER-stamped D0 evidence must project
    # through GenesisEvidenceCompatibility while the raw stored revision keeps
    # its OTHER stamps; the corrected WORLDBUILDING retry must replay onto the
    # stored receipt; non-family OTHER evidence stays fail-closed.
    fam_graph, fam_sources, _fc, _fi, fam_inits, _fa = make_init_stores()
    family_command = make_first_world_family_command(evidence_domain=SourceDomain.OTHER)
    family_receipt = initialize_reviewed_world(
        family_command, initialization_repository=fam_inits, graph_reader=graph_reader()
    )
    stored_d0 = fam_graph.get_revision(
        family_command.world_id, family_receipt.published_revision_id
    )
    if stored_d0 is None:
        raise RuntimeError("family D0 revision missing")
    raw_d0_domains = sorted(
        {record["source_domain"] for record in stored_d0.graph_payload["evidence_refs"]}
    )

    def _init_projection(graph: Any, sources: Any, init_repo: Any, world_id: str) -> Any:
        return WorldGraphProjectionService(
            world_graph=graph,
            sources=sources,
            graph_reader=graph_reader(),
            reviewed_world_initializations=init_repo,
            clock=FixedClock(),
        ).project(
            WorldGraphProjectionRequestV2(
                world_id=world_id,
                campaign_id=INIT_CAMPAIGN_ID,
                admissibility=Admissibility.GM,
                revision_pin=None,
                scope_mode=ScopeModeV2.CAMPAIGN,
            )
        )

    family_projection = _init_projection(fam_graph, fam_sources, fam_inits, family_command.world_id)
    family_admitted = sorted(family_projection.scoped_graph.snapshot.objects)
    admitted_evidence = family_projection.scoped_graph.snapshot.evidence[FAMILY_EVIDENCE_ID]

    corrected_command = make_first_world_family_command(evidence_domain=SourceDomain.WORLDBUILDING)
    replay_identity = reviewed_world_initialization_replay_identity(corrected_command)
    corrected_retry = initialize_reviewed_world(
        corrected_command, initialization_repository=fam_inits, graph_reader=graph_reader()
    )

    nf_graph, nf_sources, _nfc, _nfi, nf_inits, _nfa = make_init_stores()
    non_family_command = make_non_family_other_evidence_command()
    initialize_reviewed_world(
        non_family_command, initialization_repository=nf_inits, graph_reader=graph_reader()
    )
    nf_projection = _init_projection(nf_graph, nf_sources, nf_inits, non_family_command.world_id)
    nf_admitted = sorted(nf_projection.scoped_graph.snapshot.objects)

    adr_sem = normalize_semantic(
        {
            "world_id": family_command.world_id,
            "initialization_id": family_command.initialization_id,
            "family_admitted_object_ids": family_admitted,
            "family_admitted_evidence_domain": admitted_evidence.source_domain.value,
            "raw_d0_evidence_domains": raw_d0_domains,
            "corrected_retry_returns_stored_receipt": corrected_retry == family_receipt,
            "historical_other_normalized_sha256": (
                replay_identity.historical_other_normalized_sha256
            ),
            "non_family_other_admitted_object_ids": nf_admitted,
            "non_family_other_fail_closed": nf_admitted == [],
        }
    )
    historical.append(
        {
            "case_id": "reviewed_init.adr0023_genesis_other_compatibility",
            "stored_schema_version": "dm_reviewed_world_initialization_v1",
            "reader_path": "initialize_reviewed_world(#645 OTHER) + project + corrected retry",
            "semantic_result": adr_sem,
            "semantic_sha256": sha256_canonical(adr_sem),
        }
    )
    return historical


def run_witness(
    *,
    adapter: Literal["memory", "postgres"] = "memory",
    stores: WitnessStores | None = None,
) -> dict[str, Any]:
    if stores is None:
        if adapter != "memory":
            raise ValueError("postgres adapter requires stores=")
        stores = make_memory_stores()

    ancestor = publish_synthetic_ancestor(stores)
    head = publish_synthetic_head(stores, parent_revision_id=ancestor)
    manifest = fixture_manifest(head_revision_id=head, ancestor_revision_id=ancestor)
    operations = _run_reads(stores, head, ancestor)
    operations.extend(_run_writes(stores))
    historical = _run_historical(stores)

    missing = [op for op in REQUIRED_OPERATION_IDS if op not in {r["id"] for r in operations}]
    if missing:
        raise RuntimeError(f"missing required operations: {missing}")

    witness: dict[str, Any] = {
        "schema": WITNESS_SCHEMA,
        "inputs": {
            "dungeonmind_landed_base_sha": LANDED_BASE_SHA,
            "dungeonmind_base_tree_sha": BASE_TREE_SHA,
            "k0_inventory_schema": K0_INVENTORY_SCHEMA,
            "k0_inventory_digest": file_digest(INVENTORY_PATH),
            "fixture_digest": f"sha256:{sha256_canonical(manifest)}",
            "normalization_policy_digest": normalization_policy_digest(),
            "witness_schema": WITNESS_SCHEMA,
            "adapter": adapter,
        },
        "normalization_policy": NORMALIZATION_POLICY,
        "fixture": manifest,
        "operations": sorted(operations, key=lambda row: row["id"]),
        "historical_compatibility": historical,
        "aggregate_semantic_sha256": "",
    }
    witness["aggregate_semantic_sha256"] = aggregate_semantic_sha256(witness["operations"])
    validate_witness(witness)
    return witness
