"""Pure admission assembly, immutable validator registry and memory authority."""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from types import MappingProxyType
from typing import Any, NoReturn, Protocol

from ..contracts.publication_admission import (
    ACCEPTED_BYTES,
    GRAPH_BYTES,
    SOURCE_BYTES,
    AdmissionSourceArtifactSnapshotV1,
    AdmissionSourceRevisionSnapshotV1,
    AdmissionSourceSnapshotV1,
    PublicationAdmissionContextV1,
    PublicationAdmissionPolicyV1,
    PublicationAdmissionResultV1,
    bounded_canonical,
    bounded_sha256,
    opaque,
    strict_contract_payload,
)
from ..contracts.semantic_profile import SemanticProfileRef
from ..domain.errors import PersistenceIntegrityError


def denied(reason: str) -> NoReturn:
    raise PersistenceIntegrityError("publication admission refused", details={"reason": reason})


def profile_ref(value: Any) -> SemanticProfileRef | None:
    if value is None:
        return None
    try:
        raw = value.model_dump(mode="json") if isinstance(value, SemanticProfileRef) else value
        ref = SemanticProfileRef.model_validate(raw)
        opaque(ref.profile_id)
        opaque(ref.profile_revision)
        return ref
    except Exception:
        denied("admission_profile_invalid")


def profile_fence_key(ref: SemanticProfileRef) -> int:
    material = {
        "domain": "dm_publication_admission_profile_fence_v1",
        "profile_id": opaque(ref.profile_id),
        "profile_revision": opaque(ref.profile_revision),
    }
    return int.from_bytes(
        hashlib.sha256(bounded_canonical(material, max_bytes=4096)).digest()[:8], "big", signed=True
    )


def verified_profile(state: Any, parent: Any, child: dict[str, Any]) -> SemanticProfileRef | None:
    refs = [
        profile_ref(state.record.plan_ref.semantic_profile),
        profile_ref(parent.graph_payload.get("semantic_profile")),
        profile_ref(child.get("semantic_profile")),
    ]
    if refs[0] != refs[1] or refs[1] != refs[2]:
        denied("admission_profile_mismatch")
    return refs[0]


class PublicationAdmissionValidator(Protocol):
    def validate(
        self, context: bytes, parent_graph: bytes, child_graph: bytes
    ) -> PublicationAdmissionResultV1: ...


class PublicationAdmissionRegistry:
    """Immutable allowlist composed by trusted server code, never a request."""

    def __init__(
        self, entries: tuple[tuple[str, str, PublicationAdmissionValidator], ...] = ()
    ) -> None:
        validators = {}
        for validator_id, version, validator in entries:
            key = (opaque(validator_id), opaque(version))
            if key in validators or not callable(getattr(validator, "validate", None)):
                raise ValueError("duplicate or invalid admission validator")
            validators[key] = validator
        self._validators = MappingProxyType(validators)

    def validate(
        self, policy: PublicationAdmissionPolicyV1, context: bytes, parent: bytes, child: bytes
    ) -> None:
        ref = policy.validator_ref
        validator = self._validators.get((ref.validator_id, ref.validator_version))
        if validator is None:
            denied("validator_unavailable")
        before = tuple(hashlib.sha256(v).digest() for v in (context, parent, child))
        try:
            result = validator.validate(context, parent, child)
            # No callback success booleans, unknown family, exceptions or unchecked
            # model_construct objects may pass the owning gate.
            result = PublicationAdmissionResultV1.model_validate(
                strict_contract_payload(result)
                if isinstance(result, PublicationAdmissionResultV1)
                else result
            )
            if before != tuple(hashlib.sha256(v).digest() for v in (context, parent, child)):
                raise ValueError("changed validator input")
        except Exception:
            denied("validator_failed")
        if result.decision != "accept":
            denied(result.reason)


