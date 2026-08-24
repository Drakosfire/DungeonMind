"""Coherent source/provenance snapshot for one World Graph read (R.3a).

A scoped projection consults live source identity: artifact existence,
ownership, visibility, lifecycle, domain, and bound revisions. Loading those
records one-at-a-time is the N+1 that dominates real DungeonMind reads.

This module is the transport-neutral snapshot those reads consume:

* application-contract records only (never SQL rows or driver objects);
* immutable for the duration of one coherent read;
* missing artifacts/revisions stay missing (fail closed exactly as R.3);
* only the artifact/revision IDs referenced by the selected graph revision
  are requested — source bodies are never loaded.

The snapshot is a lookup, not durable authority and not a scoped-projection
cache key. A fingerprint exists for tests and future safe caching; R.3a does
not cache authorized projections from it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ..contracts.evidence import SourceArtifactRecord, SourceRevision
from ..domain.canonical import canonical_sha256
from .graph_snapshot import ParsedGraphSnapshot


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


@dataclass(frozen=True)
class SourceProvenanceSnapshot:
    """Immutable application-contract view of requested source identity.

    ``get_artifact`` / ``get_revision`` return the records copied into this
    snapshot, or ``None`` when the requested id was missing. Callers must not
    mutate returned models; the snapshot is the coherent view for one read.
    """

    requested_artifact_ids: frozenset[str]
    requested_revision_ids: frozenset[str]
    artifacts: Mapping[str, SourceArtifactRecord]
    revisions: Mapping[str, SourceRevision]
    fingerprint: str

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
        return cls(
            requested_artifact_ids=requested_artifact_ids,
            requested_revision_ids=requested_revision_ids,
            artifacts=dict(artifacts),
            revisions=dict(revisions),
            fingerprint=source_provenance_fingerprint(
                artifacts=artifacts,
                revisions=revisions,
                missing_artifact_ids=missing_artifacts,
                missing_revision_ids=missing_revisions,
            ),
        )

    @property
    def artifact_count(self) -> int:
        return len(self.artifacts)

    @property
    def revision_count(self) -> int:
        return len(self.revisions)

    @property
    def missing_artifact_count(self) -> int:
        return len(self.requested_artifact_ids) - len(self.artifacts)

    @property
    def missing_revision_count(self) -> int:
        return len(self.requested_revision_ids) - len(self.revisions)

    def get_artifact(self, source_artifact_id: str) -> SourceArtifactRecord | None:
        return self.artifacts.get(source_artifact_id)

    def get_revision(self, source_revision_id: str) -> SourceRevision | None:
        return self.revisions.get(source_revision_id)


__all__ = [
    "SourceProvenanceSnapshot",
    "provenance_refs_from_parsed_graph",
    "source_provenance_fingerprint",
]
