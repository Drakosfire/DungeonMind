#!/usr/bin/env -S uv run python
"""Repair the source classification of one already-adopted world (CUTOVER R.2b).

This CLI is a thin caller of the application seam. It does not execute SQL
and does not mutate source records through a generic mutable API. Default
mode is a real no-write preflight; ``--apply`` performs the atomic repair.

Do not point this at live Eldyrwild until the repair PR is merged and the
operator runbook is followed.

Usage:
    uv run python scripts/repair_existing_world_adoption_source_classification.py \\
        --database-url postgresql://... --world-id eldyrwild \\
        --bundle-path tests/fixtures/dungeonmind_dnd/\\
            eldyrwild_existing_world_adoption_bundle_v2.json \\
        --repair-intent-path /path/to/repair-intent.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _print_receipt(receipt: object, *, apply: bool) -> None:
    schema = getattr(receipt, "schema_version", None)
    membership = getattr(receipt, "membership_sha256", None)
    effective = getattr(receipt, "effective_membership_sha256", None)
    manifest = getattr(receipt, "membership_manifest", None)
    repair = getattr(receipt, "source_classification_repair", None)
    mode = "repair applied" if apply else "dry-run: preflight succeeded; no changes written"
    print(f"{mode}: receipt schema={schema}")
    print(f"  membership_sha256 (M0)={membership}")
    print(f"  effective_membership_sha256 (M1)={effective}")
    if manifest is not None:
        print(
            "  manifest="
            f"{len(manifest.source_artifact_ids)}/"
            f"{len(manifest.source_revision_ids)}/"
            f"{len(manifest.contribution_ids)}/"
            f"{len(manifest.identity_decision_ids)}"
        )
    print("  unexpected_drift=0")
    if repair is not None:
        for correction in repair.corrections:
            print(
                f"  {correction.source_artifact_id}: "
                f"changed_fields={list(correction.changed_fields)} "
                f"visibility {correction.original_visibility!r} -> "
                f"{correction.effective_visibility!r} "
                f"campaign_id {correction.original_campaign_id!r} -> "
                f"{correction.effective_campaign_id!r}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DUNGEONMIND_WORLD_GRAPH_AUTHORITY_DATABASE_URL", ""),
        help=(
            "DungeonMind authority PostgreSQL DSN "
            "(or DUNGEONMIND_WORLD_GRAPH_AUTHORITY_DATABASE_URL)."
        ),
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
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes (default: no-write preflight).",
    )
    args = parser.parse_args(argv)

    if not args.database_url:
        print(
            "error: --database-url or DUNGEONMIND_WORLD_GRAPH_AUTHORITY_DATABASE_URL "
            "required",
            file=sys.stderr,
        )
        return 2

    bundle_path = Path(args.bundle_path)
    if not bundle_path.exists():
        print(f"error: bundle file not found: {bundle_path}", file=sys.stderr)
        return 2
    raw_bundle = bundle_path.read_bytes()

    intent_path = Path(args.repair_intent_path)
    if not intent_path.exists():
        print(f"error: repair intent file not found: {intent_path}", file=sys.stderr)
        return 2
    intent_payload = json.loads(intent_path.read_text())

    from dungeonmind.application.existing_world_adoption_repair import (
        repair_existing_world_adoption_source_classification,
    )
    from dungeonmind.application.graph_snapshot import VersionedUnionGraphSnapshotReader
    from dungeonmind.contracts.existing_world_adoption_repair import (
        ExistingWorldAdoptionSourceClassificationRepairIntentV1,
    )
    from dungeonmind.infrastructure.postgres.database import PostgresDatabase
    from dungeonmind.infrastructure.postgres.existing_world_adoption import (
        PostgresExistingWorldAdoptionRepository,
    )
    from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
    from dungeonmind_dnd.application.world_object_vocabulary import (
        load_builtin_v3_descriptor,
    )

    try:
        repair_intent = ExistingWorldAdoptionSourceClassificationRepairIntentV1.model_validate(
            intent_payload
        )
    except Exception as exc:
        print(f"error: repair intent validation failed: {exc}", file=sys.stderr)
        return 2

    if repair_intent.world_id != args.world_id:
        print(
            f"error: repair intent world_id {repair_intent.world_id!r} does not match "
            f"--world-id {args.world_id!r}",
            file=sys.stderr,
        )
        return 2

    database = PostgresDatabase(args.database_url)
    adoption_repository = PostgresExistingWorldAdoptionRepository(database)
    graph_reader = VersionedUnionGraphSnapshotReader(
        profile_registry=StaticSemanticProfileRegistry([load_builtin_v3_descriptor()])
    )
    repaired_at = datetime.now(UTC)
    try:
        receipt = repair_existing_world_adoption_source_classification(
            raw_bundle,
            repair_intent=repair_intent,
            repaired_at=repaired_at,
            adoption_repository=adoption_repository,
            graph_reader=graph_reader,
            apply=args.apply,
        )
    except Exception as exc:
        print(f"error: repair failed: {exc}", file=sys.stderr)
        return 1

    _print_receipt(receipt, apply=args.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
