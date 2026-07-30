"""Content-addressed revision identity.

A revision id commits to: the world, the declared parent, the operation set,
the graph schema, and the canonical payload hash. Same inputs → same id; any
semantic change → a different id. The id is 32 hex chars of SHA-256 (128
bits), which keeps ids readable while collision probability stays negligible
at any realistic revision count. This is a DungeonMind-native choice;
DungeonMindBuddy compatibility, if ever needed, is a mapping layer, not a
reason to change this function.
"""

from .canonical import canonical_sha256

REVISION_ID_PREFIX = "rev"
REVISION_ID_HEX_LENGTH = 32


def compute_revision_id(
    *,
    world_id: str,
    parent_revision_id: str | None,
    operation_ids: list[str],
    graph_schema: str,
    graph_payload_sha256: str,
) -> str:
    """Return ``rev:<sha256-32>`` over the canonical identity material.

    ``operation_ids`` order is significant and preserved: callers pass the
    ordered operations that produced the revision.
    """
    material = {
        "world_id": world_id,
        "parent_revision_id": parent_revision_id,
        "operation_ids": list(operation_ids),
        "graph_schema": graph_schema,
        "graph_payload_sha256": graph_payload_sha256,
    }
    return f"{REVISION_ID_PREFIX}:{canonical_sha256(material)[:REVISION_ID_HEX_LENGTH]}"
