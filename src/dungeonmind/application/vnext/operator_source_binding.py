"""Pure validation for prepared, owner-attested legacy/native span binding."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import NoReturn

from dungeonmind.contracts.evidence import SourceArtifactRecord, SourceRevision, SourceStatus
from dungeonmind.contracts.vnext.common import LabelsAllVisibility
from dungeonmind.contracts.vnext.domain import DomainContractDescriptor
from dungeonmind.contracts.vnext.operator_source import (
    OperatorSourceCommandV1,
    OperatorSourceSelectionV1,
    PreparedOperatorSourceV1,
)
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError

from .builder import build_parsed_knowledge_revision
from .materialization import NATIVE_VNEXT_GRAPH_SCHEMA, decode_native_graph_payload
from .operator_approval import OperatorApprovalAuthority
from .records import StoredKnowledgeRevision


def _reject(reason: str) -> NoReturn:
    raise PersistenceIntegrityError(f"operator source binding: {reason}")


def _legacy_snapshot(
    artifact: SourceArtifactRecord | None,
    revision: SourceRevision | None,
    *, selection: OperatorSourceSelectionV1,
) -> str:
    if artifact is None or revision is None:
        _reject("legacy source pair is missing")
    if (
        artifact.source_artifact_id != selection.source_artifact_id
        or artifact.world_id != selection.legacy_world_id
        or artifact.status != SourceStatus.ACTIVE
        or artifact.current_revision_id != selection.source_revision_id
        or revision.source_revision_id != selection.source_revision_id
        or revision.source_artifact_id != selection.source_artifact_id
        or revision.content_sha256 != selection.expected_body_sha256
    ):
        _reject("legacy source identity, standing or body digest changed")
    if artifact.authority is None or artifact.authority != selection.native_policy.authority:
        _reject("legacy authority is unknown or incompatible")
    # A stored player/public policy cannot be silently narrowed or reinterpreted.
    if artifact.visibility is not None and str(artifact.visibility) != "gm":
        _reject("stored legacy visibility conflicts with GM-only policy")
    return canonical_sha256({
        "artifact": artifact.model_dump(mode="json"),
        "revision": revision.model_dump(mode="json"),
    })


def validate_operator_source_selection(
    *, selection: OperatorSourceSelectionV1,
    domain_contract: DomainContractDescriptor,
    authority: OperatorApprovalAuthority,
    head_revision: StoredKnowledgeRevision,
    legacy_artifact: SourceArtifactRecord | None,
    legacy_revision: SourceRevision | None,
    source_epoch: int,
    prepared_at: datetime | None = None,
) -> PreparedOperatorSourceV1:
    """Reject every unknown policy, stale identity and ambiguous passage before prepare."""
    if (
        head_revision.revision.space_id != selection.space_id
        or head_revision.revision.revision_id != selection.expected_head_revision_id
        or head_revision.revision.graph_schema != NATIVE_VNEXT_GRAPH_SCHEMA
    ):
        _reject("expected native head mismatch")
    descriptor_sha = canonical_sha256(domain_contract.model_dump(mode="json"))
    if (
        descriptor_sha != authority.domain_descriptor_sha256
        or head_revision.revision.domain_contract_ref.descriptor_sha256 != descriptor_sha
        or selection.gm_label != authority.gm_label
        or selection.gm_label not in domain_contract.visibility_labels
        or frozenset(selection.source_vocabulary) != authority.allowed_source_terms
    ):
        _reject("pinned domain/source vocabulary mismatch")
    policy = selection.native_policy
    if (
        policy.status != "active"
        or policy.source_classification not in authority.allowed_source_terms
        or not isinstance(policy.visibility, LabelsAllVisibility)
        or set(policy.visibility.labels) != {authority.gm_label}
        or any(item.schema_term not in domain_contract.source_annotation_schemas
               for item in policy.domain_metadata)
    ):
        _reject("native policy is not declared GM-only policy")
    legacy_sha = _legacy_snapshot(
        legacy_artifact, legacy_revision, selection=selection,
    )
    body = selection.body_text.encode("utf-8", "strict")
    if hashlib.sha256(body).hexdigest() != selection.expected_body_sha256:
        _reject("body SHA differs from legacy revision")
    parsed = build_parsed_knowledge_revision(
        revision=head_revision.revision,
        decoded_content=decode_native_graph_payload(head_revision.graph_payload),
    )
    if selection.claim_kind == "assertion":
        claim = parsed.get_assertion(selection.claim_id)
        memberships = () if claim is None else claim.metadata.evidence_ref_ids
        standing = None if claim is None else claim.metadata.standing
    else:
        claim = parsed.get_alias(selection.claim_id)
        memberships = () if claim is None else claim.evidence_ref_ids
        standing = None if claim is None else claim.standing
    evidence = parsed.get_evidence(selection.evidence_ref_id)
    if (
        claim is None or str(standing) == "retracted"
        or selection.evidence_ref_id not in memberships
        or evidence is None
        or evidence.source_artifact_id != selection.source_artifact_id
        or evidence.source_revision_id != selection.source_revision_id
        or evidence.source_span_ref_id != selection.source_span_ref_id
        or not evidence.can_open_source or not evidence.can_highlight_span
        or any(item.schema_term not in domain_contract.source_annotation_schemas
               for item in evidence.domain_metadata)
    ):
        _reject("claim/evidence/span membership mismatch")
    passage = selection.passage_text.encode("utf-8", "strict")
    starts: list[int] = []
    cursor = 0
    while (index := body.find(passage, cursor)) != -1:
        starts.append(index)
        cursor = index + 1
    if not starts or (len(starts) != 1 and selection.occurrence_index is None):
        _reject("passage absent or occurrence ambiguous")
    occurrence = 0 if selection.occurrence_index is None else selection.occurrence_index
    if occurrence >= len(starts):
        _reject("selected occurrence does not exist")
    start = starts[occurrence]
    end = start + len(passage)
    claim_sha = canonical_sha256({
        "revision_id": selection.expected_head_revision_id,
        "claim_kind": selection.claim_kind,
        "claim_id": selection.claim_id,
        "evidence_ref_id": selection.evidence_ref_id,
        "semantic_digest": parsed.semantic_digest,
    })
    command = OperatorSourceCommandV1(
        space_id=selection.space_id,
        legacy_world_id=selection.legacy_world_id,
        operation_id=selection.operation_id,
        expected_head_revision_id=selection.expected_head_revision_id,
        claim_kind=selection.claim_kind,
        claim_id=selection.claim_id,
        evidence_ref_id=selection.evidence_ref_id,
        source_artifact_id=selection.source_artifact_id,
        source_revision_id=selection.source_revision_id,
        source_span_ref_id=selection.source_span_ref_id,
        body_sha256=selection.expected_body_sha256,
        start_byte=start,
        end_byte=end,
        slice_sha256=hashlib.sha256(body[start:end]).hexdigest(),
        claim_sha256=claim_sha,
        native_policy=policy.model_copy(deep=True),
        domain_descriptor_sha256=descriptor_sha,
        source_vocabulary_sha256=authority.source_vocabulary_sha256,
        gm_label=authority.gm_label,
        legacy_metadata_sha256=legacy_sha,
        expected_source_epoch=source_epoch,
    )
    # Review text is bounded and derived from the same verified body/claim.
    excerpt = body[max(0, start - 80):min(len(body), end + 80)].decode(
        "utf-8", errors="ignore"
    )
    claim_summary = repr(claim)[:512]
    display = {
        "claim": {"kind": selection.claim_kind, "id": selection.claim_id,
                  "sha256": claim_sha, "summary": claim_summary},
        "evidence": selection.evidence_ref_id,
        "semantic_span": selection.source_span_ref_id,
        "source": {"artifact_id": selection.source_artifact_id,
                   "revision_id": selection.source_revision_id,
                   "body_sha256": selection.expected_body_sha256},
        "passage": {"excerpt": excerpt, "start_byte": start, "end_byte": end,
                    "slice_sha256": command.slice_sha256},
        "separate_policy_choice": policy.model_dump(mode="json"),
    }
    when = datetime.now(UTC) if prepared_at is None else prepared_at
    if when.utcoffset() is None:
        _reject("preparation time is naive")
    expires = when + timedelta(minutes=15)
    display_sha = canonical_sha256(display)
    preparation_sha = canonical_sha256({
        "command": command.model_dump(mode="json"),
        "review_display_sha256": display_sha,
        "prepared_at": when.isoformat(),
        "expires_at": expires.isoformat(),
    })
    return PreparedOperatorSourceV1(
        command=command, review_claim_summary=claim_summary, review_excerpt=excerpt,
        review_display_sha256=display_sha,
        prepared_at=when, expires_at=expires,
        preparation_sha256=preparation_sha,
    )
