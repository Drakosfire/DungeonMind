"""FT1a conformance: revision-pinned fictional-time query evaluation."""

# ruff: noqa: E501

from __future__ import annotations

import copy
import json
import subprocess
import traceback
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from dungeonmind.application.fictional_time import evaluate_fictional_time_query
from dungeonmind.application.graph_snapshot import UnionGraphV1SnapshotReader
from dungeonmind.contracts.fictional_time import (
    FICTIONAL_TIME_CLAIM_BUNDLE_SCHEMA,
    FICTIONAL_TIME_QUERY_RESULT_SCHEMA,
    FICTIONAL_TIME_QUERY_SCHEMA,
    FictionalTimeClaimBundle,
    FictionalTimeQuery,
    FictionalTimeResultStatus,
    FictionalTimeUnresolvedReason,
)
from dungeonmind.contracts.graph import StoredGraphRevision
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import FictionalTimeIntegrityError
from dungeonmind.domain.revision_ids import compute_revision_id

FIX = Path(__file__).resolve().parents[1] / "fixtures/fictional_time"
GRAPH_PATH = FIX / "ft1-two-case-graph-v1.json"
BUNDLE_PATH = FIX / "ft1-two-case-claim-bundle-v1.json"
READER = UnionGraphV1SnapshotReader()
SENTINEL = "__FT1A_SENTINEL_LEAK_PROBE__"
TREE = "anchor:hempholm-tree-felled"
BEETLES = "anchor:hempholm-root-beetle-attack"
GATE = "anchor:lysandra-mireward-gate-arrival"
STATE = "state:lysandra-returned-home-current-campaign-arc"
BOUNDARY = "state-boundary:lysandra-returned-at-mireward-gate"


@pytest.fixture(scope="module")
def revision() -> StoredGraphRevision:
    return StoredGraphRevision.model_validate(json.loads(GRAPH_PATH.read_text()))


@pytest.fixture(scope="module")
def bundle() -> FictionalTimeClaimBundle:
    return FictionalTimeClaimBundle.model_validate(json.loads(BUNDLE_PATH.read_text()))


def _eval(revision: StoredGraphRevision, bundle: FictionalTimeClaimBundle, query: dict):
    q = FictionalTimeQuery.model_validate(query)
    return evaluate_fictional_time_query(
        stored_revision=revision, claim_bundle=bundle, query=q, graph_reader=READER
    )


def _canon(result) -> dict[str, Any]:
    return result.model_dump(mode="json")


def _gold_queries() -> list[dict[str, Any]]:
    return [
        {"schema_version": FICTIONAL_TIME_QUERY_SCHEMA, "query_id": "query:hempholm-tree-before-beetles",
         "query_kind": "strict_before", "before_anchor_id": TREE, "after_anchor_id": BEETLES},
        {"schema_version": FICTIONAL_TIME_QUERY_SCHEMA, "query_id": "query:hempholm-tree-absolute-time",
         "query_kind": "absolute_fictional_time", "anchor_id": TREE},
        {"schema_version": FICTIONAL_TIME_QUERY_SCHEMA, "query_id": "query:lysandra-returned-before-gate",
         "query_kind": "state_at_boundary", "state_id": STATE, "boundary_anchor_id": GATE,
         "boundary_position": "immediately_before"},
        {"schema_version": FICTIONAL_TIME_QUERY_SCHEMA, "query_id": "query:lysandra-returned-after-gate",
         "query_kind": "state_at_boundary", "state_id": STATE, "boundary_anchor_id": GATE,
         "boundary_position": "immediately_after"},
    ]


def test_e1_schemas_reload_and_closed_query_shape(revision, bundle) -> None:
    assert bundle.schema_version == FICTIONAL_TIME_CLAIM_BUNDLE_SCHEMA
    assert FictionalTimeClaimBundle.model_validate(bundle.model_dump(mode="json"))
    assert StoredGraphRevision.model_validate(revision.model_dump(mode="json"))
    with pytest.raises(ValidationError):
        FictionalTimeClaimBundle.model_validate({**bundle.model_dump(), "extra": 1})
    with pytest.raises(ValidationError):
        FictionalTimeQuery.model_validate({
            "schema_version": FICTIONAL_TIME_QUERY_SCHEMA,
            "query_id": "query:bad-shape",
            "query_kind": "strict_before",
            "before_anchor_id": TREE,
            "anchor_id": TREE,
        })


