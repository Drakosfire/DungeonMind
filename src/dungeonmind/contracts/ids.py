"""Opaque identifier helpers.

IDs are stable, randomly generated (or content-addressed), and never derived
from labels, names, or array positions. Callers must treat every ID as an
opaque string: no parsing, no semantic inference, no tenancy or authorization
meaning.
"""

import uuid

# Entity prefixes in use (convention, not a registry — IDs stay opaque):
#   world, rev (content-addressed, see domain.revision_ids), ctr (contribution),
#   evd (evidence ref), src (source artifact), srev (source revision),
#   dec (identity decision), ses (retrieval session), thr (mind thread),
#   turn (mind turn), sdoc (semantic document), erun (embedding run),
#   req (request), pol (capability policy), anchor, claim, op


def new_id(prefix: str) -> str:
    """Return a fresh opaque ID with a human-sortable prefix, e.g. ``world:a1b2...``."""
    if not prefix or ":" in prefix:
        raise ValueError("prefix must be non-empty and contain no ':'")
    return f"{prefix}:{uuid.uuid4().hex}"
