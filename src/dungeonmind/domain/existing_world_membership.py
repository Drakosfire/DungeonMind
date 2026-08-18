"""Canonical exact-membership digest for existing-world adoption receipts.

One ``membership_sha256`` proves the exact adopted durable history membership
— identity AND payload — across the four families: source artifacts, source
revisions, contributions, and identity decisions. Each family contributes
sorted ``(record_id, record_fingerprint)`` pairs under the domain-separated
``dm_existing_world_adoption_membership_v1`` canonical envelope. The v2
receipt's four counts remain diagnostics; they are not sufficient proof of
exact membership (same-cardinality substitution hides under counts).

``record_fingerprint`` is ``canonical_sha256(record.model_dump(mode="json"))``,
which matches the persistence adapters' ``model_fingerprint`` semantics for
these four record families (none carries an embedding field). The same helper
is used at adoption emission, at steward-supervised v2→v3 promotion, and on
the read-only correspondence path, so all three agree on one canonical form.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..contracts.contribution import GraphContribution, GraphContributionV2
from ..contracts.evidence import SourceArtifact, SourceArtifactV2, SourceRevision
from ..contracts.identity import IdentityDecisionRecord, IdentityDecisionRecordV2
from .canonical import canonical_sha256
from .errors import PersistenceIntegrityError

EXISTING_WORLD_ADOPTION_MEMBERSHIP_SCHEMA = "dm_existing_world_adoption_membership_v1"

MembershipSourceArtifact = SourceArtifact | SourceArtifactV2
MembershipContribution = GraphContribution | GraphContributionV2
MembershipIdentityDecision = IdentityDecisionRecord | IdentityDecisionRecordV2


def _family_pairs(
    records: Iterable[object],
    *,
    id_field: str,
    family: str,
) -> list[dict[str, str]]:
    pairs: dict[str, str] = {}
    for record in records:
        record_id = getattr(record, id_field)
        if not isinstance(record_id, str) or not record_id.strip():
            raise PersistenceIntegrityError(
                "existing-world adoption membership record id is invalid",
                details={
                    "reason": "membership_invalid_record_id",
                    "family": family,
                    "record_id": repr(record_id),
                },
            )
        if record_id in pairs:
            raise PersistenceIntegrityError(
                "existing-world adoption membership contains a duplicate record id",
                details={
                    "reason": "membership_duplicate_record_id",
                    "family": family,
                    "record_id": record_id,
                },
            )
        pairs[record_id] = canonical_sha256(record.model_dump(mode="json"))  # type: ignore[attr-defined]
    return [
        {"record_id": record_id, "record_fingerprint": fingerprint}
        for record_id, fingerprint in sorted(pairs.items())
    ]


def existing_world_adoption_membership_sha256(
    *,
    source_artifacts: Iterable[MembershipSourceArtifact],
    source_revisions: Iterable[SourceRevision],
    contributions: Iterable[MembershipContribution],
    identity_decisions: Iterable[MembershipIdentityDecision],
) -> str:
    """Canonical SHA-256 over the four adopted history families.

    Records within each family are reduced to ``(record_id,
    record_fingerprint)`` pairs and sorted by record id before hashing, so the
    digest is deterministic regardless of enumeration order. Duplicate ids are
    invalid before hashing and fail closed.
    """
    envelope = {
        "schema_version": EXISTING_WORLD_ADOPTION_MEMBERSHIP_SCHEMA,
        "source_artifacts": _family_pairs(
            source_artifacts,
            id_field="source_artifact_id",
            family="source_artifacts",
        ),
        "source_revisions": _family_pairs(
            source_revisions,
            id_field="source_revision_id",
            family="source_revisions",
        ),
        "contributions": _family_pairs(
            contributions,
            id_field="contribution_id",
            family="contributions",
        ),
        "identity_decisions": _family_pairs(
            identity_decisions,
            id_field="decision_id",
            family="identity_decisions",
        ),
    }
    return canonical_sha256(envelope)