@pytest.mark.parametrize(
    "mutator,match",
    [
        (lambda b: b.model_copy(update={"anchors": b.anchors + b.anchors[:1]}), "duplicate anchor_id"),
        (lambda b: b.model_copy(update={"strict_before_claims": [
            *b.strict_before_claims,
            b.strict_before_claims[0].model_copy(update={"claim_id": "claim:dup"}),
        ]}), "duplicate strict_before pair"),
        (lambda b: b.model_copy(update={"strict_before_claims": [
            b.strict_before_claims[0].model_copy(update={"evidence_ref_ids": ["ev:missing"]}),
        ]}), "dangling evidence"),
        (lambda b: b.model_copy(update={"evidence_refs": [
            *b.evidence_refs,
            b.evidence_refs[0].model_copy(update={"evidence_ref_id": "ev:orphan"}),
        ]}), "unused evidence"),
        (lambda b: b.model_copy(update={"strict_before_claims": [
            *b.strict_before_claims,
            b.strict_before_claims[0].model_copy(
                update={"claim_id": "claim:cycle-back", "before_anchor_id": BEETLES, "after_anchor_id": TREE}
            ),
        ]}), "directed cycle"),
        (lambda b: b.model_copy(update={"strict_before_claims": [
            b.strict_before_claims[0].model_copy(
                update={"before_anchor_id": TREE, "after_anchor_id": TREE, "claim_id": "claim:self"}
            ),
        ]}), "self-edge"),
        (lambda b: b.model_copy(update={"state_boundaries": [
            b.state_boundaries[0].model_copy(update={"before_value": True, "after_value": True}),
        ]}), "before_value and after_value must differ"),
    ],
)
def test_e2_bundle_mutation_matrix(bundle, mutator, match) -> None:
    mutated = mutator(bundle)
    with pytest.raises(ValidationError, match=match):
        FictionalTimeClaimBundle.model_validate(mutated.model_dump(mode="json"))


def test_e3_binding_integrity_errors(revision, bundle) -> None:
    bad_digest = revision.model_copy(deep=True)
    bad_digest.revision.graph_payload_sha256 = "0" * 64
    with pytest.raises(FictionalTimeIntegrityError) as exc:
        _eval(bad_digest, bundle, _gold_queries()[0])
    assert exc.value.reason == "graph_payload_digest_mismatch"
    bad_world = bundle.model_copy(update={"world_id": "world:other"})
    with pytest.raises(FictionalTimeIntegrityError) as exc:
        _eval(revision, bad_world, _gold_queries()[0])
    assert exc.value.reason == "revision_binding_mismatch"


def _rebind_revision_bundle(
    revision: StoredGraphRevision, bundle: FictionalTimeClaimBundle
) -> tuple[StoredGraphRevision, FictionalTimeClaimBundle]:
    digest = canonical_sha256(revision.graph_payload)
    rev = revision.revision
    rev_id = compute_revision_id(
        world_id=rev.world_id,
        parent_revision_id=rev.parent_revision_id,
        operation_ids=list(rev.operation_ids),
        graph_schema=rev.graph_schema,
        graph_payload_sha256=digest,
    )
    revision = revision.model_copy(
        update={"revision": rev.model_copy(update={"graph_payload_sha256": digest, "revision_id": rev_id})}
    )
    bundle = bundle.model_copy(update={"graph_payload_sha256": digest, "graph_revision_id": rev_id})
    return revision, bundle


def test_e4_missing_object_and_evidence_mismatch(revision, bundle) -> None:
    bad = revision.model_copy(deep=True)
    bad.graph_payload = copy.deepcopy(bad.graph_payload)
    bad.graph_payload["nodes"] = [
        n for n in bad.graph_payload["nodes"] if n["object_id"] != "obj:mireward-gate"
    ]
    bad, bound = _rebind_revision_bundle(bad, bundle)
    with pytest.raises(FictionalTimeIntegrityError) as exc:
        _eval(bad, bound, _gold_queries()[0])
    assert exc.value.reason == "anchor_object_not_found"
    tampered = revision.model_copy(deep=True)
    tampered.graph_payload = copy.deepcopy(tampered.graph_payload)
    tampered.graph_payload["evidence_refs"][0]["locator"] = "different locator"
    tampered, tbound = _rebind_revision_bundle(tampered, bundle)
    with pytest.raises(FictionalTimeIntegrityError) as exc:
        _eval(tampered, tbound, _gold_queries()[0])
    assert exc.value.reason == "evidence_binding_mismatch"


def test_e5_gold_queries(revision, bundle) -> None:
    results = [_canon(_eval(revision, bundle, q)) for q in _gold_queries()]
    assert results[0]["status"] == "entailed" and results[0]["value"] is True
    assert results[0]["proof_claim_ids"] == [
        "claim:hempholm-tree-before-revelry", "claim:hempholm-revelry-before-beetles",
    ]
    assert results[0]["evidence_ref_ids"] == sorted([
        "ev:hempholm-evening-revelry", "ev:hempholm-root-beetle-attack", "ev:hempholm-tree-felled",
    ])
    assert results[1]["status"] == "unresolved"
    assert results[1]["reason"] == "no_explicit_absolute_anchor"
    assert results[2]["value"] is False and results[2]["proof_claim_ids"] == [BOUNDARY]
    assert results[2]["evidence_ref_ids"] == ["ev:lysandra-not-home-c1-c2"]
    assert results[3]["value"] is True and results[3]["proof_claim_ids"] == [BOUNDARY]
    assert results[3]["evidence_ref_ids"] == ["ev:lysandra-mireward-gate-arrival"]
    for row in results:
        assert row["bundle_id"] == bundle.bundle_id
        assert row["graph_revision_id"] == revision.revision.revision_id
        assert row["graph_payload_sha256"] == revision.revision.graph_payload_sha256


