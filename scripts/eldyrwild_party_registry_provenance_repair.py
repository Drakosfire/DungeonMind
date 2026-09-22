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
from dungeonmind.infrastructure.postgres import PostgresDatabase, PostgresRepositoryBundle


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
    child = bundle.world_graph.get_revision(ELDYRWILD_WORLD_ID, str(preflight["expected_child"]))
    print(json.dumps({"preflight": preflight, "child_exists": child is not None}, indent=2))
    return 0 if child is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