class InMemoryPublicationAdmissionRepository:
    """ONE authority shared explicitly by graph/review/publication repositories."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._policies: dict[tuple[str, str], dict[str, Any]] = {}
        self._uses: dict[tuple[str, str], tuple[str, bool]] = {}

    def get(self, ref: SemanticProfileRef | None) -> PublicationAdmissionPolicyV1 | None:
        if ref is None:
            return None
        ref = profile_ref(ref)
        if ref is None:
            denied("admission_profile_invalid")
        with self._lock:
            key = (ref.profile_id, ref.profile_revision)
            raw = self._policies.get(key)
            policy = PublicationAdmissionPolicyV1.model_validate(raw) if raw else None
            use = self._uses.get(key)
            if (policy is not None and policy.profile_ref != ref) or (
                use is not None and use[0] != ref.descriptor_sha256
            ):
                denied("admission_profile_conflict")
            if use is not None and use[1] and policy is None:
                denied("admission_policy_unavailable")
            return policy

    def register(self, policy: PublicationAdmissionPolicyV1) -> PublicationAdmissionPolicyV1:
        policy = PublicationAdmissionPolicyV1.model_validate(strict_contract_payload(policy))
        with self._lock:
            existing = self.get(policy.profile_ref)
            key = (policy.profile_ref.profile_id, policy.profile_ref.profile_revision)
            if existing is not None:
                if existing != policy:
                    denied("admission_policy_conflict")
                return existing
            if key in self._uses:
                denied("admission_profile_already_used")
            self._policies[key] = policy.model_dump(mode="json")
            stored = self.get(policy.profile_ref)
            if stored is None:
                denied("admission_policy_unavailable")
            return stored

    def join(self, other: InMemoryPublicationAdmissionRepository) -> None:
        if other is self:
            return
        with self._lock, other._lock:
            for key in (
                set(self._uses) | set(other._uses) | set(self._policies) | set(other._policies)
            ):
                mine = self._policies.get(key)
                theirs = other._policies.get(key)
                mine_use = self._uses.get(key)
                their_use = other._uses.get(key)
                if (
                    (mine is not None and theirs is not None and mine != theirs)
                    or (mine_use is not None and their_use is not None and mine_use != their_use)
                    or (mine is not None and their_use is not None and not their_use[1])
                    or (theirs is not None and mine_use is not None and not mine_use[1])
                ):
                    denied("admission_authority_conflict")
                profiles = [p["profile_ref"] for p in (mine, theirs) if p is not None]
                digests = {p["descriptor_sha256"] for p in profiles}
                digests.update(v[0] for v in (mine_use, their_use) if v is not None)
                if len(digests) > 1:
                    denied("admission_profile_conflict")
            self._policies.update(other._policies)
            self._uses.update(other._uses)

    def record_use(self, ref: SemanticProfileRef | None) -> None:
        with self._lock:
            policy = self.get(ref)
            if ref is not None:
                self._uses[(ref.profile_id, ref.profile_revision)] = (
                    ref.descriptor_sha256,
                    policy is not None,
                )

    @contextmanager
    def transaction(self, ref: SemanticProfileRef | None) -> Iterator[None]:
        # Once use is committed it is immutable: subsequent writes need no
        # registration fence. This avoids serializing unrelated World commits.
        key = (ref.profile_id, ref.profile_revision) if ref is not None else None
        self._lock.acquire()
        if key is None or key in self._uses:
            try:
                self.get(ref)
            finally:
                self._lock.release()
            yield
            return
        try:
            yield
        except BaseException:
            self._uses.pop(key, None)
            raise
        finally:
            self._lock.release()


def admission_source_refs(state: Any) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Complete accepted-set evidence, including accepted non-mutating roles."""
    artifacts: set[str] = set()
    revisions: set[str] = set()
    for assertion in state.reviewed_contribution.assertions:
        if assertion.acceptance_state != "accepted":
            continue
        refs = assertion.evidence_refs
        for ref in refs:
            artifacts.add(opaque(ref.source_artifact_id))
            if ref.source_revision_id is not None:
                revisions.add(opaque(ref.source_revision_id))
        if not refs:
            artifact = (
                assertion.source_artifact_id or state.reviewed_contribution.source_artifact_id
            )
            revision = (
                assertion.source_revision_id or state.reviewed_contribution.source_revision_id
            )
            if artifact is not None:
                artifacts.add(opaque(artifact))
            if revision is not None:
                revisions.add(opaque(revision))
        if len(artifacts) > 4096 or len(revisions) > 4096:
            denied("admission_context_limit_exceeded")
    return tuple(sorted(artifacts)), tuple(sorted(revisions))


