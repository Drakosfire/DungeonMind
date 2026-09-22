#!/usr/bin/env -S uv run python
"""Preflight and explicitly gated repair of Eldyrwild party-registry evidence."""
from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime

from dungeonmind.application.eldyrwild_party_registry_provenance_repair import (
    ELDYRWILD_WORLD_ID,
    EXPECTED_PARENT_REVISION_ID,
    materialize_party_registry_provenance_repair,
    publish_party_registry_provenance_repair,
)
from dungeonmind.application.graph_snapshot import VersionedUnionGraphSnapshotReader
from dungeonmind.application.semantic_profiles import StaticSemanticProfileRegistry
from dungeonmind.application.world_graph_projection import WorldGraphProjectionService
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.projection_v2 import ScopeModeV2, WorldGraphProjectionRequestV2
from dungeonmind.infrastructure.postgres import PostgresDatabase, PostgresRepositoryBundle
from dungeonmind_dnd.application.world_object_vocabulary import load_builtin_v3_descriptor


def _bundle(url: str) -> PostgresRepositoryBundle:
    return PostgresRepositoryBundle(PostgresDatabase(url))


def _url(value: str) -> str:
    return value or os.environ.get("DUNGEONMIND_WORLD_GRAPH_AUTHORITY_DATABASE_URL", "")


def _preflight(bundle: PostgresRepositoryBundle) -> dict[str, object]:
    head = bundle.world_graph.get_head(ELDYRWILD_WORLD_ID)
    parent = bundle.world_graph.get_revision(ELDYRWILD_WORLD_ID, EXPECTED_PARENT_REVISION_ID)
    if head is None or parent is None:
        raise SystemExit("STOP: expected Eldyrwild head or immutable parent is missing")
    materialized = materialize_party_registry_provenance_repair(parent, sources=bundle.sources)
    return {
        "world": ELDYRWILD_WORLD_ID,
        "head": head.head_revision_id,
        "expected_parent": EXPECTED_PARENT_REVISION_ID,
        "parent_matches_head": head.head_revision_id == EXPECTED_PARENT_REVISION_ID,
        "corrected_evidence_ref_ids": list(materialized.corrected_evidence_ref_ids),
        "expected_child": materialized.expected_child_revision_id,
        "ready_to_apply": head.head_revision_id == EXPECTED_PARENT_REVISION_ID,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "apply", "prove"))
    parser.add_argument("--database-url", default="")
    parser.add_argument("--confirm-apply", action="store_true")
    args = parser.parse_args()
    url = _url(args.database_url)
    if not url:
        raise SystemExit("DUNGEONMIND_WORLD_GRAPH_AUTHORITY_DATABASE_URL is required")
    bundle = _bundle(url)
    preflight = _preflight(bundle)
    if args.command == "preflight":
        print(json.dumps(preflight, indent=2, sort_keys=True))
        return 0 if preflight["ready_to_apply"] else 2
    if args.command == "apply":
        if not args.confirm_apply:
            print(json.dumps({"apply_gate": "pending", "preflight": preflight}, indent=2))
            return 3
        result = publish_party_registry_provenance_repair(
            bundle.world_graph, sources=bundle.sources, created_at=datetime.now(UTC)
        )
        print(json.dumps({"apply_gate": "executed", **result.__dict__}, indent=2, default=str))
        return 0
    projection = WorldGraphProjectionService(
        world_graph=bundle.world_graph,
        sources=bundle.sources,
        graph_reader=VersionedUnionGraphSnapshotReader(
            profile_registry=StaticSemanticProfileRegistry([load_builtin_v3_descriptor()])
        ),
        reviewed_world_initializations=bundle.reviewed_world_initializations,
    ).project(WorldGraphProjectionRequestV2(
        world_id=ELDYRWILD_WORLD_ID,
        campaign_id=None,
        admissibility=Admissibility.GM,
        scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN,
        revision_pin=str(preflight["expected_child"]),
    ))
    admitted = set(projection.graph.objects)
    result = {"preflight": preflight, "six_pc_admitted": sorted(
        object_id for object_id in (
            "pc:baergrom", "pc:bonogo", "pc:caelynn", "pc:ephanna", "pc:karsemine", "pc:stafl"
        ) if object_id in admitted
    ), "admitted_object_count": len(admitted)}
    print(json.dumps(result, indent=2))
    return 0 if len(result["six_pc_admitted"]) == 6 else 2


if __name__ == "__main__":
    raise SystemExit(main())
