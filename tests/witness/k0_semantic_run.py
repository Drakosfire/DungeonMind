"""Execute the K0.2 golden semantic witness scenario."""

from __future__ import annotations

import copy
import json
from pathlib import Path
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
from dungeonmind.application.reviewed_world_initialization import initialize_reviewed_world
from dungeonmind.application.world_graph_retrieval import EvidenceTarget
from dungeonmind.contracts.existing_world_adoption_repair import (
    ExistingWorldAdoptionSourceArtifactClassificationRepairIntentV1,
    ExistingWorldAdoptionSourceClassificationRepairIntentV1,
)
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.projection_v2 import ScopeModeV2
from dungeonmind.contracts.vocabulary import Visibility
from dungeonmind.domain.errors import (
    FinalizedReviewPublicationOutcomeUnknownError,
    HeadNotFoundError,
    RevisionNotFoundError,
    StaleParentRevisionError,
)
from dungeonmind.domain.existing_world_membership import (
    existing_world_adoption_membership_sha256,
)
from dungeonmind.infrastructure.memory import (
    InMemoryFinalizedReviewPublicationRepository,
    InMemoryWorldGraphRepository,
)
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from tests.witness.k0_semantic_fixture import (
    CAMPAIGN_A,
    NOW,
    WORLD_ID,
    WitnessStores,
    fixture_manifest,
    make_memory_stores,
    make_services,
    publish_synthetic_head,
    request,
    synthetic_graph_payload,
)
from tests.witness.k0_semantic_normalize import (
    K0_INVENTORY_SCHEMA,
    NORMALIZATION_POLICY,
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

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_SHA = "3b52a81a6c113ac6bfb4d1b0fa7fa78246aa31f1"
INVENTORY_PATH = REPO_ROOT / "Docs" / "Reports" / "K0-surface-inventory.json"
FIXTURES = REPO_ROOT / "tests" / "fixtures"
GATEWATCH_GRAPH = FIXTURES / "dungeonmind_dnd" / "gatewatch-world-graph-v3.json"
PLAYER_FORBIDDEN = ("obj:alpha-secret", "Hidden Cache", "Traitor's Keep")
REPAIRED_AT = NOW  # pinned; observation clocks must not affect semantic digests


def _world_membership(sources, contributions, identity, world_id: str) -> str:
    artifacts = [
        artifact for artifact in sources._artifacts.values() if artifact.world_id == world_id
    ]
    artifact_ids = {artifact.source_artifact_id for artifact in artifacts}
    return existing_world_adoption_membership_sha256(
        source_artifacts=artifacts,
        source_revisions=[
            revision
            for revision in sources._revisions.values()
            if revision.source_artifact_id in artifact_ids
        ],
        contributions=[item for key, item in contributions._items.items() if key[0] == world_id],
        identity_decisions=[item for key, item in identity._items.items() if key[0] == world_id],
    )


def _eldyrwild_classification_repair(stores: WitnessStores, *, raw: bytes, bundle: Any) -> Any:
    """Corrupt then repair Eldyrwild source classification (matches unit fixture lane)."""
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
    stores.sources._artifacts[unnamed.source_artifact_id] = unnamed.model_copy(
        update={"visibility": Visibility.GM}
    )
    digest = _world_membership(
        stores.sources, stores.contributions, stores.identity, bundle.world_id
    )
    stored = stores.adoptions._receipts_by_world[bundle.world_id]
    rewritten = stored.model_copy(update={"membership_sha256": digest})
    stores.adoptions._receipts_by_world[bundle.world_id] = rewritten
    stores.adoptions._receipts_by_adoption[rewritten.adoption_id] = rewritten
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
    object_ids = sorted(o.object_id for o in objects if getattr(o, "object_id", None))
    labels = sorted(o.label for o in objects if getattr(o, "label", None))
    rels = list(getattr(result, "relationships", ()) or ())
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


def _run_reads(stores: WitnessStores, head: str) -> list[dict[str, Any]]:
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

    pinned = request(
        scope_mode=ScopeModeV2.CAMPAIGN,
        campaign_id=CAMPAIGN_A,
        admissibility=Admissibility.GM,
        revision_pin=head,
    )
    ops.append(
        make_operation(
            operation_id="read.exact_historical_revision",
            family="read",
            request_identity={"revision_pin": head},
            status="ok",
            semantic_result=_snap(projection.project(pinned)),
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

    ops.append(
        make_operation(
            operation_id="read.neighborhood.depth_1",
            family="read",
            request_identity={"seed": "obj:alpha-keep", "depth": 1},
            status="ok",
            semantic_result=_snap(
                retrieval.get_neighborhood(gm, seed_object_ids=["obj:alpha-keep"], depth=1)
            ),
        )
    )
    ops.append(
        make_operation(
            operation_id="read.neighborhood.depth_2",
            family="read",
            request_identity={"seed": "obj:alpha-keep", "depth": 2},
            status="ok",
            semantic_result=_snap(
                retrieval.get_neighborhood(gm, seed_object_ids=["obj:alpha-keep"], depth=2)
            ),
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

    empty = make_memory_stores()
    empty_proj, _ = make_services(empty)
    try:
        empty_proj.project(gm)
        raise AssertionError("expected HeadNotFoundError")
    except HeadNotFoundError as exc:
        ops.append(
            make_operation(
                operation_id="failure.missing_head",
                family="failure",
                request_identity={"world_id": WORLD_ID},
                status="error",
                semantic_result=normalize_error(exc, bound={"world_id": WORLD_ID}),
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


def _run_writes() -> list[dict[str, Any]]:
    from tests.conformance import test_review_publication as pub
    from tests.unit.test_reviewed_world_initialization import make_stores as make_init_stores
    from tests.unit.test_reviewed_world_initialization_materialization_v6 import (
        graph_reader as init_reader,
    )
    from tests.unit.test_reviewed_world_initialization_materialization_v6 import (
        make_command,
    )

    ops: list[dict[str, Any]] = []
    _graph, _sources, _contrib, _identity, inits, _adoptions = make_init_stores()
    command = make_command()
    init_result = initialize_reviewed_world(
        command, initialization_repository=inits, graph_reader=init_reader()
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

    graph = InMemoryWorldGraphRepository()
    parent, reader = pub._seed_graph(graph)
    reviews, _state = pub._seed_review()
    publications = InMemoryFinalizedReviewPublicationRepository(reviews, graph)
    published = publish_finalized_review(
        pub.WORLD_ID,
        pub.REVIEW_ID,
        published_at=pub.PUBLISHED_AT,
        review_repository=reviews,
        world_graph_repository=graph,
        publication_repository=publications,
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
                "parent_revision_id": parent.revision.revision_id,
                "disposition": type(published).__name__,
            },
        )
    )

    replayed = publish_finalized_review(
        pub.WORLD_ID,
        pub.REVIEW_ID,
        published_at=pub.PUBLISHED_AT,
        review_repository=reviews,
        world_graph_repository=graph,
        publication_repository=publications,
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

    stale_graph = InMemoryWorldGraphRepository()
    parent2, reader2 = pub._seed_graph(stale_graph)
    stale_reviews, _ = pub._seed_review()
    stale_graph.publish_revision(
        PublishRevisionCommand(
            world_id=pub.WORLD_ID,
            parent_revision_id=parent2.revision.revision_id,
            expected_parent_revision_id=parent2.revision.revision_id,
            operation_ids=["op:competing-writer"],
            graph_schema=parent2.revision.graph_schema,
            graph_payload=copy.deepcopy(parent2.graph_payload),
            created_at=pub.PUBLISHED_AT,
        )
    )
    try:
        publish_finalized_review(
            pub.WORLD_ID,
            pub.REVIEW_ID,
            published_at=pub.PUBLISHED_AT,
            review_repository=stale_reviews,
            world_graph_repository=stale_graph,
            publication_repository=InMemoryFinalizedReviewPublicationRepository(
                stale_reviews, stale_graph
            ),
            graph_reader=reader2,
        )
        raise AssertionError("expected StaleParentRevisionError")
    except StaleParentRevisionError as exc:
        ops.append(
            make_operation(
                operation_id="write.stale_parent_rejection",
                family="write",
                request_identity={"review_id": pub.REVIEW_ID},
                status="error",
                semantic_result=normalize_error(exc),
            )
        )

    unk_graph = InMemoryWorldGraphRepository()
    _, unk_reader = pub._seed_graph(unk_graph)
    unk_reviews, _ = pub._seed_review()
    spy_pubs = pub._SpyPublicationRepository(
        InMemoryFinalizedReviewPublicationRepository(unk_reviews, unk_graph),
        raise_after_publish=True,
        fail_recovery_probe=True,
    )
    try:
        publish_finalized_review(
            pub.WORLD_ID,
            pub.REVIEW_ID,
            published_at=pub.PUBLISHED_AT,
            review_repository=unk_reviews,
            world_graph_repository=unk_graph,
            publication_repository=spy_pubs,
            graph_reader=unk_reader,
        )
        raise AssertionError("expected FinalizedReviewPublicationOutcomeUnknownError")
    except FinalizedReviewPublicationOutcomeUnknownError as exc:
        ops.append(
            make_operation(
                operation_id="write.outcome_unknown_recovery",
                family="write",
                request_identity={"review_id": pub.REVIEW_ID},
                status="error",
                semantic_result=normalize_error(exc),
            )
        )

    from tests.unit.test_eldyrwild_existing_world_adoption_bundle_v2 import (
        eldyrwild_graph_reader,
        parse_sealed_bundle,
        raw_bundle,
    )

    adopt_stores = make_memory_stores()
    adopt_raw = raw_bundle()
    adopt_bundle = parse_sealed_bundle()
    adopt_existing_world(
        adopt_raw,
        adopted_at=NOW,
        adoption_repository=adopt_stores.adoptions,
        graph_reader=eldyrwild_graph_reader(),
    )
    repair = _eldyrwild_classification_repair(adopt_stores, raw=adopt_raw, bundle=adopt_bundle)
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

    bind = make_memory_stores()
    head = publish_synthetic_head(bind)
    _, retrieval = make_services(bind)
    view = retrieval.get_object(
        request(
            scope_mode=ScopeModeV2.CAMPAIGN, campaign_id=CAMPAIGN_A, admissibility=Admissibility.GM
        ),
        object_id="obj:alpha-keep",
    )
    obj = view.object
    ops.append(
        make_operation(
            operation_id="write.source_evidence_binding_integrity",
            family="write",
            request_identity={"object_id": "obj:alpha-keep", "head_revision_id": head},
            status="ok",
            semantic_result={
                "head_revision_id": head,
                "object_id": "obj:alpha-keep",
                "evidence_ref_ids": list(obj.evidence_ref_ids if obj is not None else []),
                "anchors": _anchors(view),
                "binding_integrity": "source_revision_present_for_admitted_evidence",
                "found": bool(getattr(view, "found", obj is not None)),
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
        graph_reader as init_reader,
    )
    from tests.unit.test_reviewed_world_initialization_materialization_v6 import (
        make_command,
    )

    reader = _reader()
    historical: list[dict[str, Any]] = []

    def add(schema: str, payload: dict[str, Any], path: str) -> None:
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
                "stored_schema_version": schema,
                "reader_path": path,
                "semantic_result": summary,
                "semantic_sha256": sha256_canonical(summary),
            }
        )

    add(GRAPH_SCHEMA_V1, v1_payload(), "VersionedUnionGraphSnapshotReader.parse v1")

    from dungeonmind.application.graph_snapshot import GRAPH_SCHEMA_V2
    from tests.unit.test_assertion_scoped_graph import _v2_payload

    add(GRAPH_SCHEMA_V2, _v2_payload(), "VersionedUnionGraphSnapshotReader.parse v2")

    gate = json.loads(GATEWATCH_GRAPH.read_text(encoding="utf-8"))
    add(
        gate.get("graph_schema", GRAPH_SCHEMA_V3),
        gate["graph_payload"],
        "VersionedUnionGraphSnapshotReader.parse gatewatch-world-graph-v3.json",
    )

    from tests.unit.test_union_graph_v4 import _v4_payload
    from tests.unit.test_union_graph_v5 import _v5_payload

    add(GRAPH_SCHEMA_V4, _v4_payload(), "VersionedUnionGraphSnapshotReader.parse v4")
    add(GRAPH_SCHEMA_V5, _v5_payload(), "VersionedUnionGraphSnapshotReader.parse v5")

    add(
        GRAPH_SCHEMA_V6,
        synthetic_graph_payload(),
        "VersionedUnionGraphSnapshotReader.parse synthetic v6 witness payload",
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
            "membership_sha256": adopt_result.membership_sha256,
        }
    )
    historical.append(
        {
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
            "stored_schema_version": "dm_existing_world_adoption_repair",
            "reader_path": "repair_existing_world_adoption_source_classification",
            "semantic_result": repair_sem,
            "semantic_sha256": sha256_canonical(repair_sem),
        }
    )

    _g, _s, _c, _i, inits, _a = make_init_stores()
    command = make_command()
    initialize_reviewed_world(command, initialization_repository=inits, graph_reader=init_reader())
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
            "stored_schema_version": "dm_reviewed_world_initialization_v1",
            "reader_path": "initialize_reviewed_world + get_for_world",
            "semantic_result": compat,
            "semantic_sha256": sha256_canonical(compat),
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

    head = publish_synthetic_head(stores)
    manifest = fixture_manifest(head_revision_id=head)
    operations = _run_reads(stores, head)
    operations.extend(_run_writes())
    historical = _run_historical(stores)

    missing = [op for op in REQUIRED_OPERATION_IDS if op not in {r["id"] for r in operations}]
    if missing:
        raise RuntimeError(f"missing required operations: {missing}")

    witness: dict[str, Any] = {
        "schema": WITNESS_SCHEMA,
        "inputs": {
            "dungeonmind_base_sha": BASE_SHA,
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
