"""Revision-pinned fictional-time query evaluation (FT1a)."""

from __future__ import annotations

import copy
from collections import defaultdict, deque
from typing import Any

from pydantic import ValidationError

from ..contracts.fictional_time import (
    FictionalTimeAuthorityMode,
    FictionalTimeBoundaryPosition,
    FictionalTimeClaimBundle,
    FictionalTimeQuery,
    FictionalTimeQueryKind,
    FictionalTimeQueryResult,
    FictionalTimeResultStatus,
    FictionalTimeUnresolvedReason,
)
from ..contracts.graph import StoredGraphRevision
from ..domain.canonical import canonical_sha256
from ..domain.errors import FictionalTimeIntegrityError
from .graph_snapshot import GraphSnapshotReader, ParsedGraphSnapshot


def _integrity(reason: str, **details: Any) -> FictionalTimeIntegrityError:
    safe = {k: v for k, v in details.items() if k in ("object_id",)}
    return FictionalTimeIntegrityError(reason=reason, details=safe or None)


def _reload_revision(stored: StoredGraphRevision) -> StoredGraphRevision:
    try:
        return StoredGraphRevision.model_validate(stored.model_dump(mode="json"))
    except ValidationError:
        raise _integrity("revision_reload_validation") from None


def _reload_bundle(bundle: FictionalTimeClaimBundle) -> FictionalTimeClaimBundle:
    try:
        return FictionalTimeClaimBundle.model_validate(bundle.model_dump(mode="json"))
    except ValidationError:
        raise _integrity("bundle_reload_validation") from None


def _reload_query(query: FictionalTimeQuery) -> FictionalTimeQuery:
    try:
        return FictionalTimeQuery.model_validate(query.model_dump(mode="json"))
    except ValidationError:
        raise _integrity("query_reload_validation") from None


def _verify_binding(
    revision: StoredGraphRevision,
    bundle: FictionalTimeClaimBundle,
) -> None:
    rev = revision.revision
    digest = canonical_sha256(revision.graph_payload)
    if digest != rev.graph_payload_sha256:
        raise _integrity("graph_payload_digest_mismatch")
    checks = (
        (bundle.world_id, rev.world_id, "world_id"),
        (bundle.graph_schema, rev.graph_schema, "graph_schema"),
        (bundle.graph_revision_id, rev.revision_id, "graph_revision_id"),
        (bundle.graph_payload_sha256, rev.graph_payload_sha256, "graph_payload_sha256"),
    )
    for left, right, _ in checks:
        if left != right:
            raise _integrity("revision_binding_mismatch")


def _parse_snapshot(
    revision: StoredGraphRevision,
    reader: GraphSnapshotReader,
) -> ParsedGraphSnapshot:
    payload = copy.deepcopy(revision.graph_payload)
    try:
        snapshot = reader.parse(
            graph_schema=revision.revision.graph_schema,
            graph_payload=payload,
        )
    except Exception:
        raise _integrity("graph_snapshot_validation") from None
    rev = revision.revision
    if snapshot.world_id != rev.world_id or snapshot.graph_schema != rev.graph_schema:
        raise _integrity("graph_snapshot_validation")
    return snapshot


def _verify_anchors(bundle: FictionalTimeClaimBundle, snapshot: ParsedGraphSnapshot) -> None:
    for anchor in bundle.anchors:
        for object_id in anchor.related_object_ids:
            if object_id not in snapshot.objects:
                raise _integrity("anchor_object_not_found", object_id=object_id)


def _verify_evidence(bundle: FictionalTimeClaimBundle, snapshot: ParsedGraphSnapshot) -> None:
    for ref in bundle.evidence_refs:
        record = snapshot.evidence.get(ref.evidence_ref_id)
        if record is None or record.model_dump(mode="json") != ref.model_dump(mode="json"):
            raise _integrity("evidence_binding_mismatch")


def _binding_fields(bundle: FictionalTimeClaimBundle) -> dict[str, Any]:
    return {
        "authority_mode": FictionalTimeAuthorityMode.SHADOW,
        "bundle_id": bundle.bundle_id,
        "world_id": bundle.world_id,
        "campaign_id": bundle.campaign_id,
        "graph_schema": bundle.graph_schema,
        "graph_revision_id": bundle.graph_revision_id,
        "graph_payload_sha256": bundle.graph_payload_sha256,
    }


def _anchor_ids(bundle: FictionalTimeClaimBundle) -> set[str]:
    return {a.anchor_id for a in bundle.anchors}


def _adj(bundle: FictionalTimeClaimBundle) -> dict[str, list[tuple[str, str]]]:
    out: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for claim in bundle.strict_before_claims:
        out[claim.before_anchor_id].append((claim.after_anchor_id, claim.claim_id))
    return out


def _shortest_path(
    adj: dict[str, list[tuple[str, str]]], start: str, goal: str
) -> list[str] | None:
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
            tie = (
                existing is not None
                and len(candidate) == len(existing)
                and candidate < existing
            )
            if better or tie:
                best[dst] = candidate
                queue.append(dst)
    return best.get(goal)


def _claim_evidence(bundle: FictionalTimeClaimBundle) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for claim in bundle.strict_before_claims:
        out[claim.claim_id] = list(claim.evidence_ref_ids)
    return out


def _path_evidence(bundle: FictionalTimeClaimBundle, path: list[str]) -> list[str]:
    by_claim = _claim_evidence(bundle)
    ids: set[str] = set()
    for cid in path:
        ids.update(by_claim[cid])
    return sorted(ids)


