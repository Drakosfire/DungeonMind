"""Explicit V7 publication and historical proof on the owning SQL transaction."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

from psycopg import Connection, sql

from ...application.graph_snapshot import GraphSnapshotReader
from ...application.publication_admission import (
    admission_source_refs,
    context_for,
    denied,
    require_command_policy,
    verified_profile,
)
from ...application.repositories import (
    ContributionReviewRepository,
    DurableIdentityHistoryRecord,
    FinalizedReviewPublicationRepository,
    WorldGraphRepository,
)
from ...application.review_publication import validate_reviewed_identity_publication_preconditions
from ...application.review_publication_v7_proof import (
    make_v7_receipt,
    reprove_v7_delta,
    validate_v7_identity,
    verify_v7_history,
)
from ...application.source_description_correction import (
    SourceDescriptionCorrectionProof,
    verify_source_description_corrections,
)
from ...application.source_provenance_snapshot import SourceProvenanceSnapshot
from ...contracts.contribution_review_v3 import ContributionReviewStateV3
from ...contracts.contribution_review_v4 import ContributionReviewStateV4
from ...contracts.contribution_review_v5 import ContributionReviewStateV5
from ...contracts.evidence import SourceRevision
from ...contracts.graph import PublishRevisionCommand, StoredGraphRevision
from ...contracts.publication_admission import CONTEXT_BYTES, GRAPH_BYTES, bounded_canonical
from ...contracts.review_publication import (
    FinalizedReviewPublication,
    FinalizedReviewPublicationCommandV3,
    FinalizedReviewPublicationV3,
)
from ...domain.errors import PersistenceIntegrityError
from .database import SCHEMA, lock_world
from .publication_admission import get_policy, lock_profile
from .records import _IDENTITY_SELECT, _REVISION_SELECT, _return_identity, _return_revision

if TYPE_CHECKING:
    from .review_publication import PostgresFinalizedReviewPublicationRepository

TypedReview = ContributionReviewStateV3 | ContributionReviewStateV4 | ContributionReviewStateV5


def _history(
    conn: Connection[Any], world: str, *, locked: bool = False
) -> list[DurableIdentityHistoryRecord]:
    rows = conn.execute(
        sql.SQL(
            f"SELECT {_IDENTITY_SELECT} FROM {{}}.identity_decisions "
            "WHERE world_id=%s ORDER BY decision_id" + (" FOR SHARE" if locked else "")
        ).format(sql.Identifier(SCHEMA)),
        (world,),
    ).fetchall()
    return [_return_identity(row) for row in rows]


def _typed(state: Any) -> TypedReview:
    if not isinstance(
        state, (ContributionReviewStateV3, ContributionReviewStateV4, ContributionReviewStateV5)
    ):
        raise PersistenceIntegrityError("V7 typed confirmed review missing")
    return state


def _correction(
    repo: PostgresFinalizedReviewPublicationRepository,
    conn: Connection[Any],
    state: TypedReview,
    parent: StoredGraphRevision,
    *,
    locked: bool = False,
) -> SourceDescriptionCorrectionProof | None:
    # Every ancestry/source read uses this connection, including uncommitted
    # receipts during post-insert reconstruction. No independent snapshot.
    from .review_publication import _PUBLICATION_SELECT

    def publication(world: str, revision: str) -> FinalizedReviewPublication | None:
        row = conn.execute(
            sql.SQL(
                f"SELECT {_PUBLICATION_SELECT} FROM {{}}.finalized_review_publications "
                "WHERE world_id=%s AND published_revision_id=%s"
            ).format(sql.Identifier(SCHEMA)),
            (world, revision),
        ).fetchone()
        return repo._load_verified(conn, row) if row is not None else None

    graph = SimpleNamespace(
        get_revision=lambda world, revision: repo._load_revision(
            conn, world_id=world, revision_id=revision
        )
    )
    reviews = SimpleNamespace(
        get=lambda world, review: repo._load_review(conn, world_id=world, review_id=review)
    )
    publications = SimpleNamespace(
        get_for_published_revision=publication,
        get_provenance_snapshot=lambda **kw: repo._locked_source_snapshot(conn, lock=locked, **kw),
    )
    return verify_source_description_corrections(
        state,
        parent=parent,
        world_graph=cast(WorldGraphRepository, graph),
        reviews=cast(ContributionReviewRepository, reviews),
        publications=cast(FinalizedReviewPublicationRepository, publications),
    )


def verify_history(
    repo: PostgresFinalizedReviewPublicationRepository,
    conn: Connection[Any],
    receipt: FinalizedReviewPublicationV3,
    state: Any,
    parent: StoredGraphRevision,
    child: StoredGraphRevision,
) -> None:
    def revision(key: str) -> SourceRevision | None:
        row = conn.execute(
            sql.SQL(
                f"SELECT {_REVISION_SELECT} FROM {{}}.source_revisions WHERE source_revision_id=%s"
            ).format(sql.Identifier(SCHEMA)),
            (key,),
        ).fetchone()
        return _return_revision(row) if row is not None else None

    typed = _typed(state)
    verify_v7_history(
        receipt,
        typed,
        parent,
        child,
        [d.model_dump(mode="json") for d in _history(conn, receipt.world_id)],
        revision,
        repo._v7_graph_reader,
        correction_proof=_correction(repo, conn, typed, parent),
    )


def publish_v7(
    repo: PostgresFinalizedReviewPublicationRepository, command: FinalizedReviewPublicationCommandV3
) -> FinalizedReviewPublicationV3:
    from .review_publication import (
        _publication_row,
        _record_from_revision,
        _revision_row,
        _validate_parent_revision,
        _validate_review_binding,
    )

    try:
        raw = bounded_canonical(command.graph_payload, max_bytes=GRAPH_BYTES)
    except (TypeError, ValueError, RecursionError):
        raise PersistenceIntegrityError("V7 raw graph invalid") from None
    command = cast(FinalizedReviewPublicationCommandV3, repo._reload_command(command))
    if raw != bounded_canonical(command.graph_payload, max_bytes=GRAPH_BYTES):
        raise PersistenceIntegrityError("V7 raw graph changed on reload")
    reader: GraphSnapshotReader | None = repo._v7_graph_reader
    if reader is None:
        raise PersistenceIntegrityError("V7 publication authority unavailable")
    with repo._database.transaction() as conn:
        isolation = conn.execute("SHOW transaction_isolation").fetchone()
        if isolation is None or isolation["transaction_isolation"] != "read committed":
            raise PersistenceIntegrityError("V7 publication requires READ COMMITTED")
        lock_world(conn, command.world_id, created_at=command.requested_published_at)
        state = _typed(
            repo._load_review(conn, world_id=command.world_id, review_id=command.review_id)
        )
        _validate_review_binding(command, state)
        parent = repo._load_revision(
            conn, world_id=command.world_id, revision_id=command.expected_parent_revision_id
        )
        _validate_parent_revision(
            parent,
            world_id=command.world_id,
            parent_revision_id=command.expected_parent_revision_id,
            graph_schema=command.parent_graph_schema,
            graph_payload_sha256=command.parent_graph_payload_sha256,
        )
        existing = _publication_row(
            conn,
            world_id=command.world_id,
            review_id=command.review_id,
            operation_id=command.operation_id,
            published_revision_id=command.expected_published_revision_id,
        )
        if existing is not None:
            receipt = repo._load_verified(conn, existing)
            repo._validate_command_record(command, receipt)
            if not isinstance(receipt, FinalizedReviewPublicationV3):
                raise PersistenceIntegrityError("V7 replay family differs")
            return receipt
        profile = verified_profile(state, parent, command.graph_payload)
        lock_profile(conn, profile)
        policy = get_policy(conn, profile)
        require_command_policy(command, policy)
        artifacts, revisions = admission_source_refs(state)
        guard = getattr(state.record, "reviewed_identity_preconditions", None)
        all_artifacts, all_revisions = set(artifacts), set(revisions)
        if guard is not None:
            all_artifacts.update(s.source_artifact_id for s in guard.sources)
            all_revisions.update(s.source_revision_id for s in guard.sources)
        sources = repo._locked_source_snapshot(
            conn,
            artifact_ids=tuple(sorted(all_artifacts)),
            revision_ids=tuple(sorted(all_revisions)),
        )
        decisions = _history(conn, command.world_id, locked=True)
        history = [d.model_dump(mode="json") for d in decisions]
        if guard is not None:
            validate_reviewed_identity_publication_preconditions(
                guard, parent=parent, decisions=decisions, sources=sources
            )
        validate_v7_identity(state, parent, history)
        reprove_v7_delta(
            command,
            state,
            parent,
            sources,
            reader,
            correction_proof=_correction(repo, conn, state, parent, locked=True),
        )
        context = None
        if policy is not None:
            accepted_sources = SourceProvenanceSnapshot.from_loaded(
                requested_artifact_ids=frozenset(artifacts),
                requested_revision_ids=frozenset(revisions),
                artifacts={k: sources.artifacts[k] for k in artifacts if k in sources.artifacts},
                revisions={k: sources.revisions[k] for k in revisions if k in sources.revisions},
            )
            context, before, after = context_for(state, parent, command, policy, accepted_sources)
            repo._admission_registry.validate(
                policy,
                bounded_canonical(context.model_dump(mode="json"), max_bytes=CONTEXT_BYTES),
                before,
                after,
            )
        if (
            _revision_row(
                conn, world_id=command.world_id, revision_id=command.expected_published_revision_id
            )
            is not None
        ):
            denied("admission_raw_revision_adoption_forbidden")
        revision = repo._graph._publish_revision_in_transaction(
            conn,
            PublishRevisionCommand(
                world_id=command.world_id,
                parent_revision_id=command.expected_parent_revision_id,
                expected_parent_revision_id=command.expected_parent_revision_id,
                operation_ids=[command.operation_id],
                graph_schema=command.graph_schema,
                graph_payload=command.graph_payload,
                created_at=command.requested_published_at,
            ),
            world_locked=True,
        )
        if repo._failure_hook is not None:
            repo._failure_hook()
        receipt = make_v7_receipt(
            _record_from_revision(command, revision),
            command,
            sources,
            history,
            admission_context=context,
        )
        row = repo._insert_publication(conn, receipt)
        if repo._failure_hook is not None:
            repo._failure_hook()
        verified = repo._load_verified(conn, row)
        if not isinstance(verified, FinalizedReviewPublicationV3):
            raise PersistenceIntegrityError("V7 stored receipt family differs")
        return verified
