"""Targeted immutable source/provenance snapshots for vNext candidate admission."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass

from dungeonmind.contracts.vnext.source import SourceArtifactV3, SourceRevisionV2
from dungeonmind.domain.canonical import canonical_sha256

from .frozen_json import FrozenDict


def _deep_copy_artifacts(
    artifacts: Mapping[str, SourceArtifactV3],
) -> FrozenDict[str, SourceArtifactV3]:
    return FrozenDict(
        {artifact_id: artifact.model_copy(deep=True) for artifact_id, artifact in artifacts.items()}
    )


def _deep_copy_revisions(
    revisions: Mapping[str, SourceRevisionV2],
) -> FrozenDict[str, SourceRevisionV2]:
    return FrozenDict(
        {revision_id: revision.model_copy(deep=True) for revision_id, revision in revisions.items()}
    )


def provenance_snapshot_fingerprint(
    *,
    artifacts: Mapping[str, SourceArtifactV3],
    revisions: Mapping[str, SourceRevisionV2],
    requested_artifact_ids: tuple[str, ...],
    requested_revision_ids: tuple[str, ...],
    missing_artifact_ids: tuple[str, ...],
    missing_revision_ids: tuple[str, ...],
) -> str:
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
            "requested_artifact_ids": list(requested_artifact_ids),
            "requested_revision_ids": list(requested_revision_ids),
            "missing_artifact_ids": list(missing_artifact_ids),
            "missing_revision_ids": list(missing_revision_ids),
        }
    )


@dataclass(frozen=True, slots=True)
class KnowledgeProvenanceSnapshot:
    """Immutable coherent view of requested source identity for one admission operation."""

    artifacts_by_id: FrozenDict[str, SourceArtifactV3]
    revisions_by_id: FrozenDict[str, SourceRevisionV2]
    requested_artifact_ids: tuple[str, ...]
    requested_revision_ids: tuple[str, ...]
    missing_artifact_ids: tuple[str, ...]
    missing_revision_ids: tuple[str, ...]
    fingerprint: str

    def get_artifact(self, artifact_id: str) -> SourceArtifactV3 | None:
        artifact = self.artifacts_by_id.get(artifact_id)
        if artifact is None:
            return None
        return artifact.model_copy(deep=True)

    def get_revision(self, revision_id: str) -> SourceRevisionV2 | None:
        revision = self.revisions_by_id.get(revision_id)
        if revision is None:
            return None
        return revision.model_copy(deep=True)


class InMemoryKnowledgeSourceReader:
    """Test/double reader with mutable backing stores and immutable snapshot returns."""

    def __init__(
        self,
        *,
        artifacts: MutableMapping[str, SourceArtifactV3] | None = None,
        revisions: MutableMapping[str, SourceRevisionV2] | None = None,
    ) -> None:
        self._artifacts: dict[str, SourceArtifactV3] = dict(artifacts or {})
        self._revisions: dict[str, SourceRevisionV2] = dict(revisions or {})
        self.snapshot_call_count = 0

    def get_provenance_snapshot(
        self,
        *,
        artifact_ids: Sequence[str],
        revision_ids: Sequence[str],
    ) -> KnowledgeProvenanceSnapshot:
        self.snapshot_call_count += 1
        requested_artifacts = tuple(sorted(set(artifact_ids)))
        requested_revisions = tuple(sorted(set(revision_ids)))

        loaded_artifacts: dict[str, SourceArtifactV3] = {}
        missing_artifacts: list[str] = []
        for artifact_id in requested_artifacts:
            artifact = self._artifacts.get(artifact_id)
            if artifact is None:
                missing_artifacts.append(artifact_id)
            else:
                loaded_artifacts[artifact_id] = artifact.model_copy(deep=True)

        loaded_revisions: dict[str, SourceRevisionV2] = {}
        missing_revisions: list[str] = []
        for revision_id in requested_revisions:
            revision = self._revisions.get(revision_id)
            if revision is None:
                missing_revisions.append(revision_id)
            else:
                loaded_revisions[revision_id] = revision.model_copy(deep=True)

        frozen_artifacts = _deep_copy_artifacts(loaded_artifacts)
        frozen_revisions = _deep_copy_revisions(loaded_revisions)
        missing_artifact_tuple = tuple(missing_artifacts)
        missing_revision_tuple = tuple(missing_revisions)
        fingerprint = provenance_snapshot_fingerprint(
            artifacts=frozen_artifacts,
            revisions=frozen_revisions,
            requested_artifact_ids=requested_artifacts,
            requested_revision_ids=requested_revisions,
            missing_artifact_ids=missing_artifact_tuple,
            missing_revision_ids=missing_revision_tuple,
        )
        return KnowledgeProvenanceSnapshot(
            artifacts_by_id=frozen_artifacts,
            revisions_by_id=frozen_revisions,
            requested_artifact_ids=requested_artifacts,
            requested_revision_ids=requested_revisions,
            missing_artifact_ids=missing_artifact_tuple,
            missing_revision_ids=missing_revision_tuple,
            fingerprint=fingerprint,
        )
