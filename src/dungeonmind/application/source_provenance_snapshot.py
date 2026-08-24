"""Coherent source/provenance snapshot for one World Graph read (R.3a).

A scoped projection consults live source identity: artifact existence,
ownership, visibility, lifecycle, domain, and bound revisions. Loading those
records one-at-a-time is the N+1 that dominates real DungeonMind reads.

This module is the transport-neutral snapshot those reads consume:

* application-contract records only (never SQL rows or driver objects);
* immutable for the duration of one coherent read — backing maps are private,
  public mappings and accessors return isolated copies, and mutating a
  returned model cannot change fingerprint or later lookup/read behavior;
* missing artifacts/revisions stay missing (fail closed exactly as R.3);
* only the artifact/revision IDs referenced by the selected graph revision
  are requested — source bodies are never loaded.

The snapshot is a lookup, not durable authority and not a scoped-projection
cache key. A fingerprint exists for tests and future safe caching; R.3a does
not cache authorized projections from it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TypeVar

from ..contracts.base import DungeonMindModel
from ..contracts.evidence import SourceArtifactRecord, SourceRevision
from ..domain.canonical import canonical_sha256
from .graph_snapshot import ParsedGraphSnapshot

_TRecord = TypeVar("_TRecord", bound=DungeonMindModel)


def provenance_refs_from_parsed_graph(
    snapshot: ParsedGraphSnapshot,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Distinct artifact and source-revision IDs referenced by graph evidence."""

    artifact_ids: set[str] = set()
    revision_ids: set[str] = set()
    for record in snapshot.evidence.values():
        artifact_ids.add(record.source_artifact_id)
        if record.source_revision_id:
            revision_ids.add(record.source_revision_id)
    return tuple(sorted(artifact_ids)), tuple(sorted(revision_ids))


def source_provenance_fingerprint(
    *,
    artifacts: Mapping[str, SourceArtifactRecord],
    revisions: Mapping[str, SourceRevision],
    missing_artifact_ids: frozenset[str],
    missing_revision_ids: frozenset[str],
) -> str:
    """Deterministic digest of one coherent source/provenance view."""

    return canonical_sha256(
        {
            "artifacts": {
                artifact_id: artifact.model_dump(mode="json")
                for artifact_id, artifact in sorted(artifacts.items())
            },
            "revisions": {
                revision_id: revision.model_dump(mode="json")
                for revision_id, revision in sorted(revisions.items())
            },
            "missing_artifact_ids": sorted(missing_artifact_ids),
            "missing_revision_ids": sorted(missing_revision_ids),
        }
    )


def _isolated_record_map(
    records: Mapping[str, _TRecord],
) -> MappingProxyType[str, _TRecord]:
    return MappingProxyType(
        {
            record_id: record.model_copy(deep=True)
            for record_id, record in records.items()
        }
    )


@dataclass(frozen=True)
class SourceProvenanceSnapshot:
    """Immutable application-contract view of requested source identity.

    Backing artifact/revision maps are private. Public ``artifacts`` /
    ``revisions`` mappings and ``get_artifact`` / ``get_revision`` return
    isolated copies. Mutating a model obtained through any of those surfaces
    cannot change this snapshot's fingerprint or any later read.
    """

    requested_artifact_ids: frozenset[str]
    requested_revision_ids: frozenset[str]
    fingerprint: str
    _artifacts: Mapping[str, SourceArtifactRecord] = field(repr=False)
    _revisions: Mapping[str, SourceRevision] = field(repr=False)

    @classmethod
    def from_loaded(
        cls,
        *,
        requested_artifact_ids: frozenset[str],
        requested_revision_ids: frozenset[str],
        artifacts: Mapping[str, SourceArtifactRecord],
        revisions: Mapping[str, SourceRevision],
    ) -> SourceProvenanceSnapshot:
        missing_artifacts = requested_artifact_ids - frozenset(artifacts)
        missing_revisions = requested_revision_ids - frozenset(revisions)
        isolated_artifacts = _isolated_record_map(artifacts)
        isolated_revisions = _isolated_record_map(revisions)
        return cls(
            requested_artifact_ids=requested_artifact_ids,
            requested_revision_ids=requested_revision_ids,
            fingerprint=source_provenance_fingerprint(
                artifacts=isolated_artifacts,
                revisions=isolated_revisions,
                missing_artifact_ids=missing_artifacts,
                missing_revision_ids=missing_revisions,
            ),
            _artifacts=isolated_artifacts,
            _revisions=isolated_revisions,
        )

    @property
    def artifacts(self) -> Mapping[str, SourceArtifactRecord]:
        return _isolated_record_map(self._artifacts)

    @property
    def revisions(self) -> Mapping[str, SourceRevision]:
        return _isolated_record_map(self._revisions)

    @property
    def artifact_count(self) -> int:
        return len(self._artifacts)

    @property
    def revision_count(self) -> int:
        return len(self._revisions)

    @property
    def missing_artifact_count(self) -> int:
        return len(self.requested_artifact_ids) - len(self._artifacts)

    @property
    def missing_revision_count(self) -> int:
        return len(self.requested_revision_ids) - len(self._revisions)

    def get_artifact(self, source_artifact_id: str) -> SourceArtifactRecord | None:
        artifact = self._artifacts.get(source_artifact_id)
        if artifact is None:
            return None
        return artifact.model_copy(deep=True)

    def get_revision(self, source_revision_id: str) -> SourceRevision | None:
        revision = self._revisions.get(source_revision_id)
        if revision is None:
            return None
        return revision.model_copy(deep=True)


__all__ = [
    "SourceProvenanceSnapshot",
    "provenance_refs_from_parsed_graph",
    "source_provenance_fingerprint",
]
