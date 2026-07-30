"""Shared test factories. All timestamps are fixed for determinism."""

from datetime import UTC, datetime

from dungeonmind.contracts import PublishRevisionCommand

FIXED_NOW = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)
FIXED_LATER = datetime(2026, 7, 29, 13, 0, 0, tzinfo=UTC)

WORLD_ID = "world:demo-atlas"
GRAPH_SCHEMA = "dm_union_graph_v1"


def make_publish(
    world_id: str = WORLD_ID,
    *,
    parent: str | None = None,
    expected: str | None = None,
    operation_ids: list[str] | None = None,
    payload: dict[str, object] | None = None,
    created_at: datetime = FIXED_NOW,
) -> PublishRevisionCommand:
    """Build a publish command.

    Normal publication requires parent == expected. If only one of ``parent`` /
    ``expected`` is provided, the other is mirrored so the command is valid.
    """
    if parent is not None and expected is None:
        expected = parent
    elif expected is not None and parent is None:
        parent = expected
    return PublishRevisionCommand(
        world_id=world_id,
        parent_revision_id=parent,
        expected_parent_revision_id=expected,
        operation_ids=operation_ids or ["op:bootstrap"],
        graph_schema=GRAPH_SCHEMA,
        graph_payload=payload if payload is not None else {"world_id": world_id, "nodes": []},
        created_at=created_at,
    )
