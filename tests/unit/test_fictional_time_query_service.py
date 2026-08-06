"""FT1b application service proofs: exact revision only, no head."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from dungeonmind.application.fictional_time import evaluate_fictional_time_query
from dungeonmind.application.fictional_time_query_service import (
    query_fictional_time_shadow_at_revision,
)
from dungeonmind.application.graph_snapshot import UnionGraphV1SnapshotReader
from dungeonmind.contracts.fictional_time import (
    FICTIONAL_TIME_QUERY_SCHEMA,
    FictionalTimeClaimBundle,
    FictionalTimeQuery,
)
from dungeonmind.contracts.fictional_time_transport import FictionalTimeShadowQueryRequest
from dungeonmind.contracts.graph import PublishRevisionCommand, StoredGraphRevision
from dungeonmind.domain.errors import FictionalTimeIntegrityError, RevisionNotFoundError
from dungeonmind.infrastructure.memory import InMemoryWorldGraphRepository

FIX = Path(__file__).resolve().parents[1] / "fixtures/fictional_time"
READER = UnionGraphV1SnapshotReader()
WORLD = "world:ft1-fictional-time"
TREE = "anchor:hempholm-tree-felled"
BEETLES = "anchor:hempholm-root-beetle-attack"
LATER = datetime(2026, 8, 4, 13, 0, tzinfo=UTC)


def _fixture_revision() -> StoredGraphRevision:
    return StoredGraphRevision.model_validate(
        json.loads((FIX / "ft1-two-case-graph-v1.json").read_text())
    )


def _fixture_bundle() -> FictionalTimeClaimBundle:
    return FictionalTimeClaimBundle.model_validate(
        json.loads((FIX / "ft1-two-case-claim-bundle-v1.json").read_text())
    )


def _gold_query() -> dict[str, object]:
    return {
        "schema_version": FICTIONAL_TIME_QUERY_SCHEMA,
        "query_id": "query:hempholm-tree-before-beetles",
        "query_kind": "strict_before",
        "before_anchor_id": TREE,
        "after_anchor_id": BEETLES,
    }


def _publish_fixture(repo: InMemoryWorldGraphRepository):
    stored = _fixture_revision()
    rev = repo.publish_revision(
        PublishRevisionCommand(
            world_id=stored.revision.world_id,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=list(stored.revision.operation_ids),
            graph_schema=stored.revision.graph_schema,
            graph_payload=copy.deepcopy(stored.graph_payload),
            created_at=stored.revision.created_at,
        )
    )
    return rev, stored


def _rebind_bundle(
    bundle: FictionalTimeClaimBundle, revision_id: str, digest: str
) -> FictionalTimeClaimBundle:
    return bundle.model_copy(
        update={"graph_revision_id": revision_id, "graph_payload_sha256": digest}
    )


def _request(
    bundle: FictionalTimeClaimBundle, revision_id: str
) -> FictionalTimeShadowQueryRequest:
    return FictionalTimeShadowQueryRequest(
        world_id=bundle.world_id,
        graph_revision_id=revision_id,
        claim_bundle=bundle,
        query=FictionalTimeQuery.model_validate(_gold_query()),
    )


class _QuerySpyRepo:
    def __init__(self, inner: InMemoryWorldGraphRepository) -> None:
        self.inner = inner
        self.get_revision_calls: list[tuple[str, str]] = []

    def get_revision(self, world_id: str, revision_id: str):
        self.get_revision_calls.append((world_id, revision_id))
        return self.inner.get_revision(world_id, revision_id)

    def get_head(self, *_args, **_kwargs):
        raise AssertionError("get_head must not be called")

    def publish_revision(self, *_args, **_kwargs):
        raise AssertionError("publish_revision must not be called")

    def rollback_head(self, *_args, **_kwargs):
        raise AssertionError("rollback_head must not be called")


class _ForgedRevisionRepo(_QuerySpyRepo):
    def get_revision(self, world_id: str, revision_id: str):
        stored = self.inner.get_revision(world_id, revision_id)
        if stored is None:
            return None
        forged = stored.model_copy(deep=True)
        forged.revision = forged.revision.model_copy(
            update={"revision_id": "rev:" + "f" * 32}
        )
        return forged


def test_successful_query_uses_exact_revision_and_matches_evaluate() -> None:
    inner = InMemoryWorldGraphRepository()
    rev, _stored = _publish_fixture(inner)
    bundle = _rebind_bundle(
        _fixture_bundle(), rev.revision_id, rev.graph_payload_sha256
    )
    spy = _QuerySpyRepo(inner)
    result = query_fictional_time_shadow_at_revision(
        _request(bundle, rev.revision_id),
        world_graph_repository=spy,
        graph_reader=READER,
    )
    assert spy.get_revision_calls == [(WORLD, rev.revision_id)]
    loaded = inner.get_revision(WORLD, rev.revision_id)
    assert loaded is not None
    direct = evaluate_fictional_time_query(
        stored_revision=loaded,
        claim_bundle=bundle,
        query=FictionalTimeQuery.model_validate(_gold_query()),
        graph_reader=READER,
    )
    assert result.model_dump(mode="json") == direct.model_dump(mode="json")


def test_missing_revision_while_head_exists_is_not_found() -> None:
    inner = InMemoryWorldGraphRepository()
    rev, _stored = _publish_fixture(inner)
    missing = "rev:" + "0" * 32
    bundle = _rebind_bundle(_fixture_bundle(), missing, rev.graph_payload_sha256)
    spy = _QuerySpyRepo(inner)
    with pytest.raises(RevisionNotFoundError):
        query_fictional_time_shadow_at_revision(
            _request(bundle, missing),
            world_graph_repository=spy,
            graph_reader=READER,
        )
    assert spy.get_revision_calls == [(WORLD, missing)]


def test_forged_revision_id_on_stored_revision_raises_integrity() -> None:
    inner = InMemoryWorldGraphRepository()
    rev, _stored = _publish_fixture(inner)
    bundle = _rebind_bundle(
        _fixture_bundle(), rev.revision_id, rev.graph_payload_sha256
    )
    with pytest.raises(FictionalTimeIntegrityError) as raised:
        query_fictional_time_shadow_at_revision(
            _request(bundle, rev.revision_id),
            world_graph_repository=_ForgedRevisionRepo(inner),
            graph_reader=READER,
        )
    assert raised.value.reason == "revision_binding_mismatch"


def test_pinned_r1_result_survives_r2_head_move() -> None:
    inner = InMemoryWorldGraphRepository()
    r1, _ = _publish_fixture(inner)
    bundle = _rebind_bundle(
        _fixture_bundle(), r1.revision_id, r1.graph_payload_sha256
    )
    first = query_fictional_time_shadow_at_revision(
        _request(bundle, r1.revision_id),
        world_graph_repository=inner,
        graph_reader=READER,
    )
    payload = copy.deepcopy(_fixture_revision().graph_payload)
    payload["nodes"][0] = {**payload["nodes"][0], "label": "Mutated tree label"}
    r2 = inner.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD,
            parent_revision_id=r1.revision_id,
            expected_parent_revision_id=r1.revision_id,
            operation_ids=["op:ft1-two-case-mutated"],
            graph_schema=r1.graph_schema,
            graph_payload=payload,
            created_at=LATER,
        )
    )
    assert inner.get_head(WORLD).head_revision_id == r2.revision_id
    second = query_fictional_time_shadow_at_revision(
        _request(bundle, r1.revision_id),
        world_graph_repository=inner,
        graph_reader=READER,
    )
    assert second.model_dump(mode="json") == first.model_dump(mode="json")
