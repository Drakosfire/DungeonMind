"""Deterministic context-bound source anchors for admitted vNext evidence."""

from __future__ import annotations

import base64
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from dungeonmind.domain.canonical import canonical_json, canonical_sha256

from .entity_reads import EntityReadSourceArtifact, EntityReadSourceRevision
from .read_context import KnowledgeReadContext
from .records import ParsedEvidenceRef

ANCHOR_SCHEMA_VERSION = "dm-source-anchor-v1"
ANCHOR_TOKEN_PREFIX = "dm-source-anchor-v1."
MAX_ANCHOR_TOKEN_LENGTH = 8192


@dataclass(frozen=True, slots=True)
class SourceAnchor:
    anchor_id: str
    evidence_ref_id: str
    source_artifact_id: str
    source_revision_id: str | None
    evidence_role: str
    can_open_source: bool
    can_highlight_span: bool
    locator: str | None
    uri: str | None
    source_locator: str | None
    line_ref: str | None
    source_span_ref_id: str | None
    admitted_supporter_assertion_ids: tuple[str, ...]


def context_binding_digest(context: KnowledgeReadContext) -> str:
    parsed = context.parsed
    return canonical_sha256(
        {
            "space_id": parsed.space_id,
            "revision_id": parsed.revision_id,
            "request": context.request.model_dump(mode="json"),
            "domain_id": parsed.domain_contract_ref.domain_id,
            "domain_revision": parsed.domain_contract_ref.domain_revision,
            "domain_descriptor_sha256": parsed.domain_contract_ref.descriptor_sha256,
            "profile_id": parsed.semantic_profile_ref.profile_id,
            "profile_revision": parsed.semantic_profile_ref.profile_revision,
            "profile_descriptor_sha256": parsed.semantic_profile_ref.descriptor_sha256,
            "policy_id": context.domain_policy.policy_id,
        }
    )


def visible_source_payload(
    source_artifacts: Sequence[EntityReadSourceArtifact],
    source_revisions: Sequence[EntityReadSourceRevision],
) -> dict[str, Any]:
    return {
        "source_artifacts": [
            {
                "source_artifact_id": item.source_artifact_id,
                "status": item.status,
                "current_revision_id": item.current_revision_id,
                "source_classification": item.source_classification,
                "authority": item.authority,
            }
            for item in source_artifacts
        ],
        "source_revisions": [
            {
                "source_revision_id": item.source_revision_id,
                "source_artifact_id": item.source_artifact_id,
                "content_sha256": item.content_sha256,
            }
            for item in source_revisions
        ],
    }


def evidence_location_payload(evidence: ParsedEvidenceRef) -> dict[str, Any]:
    return {
        "evidence_ref_id": evidence.evidence_ref_id,
        "source_artifact_id": evidence.source_artifact_id,
        "source_revision_id": evidence.source_revision_id,
        "evidence_role": evidence.evidence_role,
        "can_open_source": evidence.can_open_source,
        "can_highlight_span": evidence.can_highlight_span,
        "locator": evidence.locator,
        "uri": evidence.uri,
        "source_locator": evidence.source_locator,
        "line_ref": evidence.line_ref,
        "source_span_ref_id": evidence.source_span_ref_id,
    }


def compute_anchor_identity_digest(
    *,
    context: KnowledgeReadContext,
    evidence: ParsedEvidenceRef,
    source_artifacts: Sequence[EntityReadSourceArtifact],
    source_revisions: Sequence[EntityReadSourceRevision],
) -> str:
    payload = {
        "schema": ANCHOR_SCHEMA_VERSION,
        "context_binding_digest": context_binding_digest(context),
        **evidence_location_payload(evidence),
        **visible_source_payload(source_artifacts, source_revisions),
    }
    return canonical_sha256(payload)


def encode_anchor_token(*, evidence_ref_id: str, identity_digest: str) -> str:
    canonical = canonical_json(
        {
            "version": 1,
            "evidence_ref_id": evidence_ref_id,
            "identity_digest": identity_digest,
        }
    )
    packed = base64.urlsafe_b64encode(canonical.encode("utf-8")).decode("ascii").rstrip("=")
    return f"{ANCHOR_TOKEN_PREFIX}{packed}"


def decode_anchor_token(anchor_id: str) -> tuple[str, str] | None:
    if not isinstance(anchor_id, str) or not anchor_id:
        return None
    if len(anchor_id) > MAX_ANCHOR_TOKEN_LENGTH:
        return None
    if not anchor_id.startswith(ANCHOR_TOKEN_PREFIX):
        return None
    packed = anchor_id[len(ANCHOR_TOKEN_PREFIX) :]
    if packed == "":
        return None
    padding = "=" * ((4 - len(packed) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode(packed + padding)
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("version") != 1:
        return None
    evidence_ref_id = payload.get("evidence_ref_id")
    identity_digest = payload.get("identity_digest")
    if not isinstance(evidence_ref_id, str) or evidence_ref_id == "":
        return None
    if not isinstance(identity_digest, str) or identity_digest == "":
        return None
    if set(payload) != {"version", "evidence_ref_id", "identity_digest"}:
        return None
    return evidence_ref_id, identity_digest


def build_source_anchor(
    *,
    context: KnowledgeReadContext,
    evidence: ParsedEvidenceRef,
    source_artifacts: Sequence[EntityReadSourceArtifact],
    source_revisions: Sequence[EntityReadSourceRevision],
    admitted_supporter_assertion_ids: Sequence[str],
) -> SourceAnchor:
    identity_digest = compute_anchor_identity_digest(
        context=context,
        evidence=evidence,
        source_artifacts=source_artifacts,
        source_revisions=source_revisions,
    )
    return SourceAnchor(
        anchor_id=encode_anchor_token(
            evidence_ref_id=evidence.evidence_ref_id,
            identity_digest=identity_digest,
        ),
        evidence_ref_id=evidence.evidence_ref_id,
        source_artifact_id=evidence.source_artifact_id,
        source_revision_id=evidence.source_revision_id,
        evidence_role=evidence.evidence_role,
        can_open_source=evidence.can_open_source,
        can_highlight_span=evidence.can_highlight_span,
        locator=evidence.locator,
        uri=evidence.uri,
        source_locator=evidence.source_locator,
        line_ref=evidence.line_ref,
        source_span_ref_id=evidence.source_span_ref_id,
        admitted_supporter_assertion_ids=tuple(sorted(set(admitted_supporter_assertion_ids))),
    )
