"""FT0 test-local fictional-time characterization (not production).

Gold stays in tests. Evaluator ignores source_manifest for occurrence.
Opaque temporal_scope round-trip proves carriage only, not queryability.
"""

from __future__ import annotations

import copy
import json
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pytest

from dungeonmind.contracts import (
    AcceptanceState,
    EvidenceRef,
    GraphContributionAssertion,
    SourceDomain,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures/fictional_time/ft0-two-case-characterization-v0.json"
)
VERSION = "dm_fictional_time_characterization_v0"
PIN = "a0cb1c00206cc5a674b22dc2051bd4fcbe96811f"
STATE = "state:lysandra-returned-home-current-campaign-arc"
GATE = "anchor:lysandra-mireward-gate-arrival"
TREE = "anchor:hempholm-tree-felled"
BEETLES = "anchor:hempholm-root-beetle-attack"
BOUNDARY = "state-boundary:lysandra-returned-at-mireward-gate"
Status = Literal["entailed", "contradicted", "unresolved"]
# Transcribed from pinned Buddy blob frontmatter at PIN (no sibling fetch at test time).
_PREFIX = "corpus/eldyrwild-markdown/Longmont Campaign/Campaign "
PINNED_FRONTMATTER = {
    "src:hempholm-session-04": {
        "path_tail": "1/Session Recaps/_normalized/Session 04 - The Grotesque Tree of Hempholm.md",
        "git_blob_sha": "bc9ae016793efdd5614ebd88339b745d654e5b56",
        "source_class": "observed_session_recap",
        "campaign_id": "longmont-c1",
        "session": 4,
    },
    "src:lysandra-mireward-history": {
        "path_tail": "2/NPCs/captain_lysandra_ironveil/lysandra_ironveil_mireward_history.md",
        "git_blob_sha": "1d7e7038a60d28af1215f2412e9378501bc07ba7",
        "source_class": "authored_dossier",
        "campaign_id": "longmont-c2",
        "session": 22,
    },
    "src:mireward-session-22": {
        "path_tail": "2/Session Recaps/_normalized/Session 22 - Mireward Road and Lysandro.md",
        "git_blob_sha": "1c68ce991857ae47c0407e4852526fa55aa123b4",
        "source_class": "observed_session_recap",
        "campaign_id": "longmont-c2",
        "session": 22,
    },
}
GOLD = json.loads(
    "["
    '{"query_id":"query:hempholm-tree-before-beetles",'
    '"query_kind":"strict_before","status":"entailed","value":true,'
    '"proof_claim_ids":["claim:hempholm-tree-before-revelry",'
    '"claim:hempholm-revelry-before-beetles"],'
    '"evidence_ids":["ev:hempholm-evening-revelry",'
    '"ev:hempholm-root-beetle-attack","ev:hempholm-tree-felled"],'
    '"reason":null},'
    '{"query_id":"query:hempholm-tree-absolute-time",'
    '"query_kind":"absolute_fictional_time","status":"unresolved",'
    '"value":null,"proof_claim_ids":[],"evidence_ids":[],'
    '"reason":"no_explicit_absolute_anchor"},'
    '{"query_id":"query:lysandra-returned-before-gate",'
    '"query_kind":"state_at_boundary","status":"entailed","value":false,'
    '"proof_claim_ids":["state-boundary:lysandra-returned-at-mireward-gate"],'
    '"evidence_ids":["ev:lysandra-not-home-c1-c2"],"reason":null},'
    '{"query_id":"query:lysandra-returned-after-gate",'
    '"query_kind":"state_at_boundary","status":"entailed","value":true,'
    '"proof_claim_ids":["state-boundary:lysandra-returned-at-mireward-gate"],'
    '"evidence_ids":["ev:lysandra-mireward-gate-arrival"],"reason":null}'
    "]"
)


class FixtureValidationError(ValueError):
    """Local validation failure; safe IDs/rule names only."""