def test_e6_strict_before_edge_cases(revision, bundle) -> None:
    same = {"schema_version": FICTIONAL_TIME_QUERY_SCHEMA, "query_id": "query:same",
            "query_kind": "strict_before", "before_anchor_id": TREE, "after_anchor_id": TREE}
    r = _eval(revision, bundle, same)
    assert r.status is FictionalTimeResultStatus.UNRESOLVED
    assert r.reason is FictionalTimeUnresolvedReason.SAME_ANCHOR_IRREFLEXIVE
    reverse = {"schema_version": FICTIONAL_TIME_QUERY_SCHEMA, "query_id": "query:reverse",
               "query_kind": "strict_before", "before_anchor_id": BEETLES, "after_anchor_id": TREE}
    r = _eval(revision, bundle, reverse)
    assert r.status is FictionalTimeResultStatus.CONTRADICTED and r.value is False
    unknown = {"schema_version": FICTIONAL_TIME_QUERY_SCHEMA, "query_id": "query:unknown",
               "query_kind": "strict_before", "before_anchor_id": "anchor:missing", "after_anchor_id": TREE}
    r = _eval(revision, bundle, unknown)
    assert r.reason is FictionalTimeUnresolvedReason.UNKNOWN_ANCHOR
    incomparable = {"schema_version": FICTIONAL_TIME_QUERY_SCHEMA, "query_id": "query:incomparable",
                    "query_kind": "strict_before", "before_anchor_id": TREE, "after_anchor_id": GATE}
    r = _eval(revision, bundle, incomparable)
    assert r.reason is FictionalTimeUnresolvedReason.NO_ORDERING_PATH


def test_e7_deterministic_proof_and_replay(revision, bundle) -> None:
    q = _gold_queries()[0]
    first = _eval(revision, bundle, q)
    shuffled = bundle.model_copy(deep=True)
    shuffled.strict_before_claims = list(reversed(shuffled.strict_before_claims))
    second = _eval(revision, shuffled, q)
    assert _canon(first) == _canon(second)
    dumped = first.model_dump(mode="json")
    dumped["proof_claim_ids"] = ["claim:invented"]
    again = _eval(revision, bundle, q)
    assert _canon(again) == _canon(first)


def test_e8_invalid_bundle_rejected_before_query(bundle) -> None:
    cyclic = bundle.model_copy(update={"strict_before_claims": [
        *bundle.strict_before_claims,
        bundle.strict_before_claims[0].model_copy(
            update={"claim_id": "claim:cycle", "before_anchor_id": BEETLES, "after_anchor_id": TREE},
        ),
    ]})
    with pytest.raises(ValidationError):
        FictionalTimeClaimBundle.model_validate(cyclic.model_dump(mode="json"))


def test_e9_absolute_unresolved_and_no_session_leak(revision, bundle) -> None:
    r = _eval(revision, bundle, _gold_queries()[1])
    assert r.reason is FictionalTimeUnresolvedReason.NO_EXPLICIT_ABSOLUTE_ANCHOR
    blob = json.dumps(_canon(r))
    assert "Session 04" not in blob and "Session 22" not in blob


def test_e10_sentinel_absent_from_errors(revision, bundle) -> None:
    bad = revision.model_copy(deep=True)
    bad.graph_payload = copy.deepcopy(bad.graph_payload)
    bad.graph_payload["nodes"] = [
        n for n in bad.graph_payload["nodes"] if n["object_id"] != "obj:mireward-gate"
    ]
    bad, bound = _rebind_revision_bundle(bad, bundle)
    with pytest.raises(FictionalTimeIntegrityError) as caught:
        _eval(bad, bound, _gold_queries()[0])
    exc = caught.value
    text = f"{exc!s}{exc!r}{traceback.format_exc()}{exc.details}"
    assert SENTINEL not in text
    assert "Session" not in text


def test_e11_no_temporal_scope() -> None:
    root = Path(__file__).resolve().parents[2]
    for rel in (
        "src/dungeonmind/contracts/fictional_time.py",
        "src/dungeonmind/application/fictional_time.py",
    ):
        assert "temporal_scope" not in (root / rel).read_text()


def test_e12_package_import_smoke() -> None:
    proc = subprocess.run(
        ["uv", "run", "--no-dev", "python", "-c", "import dungeonmind"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        import dungeonmind  # noqa: F401


def test_e13_result_schema_constant() -> None:
    assert FICTIONAL_TIME_QUERY_RESULT_SCHEMA == "dm_fictional_time_query_result_v1"


def test_e14_line_ceilings() -> None:
    root = Path(__file__).resolve().parents[2]
    limits = {
        root / "src/dungeonmind/contracts/fictional_time.py": 300,
        root / "src/dungeonmind/application/fictional_time.py": 325,
        Path(__file__): 525,
        FIX / "ft1-two-case-graph-v1.json": 250,
        FIX / "ft1-two-case-claim-bundle-v1.json": 250,
    }
    for path, limit in limits.items():
        count = sum(1 for line in path.read_text().splitlines() if line.strip())
        assert count <= limit, f"{path}: {count} > {limit}"
