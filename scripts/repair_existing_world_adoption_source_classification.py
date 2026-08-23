#!/usr/bin/env -S uv run python
"""Repair the source classification of one already-adopted world (CUTOVER R.2b).

The Eldyrwild adoption bundle v2 producer wrote ``SourceArtifactV2`` rows with
``visibility=None`` (Buddy's kernel serves GM-only reads and never needed an
access-granting classification). DungeonMind's native read path is fail-closed:
v2 artifacts with unset visibility are excluded from scope, which silently
empties every projection of an adopted world.

This CLI repairs the source classification of one already-adopted world through
DungeonMind authority. It is a thin caller of the application seam; it does not
execute SQL and does not mutate source records through a generic mutable API.

Usage:
    uv run python scripts/repair_existing_world_adoption_source_classification.py \
        --database-url postgresql://... --world-id eldyrwild \
        --bundle-path tests/fixtures/dungeonmind_dnd/eldyrwild_existing_world_adoption_bundle_v2.json \
        --repair-intent-path /path/to/repair-intent.json --apply
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DUNGEONMIND_WORLD_GRAPH_AUTHORITY_DATABASE_URL", ""),
        help="DungeonMind authority PostgreSQL DSN (or DUNGEONMIND_WORLD_GRAPH_AUTHORITY_DATABASE_URL).",
    )
    parser.add_argument("--world-id", default="eldyrwild")
    parser.add_argument(
        "--bundle-path",
        required=True,
        help="Path to the exact sealed adoption bundle JSON file.",
    )
    parser.add_argument(
        "--repair-intent-path",
        required=True,
        help="Path to the repair intent JSON file.",
    )
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry-run).")
    args = parser.parse_args(argv)

    if not args.database_url:
        print("error: --database-url or DUNGEONMIND_WORLD_GRAPH_AUTHORITY_DATABASE_URL required", file=sys.stderr)
        return 2

    # Load the sealed bundle
    bundle_path = Path(args.bundle_path)
    if not bundle_path.exists():
        print(f"error: bundle file not found: {bundle_path}", file=sys.stderr)
        return 2
    raw_bundle = bundle_path.read_bytes()

    # Load the repair intent
    intent_path = Path(args.repair_intent_path)
    if not intent_path.exists():
        print(f"error: repair intent file not found: {intent_path}", file=sys.stderr)
        return 2
    intent_payload = json.loads(intent_path.read_text())

    from dungeonmind.contracts.existing_world_adoption_repair import (
        ExistingWorldAdoptionSourceClassificationRepairIntentV1,
    )

    try:
        repair_intent = ExistingWorldAdoptionSourceClassificationRepairIntentV1.model_validate(
            intent_payload
        )
    except Exception as exc:
        print(f"error: repair intent validation failed: {exc}", file=sys.stderr)
        return 2

    # Validate the repair intent against the world ID
    if repair_intent.world_id != args.world_id:
        print(
            f"error: repair intent world_id {repair_intent.world_id!r} does not match --world-id {args.world_id!r}",
            file=sys.stderr,
        )
        return 2

    # Print the repair intent
    print(f"world={args.world_id}: {len(repair_intent.repairs)} repairs requested")
    for repair in repair_intent.repairs:
        operations = []
        if repair.set_visibility_to_gm:
            operations.append("set_visibility_to_gm")
        if repair.clear_campaign_id:
            operations.append("clear_campaign_id")
        print(f"  {repair.source_artifact_id}: {', '.join(operations)}")

    if not args.apply:
        print("dry-run: no changes written")
        return 0

    # Apply the repair through DungeonMind authority
    from dungeonmind.application.existing_world_adoption_repair import (
        repair_existing_world_adoption_source_classification,
    )
    from dungeonmind.application.graph_snapshot import GraphSnapshotReader
    from dungeonmind.infrastructure.postgres.database import PostgresDatabase
    from dungeonmind.infrastructure.postgres.existing_world_adoption import (
        PostgresExistingWorldAdoptionRepository,
    )

    database = PostgresDatabase(args.database_url)
    adoption_repository = PostgresExistingWorldAdoptionRepository(database)
    graph_reader = GraphSnapshotReader()

    repaired_at = datetime.now(timezone.utc)
    try:
        receipt = repair_existing_world_adoption_source_classification(
            raw_bundle,
            repair_intent=repair_intent,
            repaired_at=repaired_at,
            adoption_repository=adoption_repository,
            graph_reader=graph_reader,
        )
    except Exception as exc:
        print(f"error: repair failed: {exc}", file=sys.stderr)
        return 1

    print(f"repair applied: receipt schema={receipt.schema_version}")
    print(f"  membership_sha256={receipt.membership_sha256}")
    print(f"  effective_membership_sha256={receipt.effective_membership_sha256}")
    return 0


if __name__ == "__main__":
    sys.exit(main())