@dataclass(frozen=True, slots=True)
class QueryResult:
    query_id: str
    query_kind: str
    status: Status
    value: bool | None
    proof_claim_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    reason: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "query_kind": self.query_kind,
            "status": self.status,
            "value": self.value,
            "proof_claim_ids": list(self.proof_claim_ids),
            "evidence_ids": list(self.evidence_ids),
            "reason": self.reason,
        }


def _qr(
    qid: str,
    kind: str,
    status: Status,
    value: bool | None = None,
    proof: tuple[str, ...] = (),
    evid: tuple[str, ...] = (),
    reason: str | None = None,
) -> QueryResult:
    return QueryResult(qid, kind, status, value, proof, evid, reason)


def _uniq(ids: list[str], kind: str) -> None:
    seen: set[str] = set()
    for item in ids:
        if not item or not str(item).strip():
            raise FixtureValidationError(f"blank_{kind}_id")
        if item in seen:
            raise FixtureValidationError(f"duplicate_{kind}_id:{item}")
        seen.add(item)


def _validate(raw: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "fixture_version", "world_id", "source_manifest", "evidence",
        "anchors", "strict_before_claims", "state_boundaries",
    }
    if set(raw) - allowed:
        raise FixtureValidationError(f"unexpected_fields:{sorted(set(raw) - allowed)}")
    if raw.get("fixture_version") != VERSION:
        raise FixtureValidationError("unknown_fixture_version")
    if "gold_answers" in raw:
        raise FixtureValidationError("gold_answers_forbidden")
    sources, evidence = raw["source_manifest"], raw["evidence"]
    anchors, claims = raw["anchors"], raw["strict_before_claims"]
    boundaries = raw["state_boundaries"]
    _uniq([s["source_id"] for s in sources], "source")
    _uniq([e["evidence_id"] for e in evidence], "evidence")
    _uniq([a["anchor_id"] for a in anchors], "anchor")
    _uniq([c["claim_id"] for c in claims], "claim")
    _uniq([b["boundary_id"] for b in boundaries], "boundary")
    _uniq([b["state_id"] for b in boundaries], "state")
    source_ids = {s["source_id"] for s in sources}
    evidence_ids = {e["evidence_id"] for e in evidence}
    anchor_ids = {a["anchor_id"] for a in anchors}
    for row in evidence:
        if row["source_id"] not in source_ids:
            raise FixtureValidationError(f"dangling_evidence_source:{row['evidence_id']}")
    used: set[str] = set()
    pairs: set[tuple[str, str]] = set()
    adj: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for claim in claims:
        before, after = claim["before_anchor_id"], claim["after_anchor_id"]
        if before not in anchor_ids or after not in anchor_ids:
            raise FixtureValidationError(f"dangling_claim_anchor:{claim['claim_id']}")
        if before == after:
            raise FixtureValidationError(f"self_before:{claim['claim_id']}")
        if (before, after) in pairs:
            raise FixtureValidationError(f"duplicate_strict_before_pair:{before}->{after}")
        pairs.add((before, after))
        if not claim["evidence_ids"]:
            raise FixtureValidationError(f"empty_claim_evidence:{claim['claim_id']}")
        for eid in claim["evidence_ids"]:
            if eid not in evidence_ids:
                raise FixtureValidationError(f"dangling_claim_evidence:{claim['claim_id']}")
            used.add(eid)
        adj[before].append((after, claim["claim_id"]))
    indeg = dict.fromkeys(anchor_ids, 0)
    for outs in adj.values():
        for dst, _ in outs:
            indeg[dst] += 1
    queue = deque([a for a, d in indeg.items() if d == 0])
    seen_n = 0
    while queue:
        node = queue.popleft()
        seen_n += 1
        for dst, _ in adj.get(node, []):
            indeg[dst] -= 1
            if indeg[dst] == 0:
                queue.append(dst)
    if seen_n != len(anchor_ids):
        raise FixtureValidationError("strict_before_cycle")
    bkeys: set[tuple[str, str]] = set()
    for boundary in boundaries:
        key = (boundary["state_id"], boundary["boundary_anchor_id"])
        if key in bkeys:
            raise FixtureValidationError(f"duplicate_state_boundary:{key}")
        bkeys.add(key)
        if boundary["boundary_anchor_id"] not in anchor_ids:
            raise FixtureValidationError(f"dangling_boundary_anchor:{boundary['boundary_id']}")
        if boundary["before_value"] == boundary["after_value"]:
            raise FixtureValidationError(f"unchanged_state_boundary:{boundary['boundary_id']}")
        for side in ("before_evidence_ids", "after_evidence_ids"):
            ids = boundary[side]
            if not ids:
                raise FixtureValidationError(f"missing_{side}:{boundary['boundary_id']}")
            for eid in ids:
                if eid not in evidence_ids:
                    raise FixtureValidationError(f"dangling_boundary_evidence:{eid}")
                used.add(eid)
    unused = evidence_ids - used
    if unused:
        raise FixtureValidationError(f"unused_evidence:{sorted(unused)}")
    # FT0 forbids absolute anchors entirely (no partial FT1 absolute semantics).
    for anchor in anchors:
        if anchor.get("absolute_fictional_time") is not None:
            raise FixtureValidationError(f"absolute_anchor_forbidden:{anchor['anchor_id']}")
    return raw