def _result(
    query: FictionalTimeQuery,
    bundle: FictionalTimeClaimBundle,
    *,
    status: FictionalTimeResultStatus,
    value: bool | None,
    proof: list[str],
    evidence: list[str],
    reason: FictionalTimeUnresolvedReason | None,
) -> FictionalTimeQueryResult:
    return FictionalTimeQueryResult(
        query_id=query.query_id,
        query_kind=query.query_kind,
        status=status,
        value=value,
        proof_claim_ids=proof,
        evidence_ref_ids=evidence,
        reason=reason,
        **_binding_fields(bundle),
    )


def _eval_strict_before(
    bundle: FictionalTimeClaimBundle, query: FictionalTimeQuery
) -> FictionalTimeQueryResult:
    before = query.before_anchor_id
    after = query.after_anchor_id
    assert before is not None and after is not None
    anchors = _anchor_ids(bundle)
    if before not in anchors or after not in anchors:
        missing = before if before not in anchors else after
        _ = missing
        return _result(
            query, bundle,
            status=FictionalTimeResultStatus.UNRESOLVED,
            value=None, proof=[], evidence=[],
            reason=FictionalTimeUnresolvedReason.UNKNOWN_ANCHOR,
        )
    if before == after:
        return _result(
            query, bundle,
            status=FictionalTimeResultStatus.UNRESOLVED,
            value=None, proof=[], evidence=[],
            reason=FictionalTimeUnresolvedReason.SAME_ANCHOR_IRREFLEXIVE,
        )
    adj = _adj(bundle)
    forward = _shortest_path(adj, before, after)
    if forward is not None:
        return _result(
            query, bundle,
            status=FictionalTimeResultStatus.ENTAILED,
            value=True,
            proof=forward,
            evidence=_path_evidence(bundle, forward),
            reason=None,
        )
    reverse = _shortest_path(adj, after, before)
    if reverse is not None:
        return _result(
            query, bundle,
            status=FictionalTimeResultStatus.CONTRADICTED,
            value=False,
            proof=reverse,
            evidence=_path_evidence(bundle, reverse),
            reason=None,
        )
    return _result(
        query, bundle,
        status=FictionalTimeResultStatus.UNRESOLVED,
        value=None, proof=[], evidence=[],
        reason=FictionalTimeUnresolvedReason.NO_ORDERING_PATH,
    )


def _eval_state_at_boundary(
    bundle: FictionalTimeClaimBundle, query: FictionalTimeQuery
) -> FictionalTimeQueryResult:
    state_id = query.state_id
    boundary_anchor_id = query.boundary_anchor_id
    position = query.boundary_position
    assert state_id is not None and boundary_anchor_id is not None and position is not None
    if boundary_anchor_id not in _anchor_ids(bundle):
        return _result(
            query, bundle,
            status=FictionalTimeResultStatus.UNRESOLVED,
            value=None, proof=[], evidence=[],
            reason=FictionalTimeUnresolvedReason.UNKNOWN_ANCHOR,
        )
    matches = [
        b for b in bundle.state_boundaries
        if b.state_id == state_id and b.boundary_anchor_id == boundary_anchor_id
    ]
    if not matches:
        return _result(
            query, bundle,
            status=FictionalTimeResultStatus.UNRESOLVED,
            value=None, proof=[], evidence=[],
            reason=FictionalTimeUnresolvedReason.NO_MATCHING_STATE_BOUNDARY,
        )
    boundary = matches[0]
    if position is FictionalTimeBoundaryPosition.IMMEDIATELY_BEFORE:
        value = boundary.before_value
        evidence = sorted(boundary.before_evidence_ref_ids)
    else:
        value = boundary.after_value
        evidence = sorted(boundary.after_evidence_ref_ids)
    return _result(
        query, bundle,
        status=FictionalTimeResultStatus.ENTAILED,
        value=value,
        proof=[boundary.claim_id],
        evidence=evidence,
        reason=None,
    )


def _eval_absolute(
    bundle: FictionalTimeClaimBundle, query: FictionalTimeQuery
) -> FictionalTimeQueryResult:
    anchor_id = query.anchor_id
    assert anchor_id is not None
    if anchor_id not in _anchor_ids(bundle):
        return _result(
            query, bundle,
            status=FictionalTimeResultStatus.UNRESOLVED,
            value=None, proof=[], evidence=[],
            reason=FictionalTimeUnresolvedReason.UNKNOWN_ANCHOR,
        )
    return _result(
        query, bundle,
        status=FictionalTimeResultStatus.UNRESOLVED,
        value=None, proof=[], evidence=[],
        reason=FictionalTimeUnresolvedReason.NO_EXPLICIT_ABSOLUTE_ANCHOR,
    )


def evaluate_fictional_time_query(
    *,
    stored_revision: StoredGraphRevision,
    claim_bundle: FictionalTimeClaimBundle,
    query: FictionalTimeQuery,
    graph_reader: GraphSnapshotReader,
) -> FictionalTimeQueryResult:
    revision = _reload_revision(stored_revision)
    bundle = _reload_bundle(claim_bundle)
    query = _reload_query(query)
    _verify_binding(revision, bundle)
    snapshot = _parse_snapshot(revision, graph_reader)
    _verify_anchors(bundle, snapshot)
    _verify_evidence(bundle, snapshot)
    if query.query_kind is FictionalTimeQueryKind.STRICT_BEFORE:
        return _eval_strict_before(bundle, query)
    if query.query_kind is FictionalTimeQueryKind.STATE_AT_BOUNDARY:
        return _eval_state_at_boundary(bundle, query)
    return _eval_absolute(bundle, query)