def accepted_assertions(state: Any) -> list[dict[str, Any]]:
    assertions = [
        a for a in state.reviewed_contribution.assertions if a.acceptance_state == "accepted"
    ]
    if len(assertions) > 4096:
        denied("admission_context_limit_exceeded")
    result = []
    for assertion in sorted(assertions, key=lambda a: a.assertion_id):
        # Check raw nested JSON before coercive dumping (enums live outside
        # JSON attributes in the contract and are serialized by its own schema).
        bounded_canonical(assertion.temporal_scope, max_bytes=ACCEPTED_BYTES)
        result.append(assertion.model_dump(mode="json"))
    bounded_canonical(result, max_bytes=ACCEPTED_BYTES)
    return result


def source_projection(snapshot: Any) -> AdmissionSourceSnapshotV1:
    from .source_provenance_snapshot import SourceProvenanceSnapshot

    if not isinstance(snapshot, SourceProvenanceSnapshot):
        denied("admission_source_snapshot_unavailable")
    # Read this snapshot's already-isolated records without deep-copying rich,
    # unretained URI/lineage fields through its public caller-copy accessors.
    artifact_records = snapshot._artifacts
    revision_records = snapshot._revisions
    if any(
        len(values) > 4096
        for values in (
            snapshot.requested_artifact_ids,
            snapshot.requested_revision_ids,
            artifact_records,
            revision_records,
        )
    ):
        denied("admission_context_limit_exceeded")
    artifacts = []
    for artifact in artifact_records.values():
        from enum import Enum

        fields = {}
        for key in AdmissionSourceArtifactSnapshotV1.model_fields:
            if key in ("schema_version", "source_schema_version"):
                continue
            value = getattr(artifact, key, None)
            fields[key] = value.value if isinstance(value, Enum) else value
        workspace = fields["workspace_document_ref"]
        if workspace is not None:
            fields["workspace_document_ref"] = {
                "document_id": workspace.document_id,
                "revision": workspace.revision,
            }
        artifacts.append(
            AdmissionSourceArtifactSnapshotV1(
                source_schema_version=artifact.schema_version, **fields
            )
        )
    revisions = []
    for revision in revision_records.values():
        revisions.append(
            AdmissionSourceRevisionSnapshotV1(
                source_schema_version=revision.schema_version,
                **{
                    key: getattr(revision, key)
                    for key in (
                        "source_revision_id",
                        "source_artifact_id",
                        "content_sha256",
                        "body_storage",
                    )
                },
            )
        )
    return AdmissionSourceSnapshotV1(
        requested_artifact_ids=sorted(snapshot.requested_artifact_ids),
        requested_revision_ids=sorted(snapshot.requested_revision_ids),
        missing_artifact_ids=sorted(snapshot.requested_artifact_ids - artifact_records.keys()),
        missing_revision_ids=sorted(snapshot.requested_revision_ids - revision_records.keys()),
        artifacts=sorted(artifacts, key=lambda v: v.source_artifact_id),
        revisions=sorted(revisions, key=lambda v: v.source_revision_id),
    )


def context_for(
    state: Any, parent: Any, command: Any, policy: PublicationAdmissionPolicyV1, snapshot: Any
) -> tuple[PublicationAdmissionContextV1, bytes, bytes]:
    try:
        parent_bytes = bounded_canonical(parent.graph_payload, max_bytes=GRAPH_BYTES)
        child_bytes = bounded_canonical(command.graph_payload, max_bytes=GRAPH_BYTES)
        if (
            hashlib.sha256(parent_bytes).hexdigest() != command.parent_graph_payload_sha256
            or hashlib.sha256(child_bytes).hexdigest() != command.graph_payload_sha256
        ):
            denied("admission_payload_mismatch")
        assertions = accepted_assertions(state)
        sources = source_projection(snapshot)
        record = state.record
        context = PublicationAdmissionContextV1(
            review_id=record.review_id,
            reviewed_contribution_sha256=record.reviewed_contribution_sha256,
            review_intent_sha256=record.review_intent_sha256,
            accepted_assertions=assertions,
            accepted_assertions_sha256=bounded_sha256(assertions, max_bytes=ACCEPTED_BYTES),
            parent_revision_id=command.expected_parent_revision_id,
            parent_graph_payload_sha256=command.parent_graph_payload_sha256,
            child_revision_id=command.expected_published_revision_id,
            child_graph_payload_sha256=command.graph_payload_sha256,
            admission_policy_ref=policy.reference,
            validator_ref=policy.validator_ref,
            catalog_refs=policy.catalog_refs,
            source_snapshot=sources,
            source_snapshot_sha256=bounded_sha256(
                sources.model_dump(mode="json"), max_bytes=SOURCE_BYTES
            ),
        )
        verify_source_closure(state, context)
        return context, parent_bytes, child_bytes
    except (ValueError, TypeError):
        denied("admission_context_limit_exceeded")