def load_fixture(path: Path = FIXTURE_PATH) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise FixtureValidationError("fixture_not_object")
    return _validate(raw)


def _adj(fx: dict[str, Any]) -> dict[str, list[tuple[str, str]]]:
    out: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for claim in fx["strict_before_claims"]:
        out[claim["before_anchor_id"]].append((claim["after_anchor_id"], claim["claim_id"]))
    return out


def _shortest(adj: dict[str, list[tuple[str, str]]], start: str, goal: str) -> list[str] | None:
    # Strict-before is irreflexive: identical anchors have no positive-length path.
    if start == goal:
        return None
    best: dict[str, list[str]] = {start: []}
    queue: deque[str] = deque([start])
    while queue:
        node = queue.popleft()
        path = best[node]
        for dst, cid in sorted(adj.get(node, []), key=lambda t: t[1]):
            candidate = [*path, cid]
            existing = best.get(dst)
            better = existing is None or len(candidate) < len(existing)
            tie = existing is not None and len(candidate) == len(existing) and candidate < existing
            if better or tie:
                best[dst] = candidate
                queue.append(dst)
    return best.get(goal)


def evaluate_strict_before(
    fx: dict[str, Any], *, query_id: str, before: str, after: str
) -> QueryResult:
    adj = _adj(fx)
    claims = {c["claim_id"]: c for c in fx["strict_before_claims"]}
    forward = _shortest(adj, before, after)
    reverse = _shortest(adj, after, before)
    if forward is not None:
        evid = tuple(sorted({e for cid in forward for e in claims[cid]["evidence_ids"]}))
        return _qr(query_id, "strict_before", "entailed", True, tuple(forward), evid)
    if reverse is not None:
        evid = tuple(sorted({e for cid in reverse for e in claims[cid]["evidence_ids"]}))
        return _qr(query_id, "strict_before", "contradicted", False, tuple(reverse), evid)
    return _qr(query_id, "strict_before", "unresolved")


def evaluate_absolute_time(fx: dict[str, Any], *, query_id: str, anchor_id: str) -> QueryResult:
    # Valid FT0 fixtures have only null absolutes; never invent from provenance.
    anchors = {a["anchor_id"]: a for a in fx["anchors"]}
    assert anchors[anchor_id].get("absolute_fictional_time") is None
    return _qr(
        query_id, "absolute_fictional_time", "unresolved", reason="no_explicit_absolute_anchor"
    )


def evaluate_state_at_boundary(
    fx: dict[str, Any],
    *,
    query_id: str,
    state_id: str,
    boundary_anchor_id: str,
    position: Literal["immediately_before", "immediately_after"],
) -> QueryResult:
    matches = [
        b for b in fx["state_boundaries"]
        if b["state_id"] == state_id and b["boundary_anchor_id"] == boundary_anchor_id
    ]
    if not matches:
        return _qr(
            query_id, "state_at_boundary", "unresolved", reason="no_matching_state_boundary"
        )
    boundary = matches[0]
    if position == "immediately_before":
        value, evid = boundary["before_value"], boundary["before_evidence_ids"]
    else:
        value, evid = boundary["after_value"], boundary["after_evidence_ids"]
    return _qr(
        query_id, "state_at_boundary", "entailed", bool(value),
        (boundary["boundary_id"],), tuple(sorted(evid)),
    )


