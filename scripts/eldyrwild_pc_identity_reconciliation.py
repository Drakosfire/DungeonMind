#!/usr/bin/env -S uv run python
"""Preflight, apply, and prove the bounded Eldyrwild six-PC reconciliation.

The ``apply`` command requires ``--confirm-apply``.  Without that explicit
operator flag this script only reads the current World and materializes the
expected child in memory.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from typing import Any

from dungeonmind.application.eldyrwild_pc_identity_reconciliation import (
    ELDYRWILD_WORLD_ID,
    EldyrwildPcIdentityPreflight,
    apply_eldyrwild_pc_identity_reconciliation,
    materialize_from_persisted_reconciliation,
    preflight_eldyrwild_pc_identity_reconciliation,
)
from dungeonmind.application.world_identity_reconciliation import (
    CanonicalRebindRequest,
    publish_identity_reconciliation,
)
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.postgres import PostgresDatabase, PostgresRepositoryBundle


def _bundle(database_url: str) -> tuple[PostgresDatabase, PostgresRepositoryBundle]:
    database = PostgresDatabase(database_url)
    return database, PostgresRepositoryBundle(database)


def _database_url(value: str) -> str:
    resolved = value or os.environ.get("DUNGEONMIND_WORLD_GRAPH_AUTHORITY_DATABASE_URL", "")
    if not resolved:
        raise SystemExit(
            "error: --database-url or DUNGEONMIND_WORLD_GRAPH_AUTHORITY_DATABASE_URL is required"
        )
    return resolved


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _preflight(
    args: argparse.Namespace,
) -> tuple[PostgresRepositoryBundle, EldyrwildPcIdentityPreflight]:
    _, bundle = _bundle(_database_url(args.database_url))
    return bundle, preflight_eldyrwild_pc_identity_reconciliation(
        bundle.world_graph,
        bundle.identity_reconciliation,
        world_id=ELDYRWILD_WORLD_ID,
        operation_id=args.operation_id or None,
        actor=args.actor,
        reason=args.reason,
    )


def _cmd_preflight(args: argparse.Namespace) -> int:
    _, preflight = _preflight(args)
    _print_json(
        {
            "Parent": preflight.parent_revision_id,
            "Six mappings": preflight.summary()["mappings"],
            "Objects affected": len(preflight.mappings),
            "Relationships affected": len(preflight.affected_relationship_ids),
            "Evidence preserved": len(preflight.affected_evidence_ref_ids),
            "Expected child": preflight.expected_child_revision_id,
            "Atomicity/retry proof": {
                "decision_ids": [
                    decision.decision_id for decision in preflight.materialization.decisions
                ],
                "exact_retry": "same operation returns already_applied",
                "stale_parent": "fails before mutation",
            },
            "Ready to apply": preflight.ready_to_apply,
            "details": preflight.summary(),
        }
    )
    return 0 if preflight.ready_to_apply else 2


def _cmd_apply(args: argparse.Namespace) -> int:
    bundle, preflight = _preflight(args)
    if not args.confirm_apply:
        _print_json(
            {
                "apply_gate": "pending",
                "message": "Read-only preflight complete; rerun with --confirm-apply to publish.",
                "preflight": preflight.summary(),
            }
        )
        return 3
    if not preflight.ready_to_apply:
        _print_json(
            {
                "apply_gate": "blocked",
                "reason": "unexpected existing reconciliation history",
                "preflight": preflight.summary(),
            }
        )
        return 2
    result = apply_eldyrwild_pc_identity_reconciliation(
        preflight,
        bundle.world_graph,
        bundle.identity_reconciliation,
        actor=args.actor,
        reason=args.reason,
        published_at=datetime.now(tz=UTC),
    )
    _print_json(
        {
            "apply_gate": "executed",
            "world_id": result.world_id,
            "operation_id": result.operation_id,
            "parent_revision": result.parent_revision_id,
            "child_revision": result.published_revision_id,
            "decision_ids": list(result.decision_ids),
            "already_applied": result.already_applied,
        }
    )
    return 0


def _row_counts(database: PostgresDatabase, world_id: str) -> dict[str, int]:
    with database.connect() as conn:
        return {
            "revisions": conn.execute(
                "SELECT COUNT(*) AS count FROM dungeonmind.graph_revisions WHERE world_id = %s",
                (world_id,),
            ).fetchone()["count"],
            "head_events": conn.execute(
                "SELECT COUNT(*) AS count FROM dungeonmind.world_graph_head_events "
                "WHERE world_id = %s",
                (world_id,),
            ).fetchone()["count"],
            "decisions": conn.execute(
                "SELECT COUNT(*) AS count FROM dungeonmind.identity_decisions WHERE world_id = %s",
                (world_id,),
            ).fetchone()["count"],
        }


def _cmd_prove(args: argparse.Namespace) -> int:
    database, bundle = _bundle(_database_url(args.database_url))
    parent = bundle.world_graph.get_revision(ELDYRWILD_WORLD_ID, args.parent_revision)
    child = bundle.world_graph.get_revision(ELDYRWILD_WORLD_ID, args.child_revision)
    if parent is None or child is None:
        raise SystemExit("error: parent or child revision was not found")
    decisions = bundle.identity_reconciliation.list_for_world(ELDYRWILD_WORLD_ID)
    if args.operation_id:
        decisions = [item for item in decisions if item.operation_id == args.operation_id]
    if len(decisions) != 6:
        raise SystemExit(
            "error: expected exactly six persisted reconciliation decisions, "
            f"got {len(decisions)}"
        )

    replay = materialize_from_persisted_reconciliation(parent, decisions)
    child_ids = {record["object_id"] for record in child.graph_payload["objects"]}
    target_ids = {decision.target_object_id for decision in decisions}
    source_ids = {decision.source_object_id for decision in decisions}
    relationship_endpoints = {
        endpoint
        for relationship in child.graph_payload["relationships"]
        for endpoint in (relationship["source_object_id"], relationship["target_object_id"])
    }
    dangling = sorted(relationship_endpoints - child_ids)
    before_retry = _row_counts(database, ELDYRWILD_WORLD_ID)
    retry = publish_identity_reconciliation(
        ELDYRWILD_WORLD_ID,
        args.parent_revision,
        decisions[0].operation_id,
        [
            CanonicalRebindRequest(item.source_object_id, item.target_object_id)
            for item in decisions
        ],
        actor=decisions[0].actor,
        reason=decisions[0].reason,
        published_at=datetime.now(tz=UTC),
        world_graph_repository=bundle.world_graph,
        reconciliation_repository=bundle.identity_reconciliation,
    )
    after_retry = _row_counts(database, ELDYRWILD_WORLD_ID)
    head = bundle.world_graph.get_head(ELDYRWILD_WORLD_ID)
    _print_json(
        {
            "head_before": args.parent_revision,
            "head_after": None if head is None else head.head_revision_id,
            "child_revision": child.revision.revision_id,
            "six_pc_targets_present": target_ids <= child_ids,
            "legacy_sources_absent": not source_ids & child_ids,
            "relationships_resolve": not dangling,
            "evidence_preserved": (
                child.graph_payload["evidence_refs"] == parent.graph_payload["evidence_refs"]
            ),
            "persisted_decision_ids": [item.decision_id for item in decisions],
            "replay_matches_child": replay.graph_payload == child.graph_payload,
            "retry": {
                "already_applied": retry.already_applied,
                "child_revision": retry.published_revision_id,
                "counts_unchanged": before_retry == after_retry,
            },
            "proof_ready": (
                head is not None
                and head.head_revision_id == args.child_revision
                and target_ids <= child_ids
                and not source_ids & child_ids
                and not dangling
                and child.graph_payload["evidence_refs"] == parent.graph_payload["evidence_refs"]
                and replay.graph_payload == child.graph_payload
                and retry.already_applied
                and before_retry == after_retry
            ),
        }
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("preflight", "apply"):
        command = subparsers.add_parser(name)
        command.add_argument("--database-url", default="")
        command.add_argument("--operation-id", default="")
        command.add_argument("--actor", default="steward")
        command.add_argument(
            "--reason",
            default="reconcile Eldyrwild PC identities to the canonical pc namespace",
        )
        if name == "apply":
            command.add_argument(
                "--confirm-apply",
                action="store_true",
                help="explicitly authorize the single atomic live publication",
            )
        command.set_defaults(func=_cmd_preflight if name == "preflight" else _cmd_apply)
    prove = subparsers.add_parser("prove")
    prove.add_argument("--database-url", default="")
    prove.add_argument("--parent-revision", required=True)
    prove.add_argument("--child-revision", required=True)
    prove.add_argument("--operation-id", default="")
    prove.set_defaults(func=_cmd_prove)
    return parser


def main() -> int:
    parsed_args = _parser().parse_args()
    try:
        return parsed_args.func(parsed_args)
    except PersistenceIntegrityError as error:
        _print_json(
            {
                "status": "STOP",
                "error": str(error),
                "details": error.details,
            }
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
