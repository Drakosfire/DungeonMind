"""Historical JSON Schema locks for immutable v1 evidence/source contracts.

Pydantic emits class docstrings into ``model_json_schema()`` as the schema
``description``. A documentation-only edit to ``EvidenceRef`` or
``SourceArtifact`` therefore changes the public wire schema — including any
downstream digest-pinned packet that embeds those models (e.g. the D&D threat
candidate packet). These digests pin the historical v1 schemas directly so a
future "docs-only" edit fails closed without relying solely on the threat suite.
"""

from __future__ import annotations

from dungeonmind.contracts.evidence import EvidenceRef, SourceArtifact, SourceRevision
from dungeonmind.domain.canonical import canonical_sha256

# Digests of model_json_schema() as of DungeonMind main at the PR #25 base
# (post-#24). Do not refresh these because a docstring or field description
# changed — restore the historical contract instead (ADR-0015 / v1 immutability).
EVIDENCE_REF_V1_SCHEMA_DIGEST = (
    "f46eee08ca158ee994b57eb13dad97c83c1dc0880e0af403eb27ff55f5b87bd4"
)
SOURCE_ARTIFACT_V1_SCHEMA_DIGEST = (
    "b1f8f069c71ce19a63407c527641f75b22361433ebe9544853a0b5692b3c4723"
)
SOURCE_REVISION_V1_SCHEMA_DIGEST = (
    "43fcb3188bdb5cbe7768c0cbcde070a24da0f63afa87dfd8aa0ec15288a1801d"
)


def test_evidence_ref_v1_json_schema_is_digest_pinned() -> None:
    schema = EvidenceRef.model_json_schema()
    assert schema.get("description") == (
        "A durable pointer from graph knowledge to its evidentiary basis."
    )
    assert canonical_sha256(schema) == EVIDENCE_REF_V1_SCHEMA_DIGEST
    assert canonical_sha256(EvidenceRef.model_json_schema()) == EVIDENCE_REF_V1_SCHEMA_DIGEST


def test_source_artifact_v1_json_schema_is_digest_pinned() -> None:
    schema = SourceArtifact.model_json_schema()
    assert schema.get("description") == (
        "A registered source of evidentiary authority (e.g. one recap document).\n\n"
        "Identity fields are immutable after create. Body hashes belong on\n"
        "``SourceRevision``. ``current_revision_id`` may be advanced by a typed\n"
        "lifecycle operation; put/create is exact-replay idempotent only."
    )
    assert canonical_sha256(schema) == SOURCE_ARTIFACT_V1_SCHEMA_DIGEST


def test_source_revision_v1_json_schema_is_digest_pinned() -> None:
    assert (
        canonical_sha256(SourceRevision.model_json_schema())
        == SOURCE_REVISION_V1_SCHEMA_DIGEST
    )