def _canon(result: QueryResult) -> bytes:
    return json.dumps(result.as_dict(), sort_keys=True, separators=(",", ":")).encode()


def _run_gold(fx: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        evaluate_strict_before(
            fx, query_id="query:hempholm-tree-before-beetles", before=TREE, after=BEETLES
        ).as_dict(),
        evaluate_absolute_time(
            fx, query_id="query:hempholm-tree-absolute-time", anchor_id=TREE
        ).as_dict(),
        evaluate_state_at_boundary(
            fx, query_id="query:lysandra-returned-before-gate", state_id=STATE,
            boundary_anchor_id=GATE, position="immediately_before",
        ).as_dict(),
        evaluate_state_at_boundary(
            fx, query_id="query:lysandra-returned-after-gate", state_id=STATE,
            boundary_anchor_id=GATE, position="immediately_after",
        ).as_dict(),
    ]


@pytest.fixture(scope="module")
def fixture() -> dict[str, Any]:
    return load_fixture()


def test_e1_manifest_matches_pinned_corpus_frontmatter(fixture: dict[str, Any]) -> None:
    """E1: sealed manifest equals transcribed frontmatter from the pinned blobs."""
    assert "gold_answers" not in fixture
    assert all(a["absolute_fictional_time"] is None for a in fixture["anchors"])
    assert [r["source_id"] for r in fixture["source_manifest"]] == list(PINNED_FRONTMATTER)
    for row in fixture["source_manifest"]:
        pin = PINNED_FRONTMATTER[row["source_id"]]
        assert row == {
            "source_id": row["source_id"],
            "repository": "Drakosfire/DungeonMindBuddy",
            "repository_commit": PIN,
            "path": _PREFIX + pin["path_tail"],
            "git_blob_sha": pin["git_blob_sha"],
            "source_class": pin["source_class"],
            "campaign_id": pin["campaign_id"],
            "session_provenance": pin["session"],
        }
        # Explicit fidelity to corpus vocabulary (not invented campaign:N labels).
        assert row["campaign_id"].startswith("longmont-c")
        assert row["source_class"] in {"observed_session_recap", "authored_dossier"}


def test_e2_e3_e4_e5_four_gold_queries(fixture: dict[str, Any]) -> None:
    pairs = {(c["before_anchor_id"], c["after_anchor_id"]) for c in fixture["strict_before_claims"]}
    assert (TREE, BEETLES) not in pairs
    assert fixture["source_manifest"][0]["session_provenance"] == 4
    results = _run_gold(fixture)
    assert results == GOLD
    blob = json.dumps(results[1]).lower()
    assert "4" not in blob and "22" not in blob and "session" not in blob
    evid = {e["evidence_id"]: e["source_id"] for e in fixture["evidence"]}
    assert evid["ev:lysandra-not-home-c1-c2"] == "src:lysandra-mireward-history"
    assert evid["ev:lysandra-mireward-gate-arrival"] == "src:mireward-session-22"
    assert "current-campaign-arc" in STATE


