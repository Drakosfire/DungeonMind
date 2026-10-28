"""Owning V7 semantic delta and historical replay proof, shared by both UoWs."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from ..contracts.contribution import AcceptanceState
from ..contracts.contribution_review_v3 import ContributionReviewStateV3
from ..contracts.contribution_review_v4 import ContributionReviewStateV4
from ..contracts.contribution_review_v5 import ContributionReviewStateV5
from ..contracts.evidence import SourceRevision
from ..contracts.graph import StoredGraphRevision
from ..contracts.review_publication import (
    FinalizedReviewPublication,
    FinalizedReviewPublicationCommandV3,
    FinalizedReviewPublicationV3,
    RetainedPublicationSourcesV1,
)
from ..domain.canonical import canonical_sha256
from ..domain.errors import PersistenceIntegrityError
from .graph_snapshot import GraphSnapshotReader
from .review_materialization_v7 import materialize_finalized_review_v7
from .source_provenance_snapshot import SourceProvenanceSnapshot


def validate_v7_identity(
    state: ContributionReviewStateV3 | ContributionReviewStateV4 | ContributionReviewStateV5,
    parent: StoredGraphRevision,
    history: Sequence[dict[str, Any]],
) -> None:
    existing = {o["object_id"] for o in parent.graph_payload["objects"]}
    targets = {
        target
        for assertion in state.reviewed_contribution.assertions
        if assertion.acceptance_state is AcceptanceState.ACCEPTED
        for target in (assertion.subject_object_id, assertion.object_object_id)
        if target in existing
    }
    superseded = {
        did
        for d in history
        if d.get("status", "active") == "active"
        for did in d.get("supersedes_decision_ids", [])
    }
    for d in history:
        if d.get("world_id") != state.record.world_id:
            raise PersistenceIntegrityError("v7 identity World mismatch")
        if d.get("status", "active") != "active" or d["decision_id"] in superseded:
            continue
        if d.get("source_object_id") in targets or (
            d.get("decision_kind") in {"merge", "split"}
            and any(
                t in d.get("subject_object_ids", []) and d.get("target_object_ids") != [t]
                for t in targets
            )
        ):
            raise PersistenceIntegrityError("v7 identity target is redirected")


def retained_sources(snapshot: SourceProvenanceSnapshot) -> RetainedPublicationSourcesV1:
    if set(snapshot.artifacts) != set(snapshot.requested_artifact_ids) or set(
        snapshot.revisions
    ) != set(snapshot.requested_revision_ids):
        raise PersistenceIntegrityError("v7 source closure incomplete")
    return RetainedPublicationSourcesV1(
        artifacts=tuple(v for _, v in sorted(snapshot.artifacts.items())),
        revisions=tuple(v for _, v in sorted(snapshot.revisions.items())),
    )


def historical_sources(value: RetainedPublicationSourcesV1) -> SourceProvenanceSnapshot:
    return SourceProvenanceSnapshot.from_loaded(
        requested_artifact_ids=frozenset(a.source_artifact_id for a in value.artifacts),
        requested_revision_ids=frozenset(r.source_revision_id for r in value.revisions),
        artifacts={a.source_artifact_id: a for a in value.artifacts},
        revisions={r.source_revision_id: r for r in value.revisions},
    )


def reprove_v7_delta(
    command: FinalizedReviewPublicationCommandV3,
    state: Any,
    parent: StoredGraphRevision,
    sources: SourceProvenanceSnapshot,
    graph_reader: GraphSnapshotReader | None,
    *,
    correction_proof: Any = None,
) -> None:
    if graph_reader is None or not isinstance(
        state, (ContributionReviewStateV3, ContributionReviewStateV4, ContributionReviewStateV5)
    ):
        raise PersistenceIntegrityError("v7 publication capability unavailable")
    if parent.revision.graph_schema != command.parent_graph_schema:
        raise PersistenceIntegrityError("v7 parent schema differs")
    result = materialize_finalized_review_v7(
        state,
        parent=parent,
        graph_reader=graph_reader,
        source_snapshot=sources,
        source_description_correction_proof=correction_proof,
    )
    if result.graph_payload != command.graph_payload or (
        result.graph_payload_sha256 != command.graph_payload_sha256
    ):
        raise PersistenceIntegrityError("v7 publication differs from reviewed semantic delta")


def make_v7_receipt(
    base: FinalizedReviewPublication,
    command: FinalizedReviewPublicationCommandV3,
    sources: SourceProvenanceSnapshot,
    history: Sequence[dict[str, Any]],
    *,
    admission_context: Any = None,
) -> FinalizedReviewPublicationV3:
    source_proof = retained_sources(sources)
    return FinalizedReviewPublicationV3(
        **base.model_dump(mode="python", exclude={"schema_version"}),
        parent_graph_schema=command.parent_graph_schema,
        admission_policy_ref=command.admission_policy_ref,
        validator_ref=command.validator_ref,
        admission_context=admission_context,
        admission_context_sha256=(
            canonical_sha256(admission_context.model_dump(mode="json"))
            if admission_context is not None
            else None
        ),
        retained_sources=source_proof,
        retained_sources_sha256=canonical_sha256(source_proof.model_dump(mode="json")),
        identity_history=tuple(history),
        identity_history_sha256=canonical_sha256(history),
    )


def verify_v7_history(
    receipt: FinalizedReviewPublicationV3,
    state: Any,
    parent: StoredGraphRevision,
    child: StoredGraphRevision,
    current_history: Sequence[dict[str, Any]],
    revision_loader: Callable[[str], SourceRevision | None],
    graph_reader: GraphSnapshotReader | None,
    *,
    correction_proof: Any = None,
) -> None:
    receipt = FinalizedReviewPublicationV3.model_validate(receipt.model_dump(mode="json"))
    current = {d["decision_id"]: d for d in current_history}
    if len(current) != len(current_history) or any(
        current.get(d["decision_id"]) != d for d in receipt.identity_history
    ):
        raise PersistenceIntegrityError("v7 historical identity authority changed")
    for old in receipt.retained_sources.revisions:
        actual = revision_loader(old.source_revision_id)
        if actual is None or any(
            getattr(actual, k) != getattr(old, k)
            for k in (
                "source_revision_id",
                "source_artifact_id",
                "content_sha256",
                "body_storage",
            )
        ):
            raise PersistenceIntegrityError("v7 historical source revision changed")
    from .review_publication import validate_reviewed_identity_publication_preconditions

    # Identity guard validation uses the exact immutable records retained at
    # publication, not later superseding decisions or later source standing.
    sources = historical_sources(receipt.retained_sources)
    guard = getattr(state.record, "reviewed_identity_preconditions", None)
    if guard is not None:
        from ..contracts.identity import (
            IdentityDecisionRecord,
            IdentityDecisionRecordV2,
            IdentityReconciliationDecision,
        )

        models = {
            "dm_identity_decision_v1": IdentityDecisionRecord,
            "dm_identity_decision_v2": IdentityDecisionRecordV2,
            "dm_identity_reconciliation_decision_v1": IdentityReconciliationDecision,
        }
        decisions = []
        for row in receipt.identity_history:
            schema = row.get("schema_version")
            if not isinstance(schema, str):
                raise PersistenceIntegrityError("v7 identity schema unavailable")
            model = models.get(schema)
            if model is None:
                raise PersistenceIntegrityError("v7 identity family unavailable")
            decisions.append(model.model_validate(row))

        validate_reviewed_identity_publication_preconditions(
            guard,
            parent=parent,
            decisions=decisions,
            sources=sources,
        )
    validate_v7_identity(state, parent, receipt.identity_history)
    raw = receipt.model_dump(mode="python")
    fields = {
        key: raw[key]
        for key in (
            "world_id",
            "review_id",
            "reviewed_contribution_id",
            "reviewed_contribution_sha256",
            "review_intent_sha256",
            "confirmation_id",
            "operation_id",
            "expected_parent_revision_id",
            "parent_graph_payload_sha256",
            "parent_graph_schema",
            "graph_schema",
            "graph_payload_sha256",
            "admission_policy_ref",
            "validator_ref",
        )
    }
    command = FinalizedReviewPublicationCommandV3(
        **fields,
        expected_published_revision_id=receipt.published_revision_id,
        graph_payload=child.graph_payload,
        requested_published_at=receipt.published_at,
    )
    reprove_v7_delta(
        command, state, parent, sources, graph_reader, correction_proof=correction_proof
    )
