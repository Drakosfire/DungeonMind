"""Targeted immutable source/provenance snapshots for vNext candidate admission."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Generic, TypeVar, cast

from dungeonmind.contracts.vnext.source import SourceArtifactV3, SourceRevisionV2
from dungeonmind.domain.canonical import canonical_sha256

from .errors import KnowledgeReadContextIntegrityError
from .frozen_json import FrozenDict

_ModelT = TypeVar("_ModelT", SourceArtifactV3, SourceRevisionV2)


def _make_sealed_copy_on_read_map(inner: Mapping[str, _ModelT]) -> Mapping[str, _ModelT]:
    """Return a mapping with no replaceable backing; every access deep-copies models."""

    sealed: Mapping[str, _ModelT] = MappingProxyType(
        {key: value.model_copy(deep=True) for key, value in inner.items()}
    )

    class _SealedCopyOnReadModelMap(Mapping[str, SourceArtifactV3 | SourceRevisionV2]):
        __slots__ = ()

        def __getitem__(self, key: str) -> SourceArtifactV3 | SourceRevisionV2:
            return sealed[key].model_copy(deep=True)

        def __iter__(self) -> Iterator[str]:
            return iter(sealed)

        def __len__(self) -> int:
            return len(sealed)

        def get(
            self,
            key: str,
            default: SourceArtifactV3 | SourceRevisionV2 | None = None,
        ) -> SourceArtifactV3 | SourceRevisionV2 | None:
            if key not in sealed:
                return default
            return sealed[key].model_copy(deep=True)

        def items(self) -> Iterator[tuple[str, SourceArtifactV3 | SourceRevisionV2]]:
            for key in sealed:
                yield key, sealed[key].model_copy(deep=True)

        def values(self) -> Iterator[SourceArtifactV3 | SourceRevisionV2]:
            for value in sealed.values():
                yield value.model_copy(deep=True)

        def __setattr__(self, name: str, value: object) -> None:
            raise TypeError("provenance snapshot maps are immutable")

        def __delattr__(self, name: str) -> None:
            raise TypeError("provenance snapshot maps are immutable")

    return cast(Mapping[str, _ModelT], _SealedCopyOnReadModelMap())


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


def _assert_source_identity(
    *,
    artifact_id: str,
    artifact: SourceArtifactV3,
) -> None:
    if artifact.source_artifact_id != artifact_id:
        raise KnowledgeReadContextIntegrityError(
            f"source artifact identity mismatch: map key {artifact_id!r} != "
            f"source_artifact_id {artifact.source_artifact_id!r}"
        )


def _assert_revision_identity(
    *,
    revision_id: str,
    revision: SourceRevisionV2,
) -> None:
    if revision.source_revision_id != revision_id:
        raise KnowledgeReadContextIntegrityError(
            f"source revision identity mismatch: map key {revision_id!r} != "
            f"source_revision_id {revision.source_revision_id!r}"
        )


def validate_provenance_snapshot_integrity(
    snapshot: KnowledgeProvenanceSnapshot,
    *,
    expected_artifact_ids: Sequence[str] | None = None,
    expected_revision_ids: Sequence[str] | None = None,
) -> None:
    """Fail-closed identity checks for any reader-produced provenance snapshot.

    When ``expected_*`` IDs are supplied (candidate-derived dependency sets), the
    snapshot's self-declared ``requested_*`` tuples must match them exactly so a
    custom reader cannot widen the authority surface exposed to admission/policy.
    """

    if expected_artifact_ids is not None:
        expected_artifacts = tuple(sorted(set(expected_artifact_ids)))
        if snapshot.requested_artifact_ids != expected_artifacts:
            raise KnowledgeReadContextIntegrityError(
                "provenance requested_artifact_ids do not match candidate-derived dependencies"
            )
    if expected_revision_ids is not None:
        expected_revisions = tuple(sorted(set(expected_revision_ids)))
        if snapshot.requested_revision_ids != expected_revisions:
            raise KnowledgeReadContextIntegrityError(
                "provenance requested_revision_ids do not match candidate-derived dependencies"
            )

    requested_artifacts = frozenset(snapshot.requested_artifact_ids)
    requested_revisions = frozenset(snapshot.requested_revision_ids)

    for artifact_id, artifact in snapshot.artifacts_by_id.items():
        if artifact_id not in requested_artifacts:
            raise KnowledgeReadContextIntegrityError(
                f"unexpected artifact id in provenance snapshot: {artifact_id!r}"
            )
        _assert_source_identity(artifact_id=artifact_id, artifact=artifact)

    for revision_id, revision in snapshot.revisions_by_id.items():
        if revision_id not in requested_revisions:
            raise KnowledgeReadContextIntegrityError(
                f"unexpected revision id in provenance snapshot: {revision_id!r}"
            )
        _assert_revision_identity(revision_id=revision_id, revision=revision)

    for artifact_id in requested_artifacts:
        if (
            artifact_id not in snapshot.artifacts_by_id
            and artifact_id not in snapshot.missing_artifact_ids
        ):
            raise KnowledgeReadContextIntegrityError(
                f"requested artifact id neither present nor missing: {artifact_id!r}"
            )

    for revision_id in requested_revisions:
        if (
            revision_id not in snapshot.revisions_by_id
            and revision_id not in snapshot.missing_revision_ids
        ):
            raise KnowledgeReadContextIntegrityError(
                f"requested revision id neither present nor missing: {revision_id!r}"
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


def coherent_epoch_view_fingerprint(*, epoch: int) -> str:
    """Stable fingerprint for a coherent view pinned at one store generation."""

    return canonical_sha256({"pinned_generation": epoch})


@dataclass(frozen=True, slots=True)
class KnowledgeProvenanceSnapshot:
    """Immutable coherent view of requested source identity for one admission operation."""

    artifacts_by_id: Mapping[str, SourceArtifactV3]
    revisions_by_id: Mapping[str, SourceRevisionV2]
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


class _GenerationCounter:
    __slots__ = ("value",)

    def __init__(self) -> None:
        self.value = 0

    def bump(self) -> int:
        self.value += 1
        return self.value


class _VersionedModelStore(Generic[_ModelT]):
    """Append-only generation history for one entity kind (artifacts or revisions)."""

    __slots__ = ("_counter", "_history")

    def __init__(self, counter: _GenerationCounter) -> None:
        self._counter = counter
        self._history: dict[str, list[tuple[int, _ModelT | None]]] = {}

    def bootstrap(self, items: Mapping[str, _ModelT]) -> None:
        for key, value in items.items():
            self._history[key] = [(0, value.model_copy(deep=True))]

    def write(self, key: str, value: _ModelT) -> None:
        generation = self._counter.bump()
        self._history.setdefault(key, []).append((generation, value.model_copy(deep=True)))

    def clear_all(self) -> None:
        if not self._history:
            return
        generation = self._counter.bump()
        for key in self._history:
            self._history[key].append((generation, None))

    def get_at(self, key: str, epoch: int) -> _ModelT | None:
        entries = self._history.get(key)
        if not entries:
            return None
        resolved: _ModelT | None = None
        for generation, value in entries:
            if generation <= epoch:
                resolved = value
            else:
                break
        return None if resolved is None else resolved.model_copy(deep=True)

    def keys_at(self, epoch: int) -> tuple[str, ...]:
        present: list[str] = []
        for key in self._history:
            if self.get_at(key, epoch) is not None:
                present.append(key)
        return tuple(sorted(present))

    def values_at(self, epoch: int) -> list[_ModelT]:
        return [
            value
            for key in self.keys_at(epoch)
            if (value := self.get_at(key, epoch)) is not None
        ]


class _VersionedStoreProxy(Mapping[str, _ModelT], Generic[_ModelT]):
    """Dict-like facade over a versioned store at the live (latest) generation."""

    __slots__ = ("_store",)

    def __init__(self, store: _VersionedModelStore[_ModelT]) -> None:
        self._store = store

    def __getitem__(self, key: str) -> _ModelT:
        value = self._store.get_at(key, self._epoch())
        if value is None:
            raise KeyError(key)
        return value

    def __setitem__(self, key: str, value: _ModelT) -> None:
        self._store.write(key, value)

    def __delitem__(self, key: str) -> None:
        generation = self._store._counter.bump()
        self._store._history.setdefault(key, []).append((generation, None))

    def _epoch(self) -> int:
        return self._store._counter.value

    def __iter__(self) -> Iterator[str]:
        return iter(self._store.keys_at(self._epoch()))

    def __len__(self) -> int:
        return len(self._store.keys_at(self._epoch()))

    def get(self, key: str, default: _ModelT | None = None) -> _ModelT | None:
        value = self._store.get_at(key, self._epoch())
        if value is None:
            return default
        return value

    def clear(self) -> None:
        self._store.clear_all()

    def update(self, other: Mapping[str, _ModelT]) -> None:
        for key, value in other.items():
            self[key] = value

    def values(self) -> Iterator[_ModelT]:
        yield from self._store.values_at(self._epoch())


def _build_snapshot_from_loaded(
    *,
    loaded_artifacts: Mapping[str, SourceArtifactV3],
    loaded_revisions: Mapping[str, SourceRevisionV2],
    requested_artifacts: tuple[str, ...],
    requested_revisions: tuple[str, ...],
    missing_artifacts: tuple[str, ...],
    missing_revisions: tuple[str, ...],
) -> KnowledgeProvenanceSnapshot:
    frozen_artifacts = _deep_copy_artifacts(loaded_artifacts)
    frozen_revisions = _deep_copy_revisions(loaded_revisions)
    fingerprint = provenance_snapshot_fingerprint(
        artifacts=frozen_artifacts,
        revisions=frozen_revisions,
        requested_artifact_ids=requested_artifacts,
        requested_revision_ids=requested_revisions,
        missing_artifact_ids=missing_artifacts,
        missing_revision_ids=missing_revisions,
    )
    snapshot = KnowledgeProvenanceSnapshot(
        artifacts_by_id=_make_sealed_copy_on_read_map(frozen_artifacts),
        revisions_by_id=_make_sealed_copy_on_read_map(frozen_revisions),
        requested_artifact_ids=requested_artifacts,
        requested_revision_ids=requested_revisions,
        missing_artifact_ids=missing_artifacts,
        missing_revision_ids=missing_revisions,
        fingerprint=fingerprint,
    )
    validate_provenance_snapshot_integrity(
        snapshot,
        expected_artifact_ids=requested_artifacts,
        expected_revision_ids=requested_revisions,
    )
    return snapshot


class CoherentInMemoryView:
    """O(1) coherent view: pins one authority generation; materializes on snapshot only."""

    __slots__ = (
        "_artifact_cache",
        "_epoch",
        "_parent",
        "_revision_cache",
        "_view_fingerprint",
        "materialized_artifact_count",
        "materialized_revision_count",
        "snapshot_call_count",
    )

    def __init__(self, parent: InMemoryKnowledgeSourceReader, *, epoch: int) -> None:
        object.__setattr__(self, "_parent", parent)
        object.__setattr__(self, "_epoch", epoch)
        object.__setattr__(
            self, "_view_fingerprint", coherent_epoch_view_fingerprint(epoch=epoch)
        )
        object.__setattr__(self, "_artifact_cache", {})
        object.__setattr__(self, "_revision_cache", {})
        object.__setattr__(self, "snapshot_call_count", 0)
        object.__setattr__(self, "materialized_artifact_count", 0)
        object.__setattr__(self, "materialized_revision_count", 0)

    def __setattr__(self, name: str, value: object) -> None:
        if name in {"_epoch", "_view_fingerprint", "epoch", "view_fingerprint"}:
            raise TypeError("CoherentInMemoryView epoch/fingerprint are immutable")
        if name.startswith("_") or name in {
            "materialized_artifact_count",
            "materialized_revision_count",
            "snapshot_call_count",
        }:
            object.__setattr__(self, name, value)
            return
        raise TypeError(f"CoherentInMemoryView attribute {name!r} is not assignable")

    @property
    def epoch(self) -> int:
        return self._epoch

    @property
    def view_fingerprint(self) -> str:
        return self._view_fingerprint

    def open_coherent_view(self) -> CoherentInMemoryView:
        return CoherentInMemoryView(self._parent, epoch=self._epoch)

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
            if artifact_id in self._artifact_cache:
                loaded_artifacts[artifact_id] = self._artifact_cache[artifact_id].model_copy(
                    deep=True
                )
                continue
            artifact = self._parent._artifact_store.get_at(artifact_id, self.epoch)
            if artifact is None:
                missing_artifacts.append(artifact_id)
            else:
                copied = artifact
                _assert_source_identity(artifact_id=artifact_id, artifact=copied)
                self._artifact_cache[artifact_id] = copied
                self.materialized_artifact_count = len(self._artifact_cache)
                loaded_artifacts[artifact_id] = copied

        loaded_revisions: dict[str, SourceRevisionV2] = {}
        missing_revisions: list[str] = []
        for revision_id in requested_revisions:
            if revision_id in self._revision_cache:
                loaded_revisions[revision_id] = self._revision_cache[revision_id].model_copy(
                    deep=True
                )
                continue
            revision = self._parent._revision_store.get_at(revision_id, self.epoch)
            if revision is None:
                missing_revisions.append(revision_id)
            else:
                copied = revision
                _assert_revision_identity(revision_id=revision_id, revision=copied)
                self._revision_cache[revision_id] = copied
                self.materialized_revision_count = len(self._revision_cache)
                loaded_revisions[revision_id] = copied

        return _build_snapshot_from_loaded(
            loaded_artifacts=loaded_artifacts,
            loaded_revisions=loaded_revisions,
            requested_artifacts=requested_artifacts,
            requested_revisions=requested_revisions,
            missing_artifacts=tuple(missing_artifacts),
            missing_revisions=tuple(missing_revisions),
        )


class InMemoryKnowledgeSourceReader:
    """Test/double reader with mutable backing stores and immutable snapshot returns."""

    def __init__(
        self,
        *,
        artifacts: MutableMapping[str, SourceArtifactV3] | None = None,
        revisions: MutableMapping[str, SourceRevisionV2] | None = None,
        view_fingerprint: str | None = None,
    ) -> None:
        self._generation_counter = _GenerationCounter()
        self._artifact_store: _VersionedModelStore[SourceArtifactV3] = _VersionedModelStore(
            self._generation_counter
        )
        self._revision_store: _VersionedModelStore[SourceRevisionV2] = _VersionedModelStore(
            self._generation_counter
        )
        if artifacts:
            self._artifact_store.bootstrap(artifacts)
        if revisions:
            self._revision_store.bootstrap(revisions)
        self._artifacts: _VersionedStoreProxy[SourceArtifactV3] = _VersionedStoreProxy(
            self._artifact_store
        )
        self._revisions: _VersionedStoreProxy[SourceRevisionV2] = _VersionedStoreProxy(
            self._revision_store
        )
        self.snapshot_call_count = 0
        self.view_fingerprint = view_fingerprint or coherent_epoch_view_fingerprint(
            epoch=self._generation_counter.value
        )

    def open_coherent_view(self) -> CoherentInMemoryView:
        return CoherentInMemoryView(self, epoch=self._generation_counter.value)

    def get_provenance_snapshot(
        self,
        *,
        artifact_ids: Sequence[str],
        revision_ids: Sequence[str],
    ) -> KnowledgeProvenanceSnapshot:
        self.snapshot_call_count += 1
        epoch = self._generation_counter.value
        requested_artifacts = tuple(sorted(set(artifact_ids)))
        requested_revisions = tuple(sorted(set(revision_ids)))

        loaded_artifacts: dict[str, SourceArtifactV3] = {}
        missing_artifacts: list[str] = []
        for artifact_id in requested_artifacts:
            artifact = self._artifact_store.get_at(artifact_id, epoch)
            if artifact is None:
                missing_artifacts.append(artifact_id)
            else:
                copied = artifact
                _assert_source_identity(artifact_id=artifact_id, artifact=copied)
                loaded_artifacts[artifact_id] = copied

        loaded_revisions: dict[str, SourceRevisionV2] = {}
        missing_revisions: list[str] = []
        for revision_id in requested_revisions:
            revision = self._revision_store.get_at(revision_id, epoch)
            if revision is None:
                missing_revisions.append(revision_id)
            else:
                copied = revision
                _assert_revision_identity(revision_id=revision_id, revision=copied)
                loaded_revisions[revision_id] = copied

        return _build_snapshot_from_loaded(
            loaded_artifacts=loaded_artifacts,
            loaded_revisions=loaded_revisions,
            requested_artifacts=requested_artifacts,
            requested_revisions=requested_revisions,
            missing_artifacts=tuple(missing_artifacts),
            missing_revisions=tuple(missing_revisions),
        )