def test_e6_e7_partial_order_replay_and_reorder(fixture: dict[str, Any]) -> None:
    mutated = copy.deepcopy(fixture)
    mutated["anchors"].append({
        "anchor_id": "anchor:unrelated-market-day",
        "label": "Unrelated",
        "absolute_fictional_time": None,
    })
    _validate(mutated)
    unresolved = evaluate_strict_before(
        mutated, query_id="query:unrelated-vs-tree",
        before="anchor:unrelated-market-day", after=TREE,
    )
    assert unresolved.status == "unresolved" and unresolved.value is None
    reflexive = evaluate_strict_before(
        fixture, query_id="query:tree-before-tree", before=TREE, after=TREE
    )
    assert reflexive.status == "unresolved" and reflexive.value is None
    assert reflexive.proof_claim_ids == ()
    reverse = evaluate_strict_before(
        fixture, query_id="query:beetles-before-tree", before=BEETLES, after=TREE
    )
    assert reverse.status == "contradicted" and reverse.value is False
    assert _run_gold(fixture) == GOLD
    shuffled = copy.deepcopy(fixture)
    keys = (
        "source_manifest",
        "evidence",
        "anchors",
        "strict_before_claims",
        "state_boundaries",
    )
    for key in keys:
        shuffled[key] = list(reversed(shuffled[key]))
    _validate(shuffled)
    assert _run_gold(shuffled) == GOLD
    result = evaluate_strict_before(
        fixture, query_id="query:hempholm-tree-before-beetles", before=TREE, after=BEETLES
    )
    poisoned = list(result.proof_claim_ids)
    poisoned.append("claim:invented")
    evid = list(result.evidence_ids)
    evid.clear()
    again = evaluate_strict_before(
        fixture, query_id="query:hempholm-tree-before-beetles", before=TREE, after=BEETLES
    )
    assert _canon(again) == _canon(result)


def test_e8_e9_fail_closed_validation(fixture: dict[str, Any]) -> None:
    cases = [
        (
            "strict_before_cycle",
            {
                "claim_id": "claim:beetles-before-tree-cycle",
                "before_anchor_id": BEETLES,
                "after_anchor_id": TREE,
                "evidence_ids": ["ev:hempholm-root-beetle-attack"],
            },
        ),
        (
            "self_before",
            {
                "claim_id": "claim:tree-before-tree",
                "before_anchor_id": TREE,
                "after_anchor_id": TREE,
                "evidence_ids": ["ev:hempholm-tree-felled"],
            },
        ),
    ]
    for match, claim in cases:
        bad = copy.deepcopy(fixture)
        bad["strict_before_claims"].append(claim)
        with pytest.raises(FixtureValidationError, match=match):
            _validate(bad)
    dangling = copy.deepcopy(fixture)
    dangling["strict_before_claims"][0]["evidence_ids"] = ["ev:missing"]
    with pytest.raises(FixtureValidationError, match="dangling_claim_evidence"):
        _validate(dangling)
    unused = copy.deepcopy(fixture)
    unused["evidence"].append({
        "evidence_id": "ev:orphan",
        "source_id": "src:hempholm-session-04",
        "locator_hint": "unused",
    })
    with pytest.raises(FixtureValidationError, match="unused_evidence"):
        _validate(unused)
    empty = copy.deepcopy(fixture)
    empty["strict_before_claims"][0]["evidence_ids"] = []
    with pytest.raises(FixtureValidationError, match="empty_claim_evidence"):
        _validate(empty)
    absolute = copy.deepcopy(fixture)
    absolute["anchors"][1]["absolute_fictional_time"] = "campaign-year-3"
    with pytest.raises(FixtureValidationError, match="absolute_anchor_forbidden"):
        _validate(absolute)


def test_e10_opaque_temporal_scope_round_trip_without_semantic_claim() -> None:
    """Carriage only: no production semantic validation, materialization, or queryability."""
    payload = {
        "fixture_version": VERSION,
        "claim_type": "strict_before",
        "claim_id": "claim:hempholm-tree-before-revelry",
        "before_anchor_id": TREE,
        "after_anchor_id": "anchor:hempholm-evening-revelry",
    }
    assertion = GraphContributionAssertion(
        assertion_id="assertion:ft0-opaque-carrier-probe",
        assertion_kind="fictional_time_probe",
        acceptance_state=AcceptanceState.ACCEPTED,
        temporal_scope=payload,
        evidence_refs=[
            EvidenceRef(
                evidence_ref_id="evidence:ft0-carrier",
                source_artifact_id="source:ft0-carrier",
                source_domain=SourceDomain.MANUAL,
            )
        ],
    )
    dumped = assertion.model_dump(mode="json")
    reloaded = GraphContributionAssertion.model_validate(dumped)
    assert reloaded.temporal_scope == payload
    assert reloaded.assertion_kind == "fictional_time_probe"