def verify_source_closure(state: Any, context: PublicationAdmissionContextV1) -> None:
    artifacts, revisions = admission_source_refs(state)
    snapshot = context.source_snapshot
    if (
        snapshot.requested_artifact_ids != sorted(artifacts)
        or snapshot.requested_revision_ids != sorted(revisions)
        or snapshot.missing_artifact_ids
        or snapshot.missing_revision_ids
    ):
        denied("admission_source_closure_mismatch")
    artifact_map = {a.source_artifact_id: a for a in snapshot.artifacts}
    revision_map = {r.source_revision_id: r for r in snapshot.revisions}
    for artifact in snapshot.artifacts:
        if artifact.world_id != state.record.world_id:
            denied("admission_source_identity_mismatch")
    for revision in snapshot.revisions:
        if revision.source_artifact_id not in artifact_map:
            denied("admission_source_identity_mismatch")
    for assertion in state.reviewed_contribution.assertions:
        if assertion.acceptance_state != "accepted":
            continue
        for ref in assertion.evidence_refs:
            if ref.source_revision_id is not None and (
                ref.source_revision_id not in revision_map
                or revision_map[ref.source_revision_id].source_artifact_id != ref.source_artifact_id
            ):
                denied("admission_source_identity_mismatch")


def require_command_policy(command: Any, policy: PublicationAdmissionPolicyV1 | None) -> None:
    from ..contracts.review_publication import FinalizedReviewPublicationCommandV2

    if policy is None:
        if isinstance(command, FinalizedReviewPublicationCommandV2):
            denied("admission_policy_unavailable")
    elif (
        not isinstance(command, FinalizedReviewPublicationCommandV2)
        or command.admission_policy_ref != policy.reference
        or command.validator_ref != policy.validator_ref
    ):
        denied("admission_policy_mismatch")


def verify_receipt(
    publication: Any,
    state: Any,
    parent: Any,
    child: Any,
    policy: PublicationAdmissionPolicyV1 | None,
) -> None:
    from ..contracts.review_publication import FinalizedReviewPublicationV2

    ref = verified_profile(state, parent, child.graph_payload)
    if isinstance(publication, FinalizedReviewPublicationV2):
        if policy is None or policy.profile_ref != ref:
            denied("admission_policy_unavailable")
        context = publication.admission_context
        if (
            publication.admission_policy_ref != policy.reference
            or publication.validator_ref != policy.validator_ref
            or context.admission_policy_ref != policy.reference
            or context.validator_ref != policy.validator_ref
            or context.catalog_refs != policy.catalog_refs
            or context.review_id != publication.review_id
            or context.reviewed_contribution_sha256 != publication.reviewed_contribution_sha256
            or context.review_intent_sha256 != publication.review_intent_sha256
            or context.parent_revision_id != publication.expected_parent_revision_id
            or context.child_revision_id != publication.published_revision_id
            or context.parent_graph_payload_sha256 != publication.parent_graph_payload_sha256
            or context.child_graph_payload_sha256 != publication.graph_payload_sha256
            or context.accepted_assertions_sha256
            != bounded_sha256(accepted_assertions(state), max_bytes=ACCEPTED_BYTES)
            or bounded_sha256(parent.graph_payload, max_bytes=GRAPH_BYTES)
            != context.parent_graph_payload_sha256
            or bounded_sha256(child.graph_payload, max_bytes=GRAPH_BYTES)
            != context.child_graph_payload_sha256
        ):
            denied("admission_receipt_mismatch")
        verify_source_closure(state, context)
    elif policy is not None:
        denied("admission_legacy_protected_receipt")


def verify_retained_revisions(publication: Any, revision_loader: Any) -> None:
    from ..contracts.review_publication import FinalizedReviewPublicationV2

    if not isinstance(publication, FinalizedReviewPublicationV2):
        return
    for retained in publication.admission_context.source_snapshot.revisions:
        actual = revision_loader(retained.source_revision_id)
        if actual is None or any(
            getattr(actual, name) != getattr(retained, name)
            for name in (
                "source_revision_id",
                "source_artifact_id",
                "content_sha256",
                "body_storage",
            )
        ):
            denied("admission_source_revision_mismatch")
