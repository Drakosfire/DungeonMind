"""Opt-in compact index for the Core read benchmark.

The expected manifest comes from a trusted offline builder and is kept
independently of the artifact. An artifact cannot vouch for its own contents.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from dungeonmind.application.vnext._read_artifact import parse_verified_source_rows

FIELDS = (
    "assertions_by_subject",
    "entity_ref_outgoing",
    "entity_ref_incoming",
    "entity_ref_outgoing_assertions",
    "entity_ref_incoming_assertions",
    "entity_adjacency",
    "assertion_evidence",
    "evidence_supporters",
    "aliases_by_entity",
    "alias_exact_index",
    "literal_exact_index",
    "lexical_candidate_index",
    "lexical_assertion_index",
    "predicate_assertion_index",
    "term_ref_assertion_index",
)
FORMAT = "DMIDX001"


@dataclass(frozen=True)
class Manifest:
    format: str
    space_id: str
    revision_id: str
    payload_sha256: str
    index_sha256: str
    semantic_digest: str


def encode(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode()


def prefix(field):
    return field.encode("ascii") + b"\0"


def build(extension, parsed):
    data = extension.build([
        (prefix(field) + encode(key), encode(value))
        for field in FIELDS
        for key, value in getattr(parsed, field).items()
    ])
    return data, Manifest(
        FORMAT, parsed.space_id, parsed.revision_id, parsed.graph_payload_sha256,
        sha256(data).hexdigest(), parsed.semantic_digest,
    )


class Postings(Mapping):
    __slots__ = ("_index", "_prefix")

    def __init__(self, index, field):
        object.__setattr__(self, "_index", index)
        object.__setattr__(self, "_prefix", prefix(field))

    def __setattr__(self, name, value):
        raise TypeError("postings are immutable")

    def __delattr__(self, name):
        raise TypeError("postings are immutable")

    def __getitem__(self, key):
        value = self._index.get(self._prefix + encode(key))
        if value is None:
            raise KeyError(key)
        return tuple(json.loads(value))

    def __iter__(self):
        keys = (json.loads(key) for key in self._index.keys(self._prefix))
        return iter(sorted(
            (tuple(key) if isinstance(key, list) else key for key in keys),
            key=str,
        ))

    def __len__(self):
        return len(self._index.keys(self._prefix))


def parse(extension, stored, rows, artifact: Path, expected: Manifest):
    """Open postings only after the exact revision has passed Core verification."""
    revision = stored.revision
    if (expected.format, expected.space_id, expected.revision_id, expected.payload_sha256) != (
        FORMAT, revision.space_id, revision.revision_id, revision.graph_payload_sha256,
    ):
        raise ValueError("compact index revision binding mismatch")
    data = artifact.read_bytes()
    if sha256(data).hexdigest() != expected.index_sha256:
        raise ValueError("compact index differs from trusted artifact digest")
    index = extension.Index(data)
    parsed = parse_verified_source_rows(
        stored, rows, _verified_indexes={field: Postings(index, field) for field in FIELDS},
    )
    if parsed is None or parsed.semantic_digest != expected.semantic_digest:
        raise ValueError("compact index semantic binding mismatch")
    return parsed
