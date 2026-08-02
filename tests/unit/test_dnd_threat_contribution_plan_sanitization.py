"""Failure sanitization: planning errors never echo source or graph prose."""

from __future__ import annotations

import copy
import json
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from dungeonmind.application.graph_snapshot import UnionGraphV3SnapshotReader
from dungeonmind.contracts.graph import StoredGraphRevision, WorldGraphRevision
from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.revision_ids import compute_revision_id
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from dungeonmind_dnd.application.contribution_planning import (
    plan_threat_candidate_contribution,
)
from dungeonmind_dnd.domain.errors import DndContributionPlanningError

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "dungeonmind_dnd"
PACKET_PATH = FIXTURES / "tripod-null-calf-threat-candidates-v1.json"
GRAPH_PATH = FIXTURES / "gatewatch-world-graph-v3.json"
DESCRIPTOR_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "dungeonmind_dnd"
    / "profiles"
    / "dnd5e-v2.json"
)

ACTOR = "operator:synthetic-reviewer"
PLANNED_AT = datetime(2026, 8, 1, 18, 0, tzinfo=UTC)

SENTINEL_LABEL = "SENTINEL_CANDIDATE_LABEL_LEAK_PROBE"
SENTINEL_SUMMARY = "SENTINEL_CANDIDATE_SUMMARY_LEAK_PROBE"
SENTINEL_LOCATOR = "fixture://sentinel-candidate-locator#LEAK_PROBE"
SENTINEL_GRAPH_LABEL = "SENTINEL_GRAPH_LABEL_LEAK_PROBE"
SENTINEL_GRAPH_ALIAS = "SENTINEL_GRAPH_ALIAS_LEAK_PROBE"
SENTINEL_GRAPH_SUMMARY = "SENTINEL_GRAPH_SUMMARY_LEAK_PROBE"
SENTINEL_GRAPH_LOCATOR = "fixture://sentinel-graph-locator#LEAK_PROBE"

ALL_SENTINELS = (
    SENTINEL_LABEL,
    SENTINEL_SUMMARY,
    SENTINEL_LOCATOR,
    SENTINEL_GRAPH_LABEL,
    SENTINEL_GRAPH_ALIAS,
    SENTINEL_GRAPH_SUMMARY,
    SENTINEL_GRAPH_LOCATOR,
)


def _reader() -> UnionGraphV3SnapshotReader:
    descriptor = SemanticProfileDescriptor.model_validate(
        json.loads(DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    )
    return UnionGraphV3SnapshotReader(
        profile_registry=StaticSemanticProfileRegistry([descriptor])
    )


def _stored(payload: dict[str, Any] | None = None) -> StoredGraphRevision:
    fixture = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    graph_payload = copy.deepcopy(payload or fixture["graph_payload"])
    meta = fixture["revision_metadata"]
    digest = canonical_sha256(graph_payload)
    revision_id = compute_revision_id(
        world_id=fixture["world_id"],
        parent_revision_id=meta["parent_revision_id"],
        operation_ids=list(meta["operation_ids"]),
        graph_schema=fixture["graph_schema"],
        graph_payload_sha256=digest,
    )
    return StoredGraphRevision(
        revision=WorldGraphRevision(
            world_id=fixture["world_id"],
            revision_id=revision_id,
            parent_revision_id=meta["parent_revision_id"],
            created_at=datetime.fromisoformat(meta["created_at"].replace("Z", "+00:00")),
            operation_ids=list(meta["operation_ids"]),
            graph_schema=fixture["graph_schema"],
            graph_payload_sha256=digest,
        ),
        graph_payload=graph_payload,
    )


def _assert_no_sentinel(error: BaseException) -> None:
    formatted = "".join(traceback.format_exception(error))
    details = getattr(error, "details", {})
    surfaces = (
        str(error),
        repr(error),
        formatted,
        json.dumps(details, default=str),
    )
    for surface in surfaces:
        for sentinel in ALL_SENTINELS:
            assert sentinel not in surface


def test_malformed_packet_parse_failure_hides_candidate_prose() -> None:
    packet = json.loads(PACKET_PATH.read_text(encoding="utf-8"))
    packet["nodes"][0]["label"] = SENTINEL_LABEL
    packet["nodes"][0]["summary"] = SENTINEL_SUMMARY
    packet["evidence_refs"][0]["locator"] = SENTINEL_LOCATOR
    # Force a packet-level failure after prose is present.
    packet["nodes"][0]["kind"] = "dnd5e:not-a-catalog-kind"
    with pytest.raises(DndContributionPlanningError) as exc_info:
        plan_threat_candidate_contribution(
            packet,
            stored_revision=_stored(),
            graph_reader=_reader(),
            actor=ACTOR,
            planned_at=PLANNED_AT,
        )
    _assert_no_sentinel(exc_info.value)


def test_reader_failure_hides_graph_prose() -> None:
    fixture = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    payload = copy.deepcopy(fixture["graph_payload"])
    north = next(n for n in payload["nodes"] if n["object_id"] == "obj:north-gate")
    north["label"] = SENTINEL_GRAPH_LABEL
    north["alias_assertions"][0]["alias"] = SENTINEL_GRAPH_ALIAS
    north["summary_assertion"]["summary"] = SENTINEL_GRAPH_SUMMARY
    payload["evidence_refs"][0]["locator"] = SENTINEL_GRAPH_LOCATOR
    # Corrupt structure so the reader fails after prose is present.
    payload["relationships"] = [{"broken": True}]
    with pytest.raises(DndContributionPlanningError) as exc_info:
        plan_threat_candidate_contribution(
            json.loads(PACKET_PATH.read_text(encoding="utf-8")),
            stored_revision=_stored(payload),
            graph_reader=_reader(),
            actor=ACTOR,
            planned_at=PLANNED_AT,
        )
    _assert_no_sentinel(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True


def test_profile_mismatch_hides_graph_and_candidate_prose() -> None:
    packet = json.loads(PACKET_PATH.read_text(encoding="utf-8"))
    packet["nodes"][0]["label"] = SENTINEL_LABEL
    packet["nodes"][0]["summary"] = SENTINEL_SUMMARY
    packet["evidence_refs"][0]["locator"] = SENTINEL_LOCATOR
    fixture = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    payload = copy.deepcopy(fixture["graph_payload"])
    north = next(n for n in payload["nodes"] if n["object_id"] == "obj:north-gate")
    north["label"] = SENTINEL_GRAPH_LABEL
    north["alias_assertions"][0]["alias"] = SENTINEL_GRAPH_ALIAS
    north["summary_assertion"]["summary"] = SENTINEL_GRAPH_SUMMARY
    payload["evidence_refs"][0]["locator"] = SENTINEL_GRAPH_LOCATOR
    # Valid graph structure, wrong profile digest → integrity/planning error.
    payload["semantic_profile"]["descriptor_sha256"] = "0" * 64
    with pytest.raises(DndContributionPlanningError) as exc_info:
        plan_threat_candidate_contribution(
            packet,
            stored_revision=_stored(payload),
            graph_reader=_reader(),
            actor=ACTOR,
            planned_at=PLANNED_AT,
        )
    _assert_no_sentinel(exc_info.value)
    assert exc_info.value.__cause__ is None
