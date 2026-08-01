"""Application-owned Mind Turn orchestration.

Transport-neutral: no FastAPI, Psycopg, fixture paths, or Uvicorn imports.
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from ..agents.protocol import AgentAdapter, AgentTurnContext, sanitize_agent_input
from ..contracts.capability import CapabilityPolicy, GraphScope
from ..contracts.evidence import EvidenceRef, EvidenceRole
from ..contracts.graph import StoredGraphRevision
from ..contracts.mind_turn import (
    ContextChange,
    MindTurnRequest,
    MindTurnResponse,
    SemanticProjection,
    SuggestedAction,
)
from ..contracts.projection import Admissibility, ProjectionSnapshot, ScopeMode
from ..contracts.retrieval import (
    Coverage,
    DiagnosticEntry,
    GraphRetrievalSession,
    OperationOutcome,
    RetrievalOperation,
    RetrievalOperationKind,
    SourceAnchor,
)
from ..contracts.semantic import CandidateChannel, SemanticQuery
from ..contracts.vocabulary import Visibility
from ..domain.canonical import canonical_json, canonical_sha256
from ..domain.errors import (
    HeadNotFoundError,
    IdempotencyConflictError,
    RevisionNotFoundError,
    ScopeResolutionError,
)
from ..domain.fusion import reciprocal_rank_fusion
from .context_assembly import assemble_agent_context
from .graph_scope import (
    STORED_PROVENANCE_INVALID,
    EvidenceScopeVerdict,
    ProvenanceRejection,
    ValidatedProvenance,
    project_scoped_snapshot,
    public_coverage_gaps_for_exclusion,
    resolve_evidence_provenance,
)
from .graph_snapshot import (
    GraphObjectView,
    GraphRelationshipView,
    GraphSnapshotReader,
    ParsedGraphSnapshot,
    VersionedUnionGraphSnapshotReader,
    collect_one_hop_object_ids,
)
from .query_embedding import QueryEmbeddingProvider
from .repositories import (
    MindThreadRepository,
    RetrievalSessionRepository,
    SemanticDocumentRepository,
    SemanticSearchPort,
    SourceRepository,
    WorldGraphRepository,
)

TOP_K_PER_CHANNEL = 5
REQUEST_FINGERPRINT_DIAGNOSTIC = "authorized_request_fingerprint"


@dataclass
class _RequestLockEntry:
    """Reference-counted process-local lock for identical in-flight requests."""

    lock: threading.Lock
    users: int = 0


class Clock(Protocol):
    def now(self) -> datetime: ...


class FixedClock:
    def __init__(self, instant: datetime) -> None:
        self._instant = instant

    def now(self) -> datetime:
        return self._instant


def _stable_id(prefix: str, request_id: str, *parts: str) -> str:
    digest = hashlib.sha256(
        "|".join((request_id, *parts)).encode("utf-8")
    ).hexdigest()
    return f"{prefix}:{digest[:24]}"


def _session_id_for(request_id: str) -> str:
    digest = hashlib.sha256(request_id.encode("utf-8")).hexdigest()
    return f"rse:{digest[:24]}"


def _admissibility_to_visibility(admissibility: Admissibility) -> Visibility:
    return Visibility.GM if admissibility is Admissibility.GM else Visibility.PLAYER



def request_fingerprint(request: MindTurnRequest) -> str:
    """Canonical fingerprint of the complete authorized request."""
    return canonical_sha256(request.model_dump(mode="json"))


def _fingerprint_diagnostic(request: MindTurnRequest) -> DiagnosticEntry:
    return DiagnosticEntry(
        code=REQUEST_FINGERPRINT_DIAGNOSTIC,
        severity="info",
        message="Canonical fingerprint of the authorized MindTurnRequest.",
        data={"fingerprint": request_fingerprint(request)},
    )


def _session_request_fingerprint(session: GraphRetrievalSession) -> str | None:
    for entry in session.diagnostics:
        if entry.code == REQUEST_FINGERPRINT_DIAGNOSTIC:
            value = entry.data.get("fingerprint")
            return str(value) if isinstance(value, str) else None
    return None


class MindTurnService:
    def __init__(
        self,
        *,
        world_graph: WorldGraphRepository,
        retrieval_sessions: RetrievalSessionRepository,
        threads: MindThreadRepository,
        semantic_documents: SemanticDocumentRepository,
        semantic_search: SemanticSearchPort,
        sources: SourceRepository,
        graph_reader: GraphSnapshotReader | None = None,
        query_embedder: QueryEmbeddingProvider,
        agent_adapter: AgentAdapter,
        clock: Clock,
    ) -> None:
        self._world_graph = world_graph
        self._retrieval_sessions = retrieval_sessions
        self._threads = threads
        self._semantic_documents = semantic_documents
        self._semantic_search = semantic_search
        self._sources = sources
        self._graph_reader = graph_reader or VersionedUnionGraphSnapshotReader()
        self._query_embedder = query_embedder
        self._agent_adapter = agent_adapter
        self._clock = clock
        self._agent_invocation_count = 0
        self._request_locks_guard = threading.Lock()
        self._request_locks: dict[tuple[str, str], _RequestLockEntry] = {}

    @property
    def agent_invocation_count(self) -> int:
        return self._agent_invocation_count

    def _acquire_request_lock(
        self, thread_id: str, request_id: str
    ) -> tuple[tuple[str, str], threading.Lock]:
        """Increment the user count and return the shared lock for this request."""
        key = (thread_id, request_id)
        with self._request_locks_guard:
            entry = self._request_locks.get(key)
            if entry is None:
                entry = _RequestLockEntry(lock=threading.Lock(), users=0)
                self._request_locks[key] = entry
            entry.users += 1
            return key, entry.lock

    def _release_request_lock(self, key: tuple[str, str]) -> None:
        """Decrement users; remove the entry only when no waiters/holders remain."""
        with self._request_locks_guard:
            entry = self._request_locks.get(key)
            if entry is None:
                return
            entry.users -= 1
            if entry.users <= 0:
                self._request_locks.pop(key, None)

    def execute(self, request: MindTurnRequest) -> MindTurnResponse:
        # Process-local coordination only. Run the demo host as a single worker.
        key, lock = self._acquire_request_lock(request.thread_id, request.request_id)
        try:
            with lock:
                return self._execute_unlocked(request)
        finally:
            self._release_request_lock(key)

    def _execute_unlocked(self, request: MindTurnRequest) -> MindTurnResponse:
        replay = self._find_replay(request)
        if replay is not None:
            return replay

        session_id = _session_id_for(request.request_id)
        existing_session = self._retrieval_sessions.get(session_id)
        if existing_session is not None:
            response = self._response_from_session(request, existing_session)
            self._threads.append_turn(request, response)
            return response

        now = self._clock.now()
        revision_id, head_revision_id, stored = self._resolve_revision(request)
        snapshot = ProjectionSnapshot(
            world_id=request.world_id,
            campaign_id=request.campaign_id,
            focus=request.focus,
            admissibility=request.admissibility,
            scope_mode=(
                ScopeMode.CAMPAIGN if request.campaign_id is not None else ScopeMode.WORLD
            ),
            revision_id=revision_id,
            head_revision_id=head_revision_id,
            is_head=revision_id == head_revision_id,
            projected_at=now,
        )

        parsed = self._graph_reader.parse(
            graph_schema=stored.revision.graph_schema,
            graph_payload=stored.graph_payload,
        )
        if parsed.world_id != request.world_id:
            raise PersistenceWorldMismatch(parsed.world_id, request.world_id)
        scoped = project_scoped_snapshot(
            parsed,
            sources=self._sources,
            world_id=request.world_id,
            campaign_id=request.campaign_id,
            admissibility=request.admissibility,
        )
        object_exclusions = dict(scoped.object_exclusions)
        parsed = scoped.snapshot

        diagnostics: list[DiagnosticEntry] = [
            _fingerprint_diagnostic(request),
            DiagnosticEntry(
                code="fixture_embedding_provider",
                severity="info",
                message="Using fixture query embedding provider.",
                data={"provider_id": self._query_embedder.provider_id},
            ),
            DiagnosticEntry(
                code="fixture_only_agent",
                severity="info",
                message="Using deterministic fixture agent adapter.",
                data={"adapter_id": self._agent_adapter.adapter_id},
            ),
        ]
        if (
            request.surface_context.selected_document_ref is not None
            or request.surface_context.active_artifact_refs
        ):
            diagnostics.append(
                DiagnosticEntry(
                    code="surface_context_reference_not_resolved",
                    severity="warning",
                    message=(
                        "selected_document_ref and active_artifact_refs are not "
                        "dereferenced in this slice."
                    ),
                )
            )

        operations: list[RetrievalOperation] = []
        embedding = self._query_embedder.embed_query(request.message)
        candidates = self._semantic_search.search(
            SemanticQuery(
                world_id=request.world_id,
                campaign_scope=request.campaign_id,
                visibility=_admissibility_to_visibility(request.admissibility),
                graph_revision_id=revision_id,
                text=request.message,
                embedding=embedding,
                top_k=TOP_K_PER_CHANNEL,
            )
        )
        operations.append(
            RetrievalOperation(
                operation_id=_stable_id("op", request.request_id, "semantic"),
                kind=RetrievalOperationKind.SEMANTIC_CANDIDATES,
                outcome=OperationOutcome.OK if candidates else OperationOutcome.MISS,
                revision_id=revision_id,
                arguments={"top_k": TOP_K_PER_CHANNEL},
                result_count=len(candidates),
            )
        )

        by_channel: dict[CandidateChannel, list[str]] = {
            CandidateChannel.EXACT: [],
            CandidateChannel.LEXICAL: [],
            CandidateChannel.DENSE: [],
        }
        for candidate in sorted(candidates, key=lambda c: (c.channel.value, c.rank)):
            by_channel[candidate.channel].append(candidate.semantic_document_id)

        fused = reciprocal_rank_fusion(
            [
                by_channel[CandidateChannel.EXACT],
                by_channel[CandidateChannel.LEXICAL],
                by_channel[CandidateChannel.DENSE],
            ]
        )
        preflight_ids = [doc_id for doc_id, _score in fused]

        candidate_object_ids: list[str] = []
        coverage = Coverage()
        targeted_excluded_ids: list[str] = []
        for doc_id in preflight_ids:
            doc = self._semantic_documents.get(doc_id)
            if doc is None or not doc.graph_object_id:
                coverage.gap_codes.append("semantic_document_missing_graph_object")
                coverage.missing.append(doc_id)
                continue
            if self._graph_reader.get_object(parsed, doc.graph_object_id) is None:
                coverage.gap_codes.append("candidate_graph_object_missing")
                coverage.missing.append(doc.graph_object_id)
                targeted_excluded_ids.append(doc.graph_object_id)
                continue
            candidate_object_ids.append(doc.graph_object_id)

        # Selected IDs that fail scoping are request-targeted; surface only
        # sanitized / in-scope gaps for those objects — never graph-global dumps.
        for selected_id in request.surface_context.selected_object_ids:
            if self._graph_reader.get_object(parsed, selected_id) is None:
                targeted_excluded_ids.append(selected_id)

        for object_id in dict.fromkeys(targeted_excluded_ids):
            exclusion = object_exclusions.get(object_id)
            if exclusion is None:
                continue
            gap_codes, missing = public_coverage_gaps_for_exclusion(exclusion)
            coverage.gap_codes.extend(gap_codes)
            coverage.missing.extend(missing)

        referents = self._graph_reader.resolve_mentions(
            parsed,
            message=request.message,
            selected_object_ids=list(request.surface_context.selected_object_ids),
            candidate_object_ids=candidate_object_ids,
        )
        operations.append(
            RetrievalOperation(
                operation_id=_stable_id("op", request.request_id, "resolve"),
                kind=RetrievalOperationKind.SEARCH_OBJECTS,
                outcome=(
                    OperationOutcome.OK
                    if any(r.object_id for r in referents)
                    else OperationOutcome.MISS
                ),
                revision_id=revision_id,
                result_count=sum(1 for r in referents if r.object_id),
            )
        )

        seed_ids = sorted(
            {
                *(r.object_id for r in referents if r.object_id),
                *candidate_object_ids,
            }
        )
        focus_ids = collect_one_hop_object_ids(parsed, seed_ids)
        objects: list[GraphObjectView] = []
        for object_id in focus_ids:
            obj = self._graph_reader.get_object(parsed, object_id)
            if obj is None:
                continue
            objects.append(obj)
            operations.append(
                RetrievalOperation(
                    operation_id=_stable_id("op", request.request_id, "get", object_id),
                    kind=RetrievalOperationKind.GET_OBJECT,
                    outcome=OperationOutcome.OK,
                    revision_id=revision_id,
                    arguments={"object_id": object_id},
                    result_count=1,
                )
            )

        relationships = self._graph_reader.list_relationships(parsed, seed_ids)
        operations.append(
            RetrievalOperation(
                operation_id=_stable_id("op", request.request_id, "rels"),
                kind=RetrievalOperationKind.LIST_RELATIONSHIPS,
                outcome=OperationOutcome.OK if relationships else OperationOutcome.MISS,
                revision_id=revision_id,
                arguments={"object_ids": seed_ids},
                result_count=len(relationships),
            )
        )

        evidence, anchors = self._admit_evidence(
            request=request,
            revision_id=revision_id,
            parsed=parsed,
            objects=objects,
            relationships=relationships,
            coverage=coverage,
        )
        for anchor in anchors:
            operations.append(
                RetrievalOperation(
                    operation_id=_stable_id("op", request.request_id, "anchor", anchor.anchor_id),
                    kind=RetrievalOperationKind.READ_SOURCE,
                    outcome=OperationOutcome.OK,
                    revision_id=revision_id,
                    arguments={"anchor_id": anchor.anchor_id},
                    result_count=0,
                    diagnostics={"note": "anchor admitted; source body not opened"},
                )
            )

        if not seed_ids:
            coverage.missing.append(request.message)
            if "missing_support_evidence" not in coverage.gap_codes:
                coverage.gap_codes.append("unresolved_referent")

        assembled = assemble_agent_context(
            revision_id=revision_id,
            world_id=request.world_id,
            campaign_id=request.campaign_id,
            admissibility=request.admissibility,
            focus=request.focus,
            objects=objects,
            relationships=relationships,
            evidence=evidence,
            source_anchors=anchors,
            coverage=coverage,
        )

        policy = CapabilityPolicy(
            policy_id=_stable_id("pol", request.request_id, "readonly"),
            graph_scope=GraphScope(
                world_id=request.world_id,
                campaign_id=request.campaign_id,
                focus=request.focus,
                admissibility=request.admissibility,
                revision_pin=revision_id,
            ),
            enabled_tools=[],
            tool_rules=[],
        )
        agent_input = sanitize_agent_input(
            message=request.message,
            world_id=request.world_id,
            campaign_id=request.campaign_id,
            focus_kind=request.focus.kind,
            focus_session_id=request.focus.session_id,
            admissibility=request.admissibility,
            surface_id=request.surface_context.surface_id,
            surface_mode=request.surface_context.mode,
            selected_object_ids=list(request.surface_context.selected_object_ids),
            assembled_context=assembled,
            revision_id=revision_id,
        )
        # Prove auth metadata never reaches the adapter input document.
        if "caller_id" in assembled or "tenant_id" in assembled or '"roles"' in assembled:
            raise RuntimeError("assembled context leaked authorization metadata")

        self._agent_invocation_count += 1
        agent_result = self._agent_adapter.execute_turn(
            AgentTurnContext(input=agent_input, capability_policy=policy)
        )
        diagnostics.extend(agent_result.diagnostics)
        diagnostics.append(
            DiagnosticEntry(
                code="persisted_turn_answer",
                severity="info",
                message="Deterministic answer retained for session recovery.",
                data={"answer": agent_result.answer},
            )
        )

        claims = list(agent_result.claims)
        # Drop accepted graph facts that lack SUPPORT in the admitted ledger.
        support_ids = {
            item.evidence_ref_id
            for item in evidence
            if item.evidence_role is EvidenceRole.SUPPORT
        }
        filtered_claims = []
        for claim in claims:
            if (
                claim.authority.value == "graph_fact"
                and claim.status.value == "accepted"
                and not any(eid in support_ids for eid in claim.evidence_ref_ids)
            ):
                coverage.gap_codes.append("missing_support_evidence")
                coverage.missing.append(claim.claim_id)
                continue
            filtered_claims.append(claim)

        projections = self._build_projections(
            request_id=request.request_id,
            objects=objects,
            relationships=relationships,
            evidence=evidence,
            seed_ids=seed_ids,
        )
        actions = [
            SuggestedAction(
                action_id=_stable_id("act", request.request_id, anchor.anchor_id),
                kind="open_source",
                label=f"Open {anchor.display_label or anchor.source_artifact_id}",
                arguments={"source_anchor_id": anchor.anchor_id},
            )
            for anchor in anchors
            if anchor.readable
        ]
        context_changes = [
            ContextChange(
                change_id=_stable_id("ctx", request.request_id, "thread"),
                kind="thread_continued",
                payload={"thread_id": request.thread_id},
            )
        ]
        if seed_ids:
            context_changes.append(
                ContextChange(
                    change_id=_stable_id("ctx", request.request_id, "selection"),
                    kind="selection_resolved",
                    payload={"object_ids": seed_ids},
                )
            )

        for obj in objects:
            coverage.known.append(obj.object_id)

        session = GraphRetrievalSession(
            session_id=session_id,
            thread_id=request.thread_id,
            snapshot=snapshot,
            question=request.message,
            referents=referents,
            operations=operations,
            evidence=evidence,
            claims=filtered_claims,
            source_anchors=anchors,
            source_reads=[],
            coverage=coverage,
            diagnostics=diagnostics,
            preflight_candidate_ids=preflight_ids,
            created_at=now,
            updated_at=now,
        )
        self._retrieval_sessions.create(session)

        response = MindTurnResponse(
            request_id=request.request_id,
            turn_id=_stable_id("turn", request.request_id),
            thread_id=request.thread_id,
            world_id=request.world_id,
            campaign_id=request.campaign_id,
            revision_id=revision_id,
            answer=agent_result.answer,
            resolved_referents=referents,
            claims=filtered_claims,
            evidence=evidence,
            source_anchors=anchors,
            source_reads=[],
            semantic_projections=projections,
            suggested_actions=actions,
            context_changes=context_changes,
            coverage=coverage,
            diagnostics=diagnostics,
        )
        self._threads.append_turn(request, response)
        return response

    def _find_replay(self, request: MindTurnRequest) -> MindTurnResponse | None:
        turns = self._threads.list_turns(request.thread_id)
        for prior_request, prior_response in turns:
            if prior_request.request_id != request.request_id:
                continue
            if canonical_json(prior_request.model_dump(mode="json")) != canonical_json(
                request.model_dump(mode="json")
            ):
                raise IdempotencyConflictError(
                    f"request_id {request.request_id!r} already used with a different payload"
                )
            return prior_response
        return None

    def _assert_session_matches_request(
        self,
        request: MindTurnRequest,
        session: GraphRetrievalSession,
    ) -> None:
        """Fail closed when a persisted session is not the originating request."""
        stored_fingerprint = _session_request_fingerprint(session)
        actual_fingerprint = request_fingerprint(request)
        if stored_fingerprint is None or stored_fingerprint != actual_fingerprint:
            raise IdempotencyConflictError(
                f"request_id {request.request_id!r} already used with a different payload",
                details={"reason": "retrieval_session_fingerprint_mismatch"},
            )
        if session.thread_id != request.thread_id:
            raise IdempotencyConflictError(
                f"request_id {request.request_id!r} already used with a different payload",
                details={"reason": "retrieval_session_thread_mismatch"},
            )
        if session.question != request.message:
            raise IdempotencyConflictError(
                f"request_id {request.request_id!r} already used with a different payload",
                details={"reason": "retrieval_session_question_mismatch"},
            )
        snap = session.snapshot
        if (
            snap.world_id != request.world_id
            or snap.campaign_id != request.campaign_id
            or snap.focus != request.focus
            or snap.admissibility != request.admissibility
        ):
            raise IdempotencyConflictError(
                f"request_id {request.request_id!r} already used with a different payload",
                details={"reason": "retrieval_session_scope_mismatch"},
            )
        if (
            request.requested_revision_id is not None
            and snap.revision_id != request.requested_revision_id
        ):
            raise IdempotencyConflictError(
                f"request_id {request.request_id!r} already used with a different payload",
                details={"reason": "retrieval_session_revision_mismatch"},
            )

    def _response_from_session(
        self,
        request: MindTurnRequest,
        session: GraphRetrievalSession,
    ) -> MindTurnResponse:
        """Reconstruct a deterministic response from an existing retrieval session.

        Replays the same seed → one-hop → projection path against the pinned
        revision using persisted preflight candidates and referents, without
        re-invoking the agent.
        """
        self._assert_session_matches_request(request, session)

        objects: list[GraphObjectView] = []
        relationships: list[GraphRelationshipView] = []
        seed_ids: list[str] = sorted(
            {r.object_id for r in session.referents if r.object_id}
        )
        stored = self._world_graph.get_revision(
            request.world_id, session.snapshot.revision_id
        )
        if stored is None:
            raise RevisionNotFoundError(
                f"revision {session.snapshot.revision_id!r} not found for world "
                f"{request.world_id!r} during session recovery"
            )
        parsed = self._graph_reader.parse(
            graph_schema=stored.revision.graph_schema,
            graph_payload=stored.graph_payload,
        )
        scoped = project_scoped_snapshot(
            parsed,
            sources=self._sources,
            world_id=request.world_id,
            campaign_id=request.campaign_id,
            admissibility=request.admissibility,
        )
        parsed = scoped.snapshot
        candidate_object_ids: list[str] = []
        for doc_id in session.preflight_candidate_ids:
            doc = self._semantic_documents.get(doc_id)
            if doc is None or not doc.graph_object_id:
                continue
            if self._graph_reader.get_object(parsed, doc.graph_object_id) is None:
                continue
            candidate_object_ids.append(doc.graph_object_id)
        seed_ids = sorted(
            {
                *(r.object_id for r in session.referents if r.object_id),
                *candidate_object_ids,
            }
        )
        focus_ids = collect_one_hop_object_ids(parsed, seed_ids)
        for object_id in focus_ids:
            obj = self._graph_reader.get_object(parsed, object_id)
            if obj is not None:
                objects.append(obj)
        relationships = self._graph_reader.list_relationships(parsed, seed_ids)

        projections = self._build_projections(
            request_id=request.request_id,
            objects=objects,
            relationships=relationships,
            evidence=session.evidence,
            seed_ids=seed_ids,
        )
        if not projections and session.evidence:
            projections = [
                SemanticProjection(
                    projection_id=_stable_id("proj", request.request_id, "evidence"),
                    kind="evidence_summary",
                    payload={
                        "evidence_ref_ids": [e.evidence_ref_id for e in session.evidence],
                    },
                )
            ]
        actions = [
            SuggestedAction(
                action_id=_stable_id("act", request.request_id, anchor.anchor_id),
                kind="open_source",
                label=f"Open {anchor.display_label or anchor.source_artifact_id}",
                arguments={"source_anchor_id": anchor.anchor_id},
            )
            for anchor in session.source_anchors
            if anchor.readable
        ]
        answer = "I do not have grounded knowledge for that question in the admitted graph context."
        for entry in session.diagnostics:
            if entry.code == "persisted_turn_answer" and isinstance(
                entry.data.get("answer"), str
            ):
                answer = str(entry.data["answer"])
                break
        else:
            for claim in session.claims:
                if claim.status.value == "accepted":
                    answer = claim.text
                    break
        context_changes = [
            ContextChange(
                change_id=_stable_id("ctx", request.request_id, "thread"),
                kind="thread_continued",
                payload={"thread_id": request.thread_id},
            )
        ]
        if seed_ids:
            context_changes.append(
                ContextChange(
                    change_id=_stable_id("ctx", request.request_id, "selection"),
                    kind="selection_resolved",
                    payload={"object_ids": seed_ids},
                )
            )
        return MindTurnResponse(
            request_id=request.request_id,
            turn_id=_stable_id("turn", request.request_id),
            thread_id=request.thread_id,
            world_id=request.world_id,
            campaign_id=request.campaign_id,
            revision_id=session.snapshot.revision_id,
            answer=answer,
            resolved_referents=session.referents,
            claims=session.claims,
            evidence=session.evidence,
            source_anchors=session.source_anchors,
            source_reads=session.source_reads,
            semantic_projections=projections,
            suggested_actions=actions,
            context_changes=context_changes,
            coverage=session.coverage,
            diagnostics=session.diagnostics,
        )

    def _resolve_revision(
        self, request: MindTurnRequest
    ) -> tuple[str, str, StoredGraphRevision]:
        head = self._world_graph.get_head(request.world_id)
        if head is None:
            raise HeadNotFoundError(f"no graph head for world {request.world_id!r}")
        head_revision_id = head.head_revision_id
        revision_id = request.requested_revision_id or head_revision_id
        stored = self._world_graph.get_revision(request.world_id, revision_id)
        if stored is None:
            raise RevisionNotFoundError(
                f"revision {revision_id!r} not found for world {request.world_id!r}"
            )
        if stored.revision.world_id != request.world_id:
            raise ScopeResolutionError(
                f"revision {revision_id!r} belongs to world "
                f"{stored.revision.world_id!r}, not {request.world_id!r}"
            )
        return revision_id, head_revision_id, stored

    def _admit_evidence(
        self,
        *,
        request: MindTurnRequest,
        revision_id: str,
        parsed: ParsedGraphSnapshot,
        objects: list[GraphObjectView],
        relationships: list[GraphRelationshipView],
        coverage: Coverage,
    ) -> tuple[list[EvidenceRef], list[SourceAnchor]]:
        evidence: list[EvidenceRef] = []
        anchors: list[SourceAnchor] = []
        seen_evidence: set[str] = set()
        seen_anchors: set[str] = set()

        def _admit(
            evidence_ref_id: str,
            supporting_object_ids: list[str],
            owner_id: str,
        ) -> None:
            resolved = resolve_evidence_provenance(
                evidence_ref_id,
                snapshot=parsed,
                sources=self._sources,
                world_id=request.world_id,
                campaign_id=request.campaign_id,
                admissibility=request.admissibility,
            )
            if resolved is None:
                # Out-of-scope: silent (should not occur on retained objects).
                return
            if resolved is EvidenceScopeVerdict.SCOPE_UNKNOWN:
                # Scope unestablishable — never echo hidden source identities.
                coverage.gap_codes.append(STORED_PROVENANCE_INVALID)
                return
            if isinstance(resolved, ProvenanceRejection):
                coverage.gap_codes.append(resolved.gap_code)
                coverage.missing.append(resolved.missing_id)
                return
            assert isinstance(resolved, ValidatedProvenance)
            record = resolved.record
            if evidence_ref_id not in seen_evidence:
                seen_evidence.add(evidence_ref_id)
                evidence.append(resolved.evidence)
            anchor_id = _stable_id(
                "anchor",
                request.request_id,
                revision_id,
                evidence_ref_id,
                owner_id,
            )
            if anchor_id in seen_anchors:
                return
            seen_anchors.add(anchor_id)
            anchors.append(
                SourceAnchor(
                    anchor_id=anchor_id,
                    revision_id=revision_id,
                    evidence_ref_id=evidence_ref_id,
                    source_artifact_id=record.source_artifact_id,
                    source_domain=record.source_domain,
                    supporting_object_ids=sorted(set(supporting_object_ids)),
                    readable=record.can_open_source,
                    locator_kind="external_fixture",
                    display_label=record.locator or record.source_artifact_id,
                )
            )

        for obj in objects:
            if not obj.evidence_ref_ids:
                coverage.gap_codes.append("missing_support_evidence")
                coverage.missing.append(obj.object_id)
            for evidence_ref_id in obj.evidence_ref_ids:
                _admit(evidence_ref_id, [obj.object_id], obj.object_id)

        for rel in relationships:
            if not rel.evidence_ref_ids:
                coverage.gap_codes.append("missing_support_evidence")
                coverage.missing.append(rel.relationship_id)
            for evidence_ref_id in rel.evidence_ref_ids:
                _admit(
                    evidence_ref_id,
                    [rel.subject_object_id, rel.object_object_id],
                    rel.relationship_id,
                )

        evidence.sort(key=lambda item: item.evidence_ref_id)
        anchors.sort(key=lambda item: item.anchor_id)
        # Deduplicate gap codes while preserving order.
        coverage.gap_codes = list(dict.fromkeys(coverage.gap_codes))
        coverage.missing = list(dict.fromkeys(coverage.missing))
        return evidence, anchors

    def _build_projections(
        self,
        *,
        request_id: str,
        objects: list[GraphObjectView],
        relationships: list[GraphRelationshipView],
        evidence: list[EvidenceRef],
        seed_ids: list[str],
    ) -> list[SemanticProjection]:
        projections: list[SemanticProjection] = []
        for obj in objects:
            projections.append(
                SemanticProjection(
                    projection_id=_stable_id("proj", request_id, "entity", obj.object_id),
                    kind="entity_brief",
                    payload={
                        "object_id": obj.object_id,
                        "label": obj.label,
                        "kind": obj.kind,
                        "aliases": list(obj.aliases),
                        **({"summary": obj.summary} if obj.summary else {}),
                    },
                )
            )
            if (
                obj.object_field_schema == "v2"
                and (
                    obj.admitted_alias_assertions
                    or obj.admitted_summary_assertion is not None
                )
            ):
                provenance_payload: dict[str, Any] = {
                    "object_id": obj.object_id,
                    "alias_assertions": [
                        {
                            "assertion_id": assertion.assertion_id,
                            "alias": assertion.alias,
                            "evidence_ref_ids": list(assertion.evidence_ref_ids),
                        }
                        for assertion in obj.admitted_alias_assertions
                    ],
                }
                if obj.admitted_summary_assertion is not None:
                    summary = obj.admitted_summary_assertion
                    provenance_payload["summary_assertion"] = {
                        "assertion_id": summary.assertion_id,
                        "summary": summary.summary,
                        "evidence_ref_ids": list(summary.evidence_ref_ids),
                    }
                projections.append(
                    SemanticProjection(
                        projection_id=_stable_id(
                            "proj",
                            request_id,
                            "entity_field_provenance",
                            obj.object_id,
                        ),
                        kind="entity_field_provenance",
                        payload=provenance_payload,
                    )
                )
        if relationships:
            projections.append(
                SemanticProjection(
                    projection_id=_stable_id("proj", request_id, "relationships"),
                    kind="relationship_list",
                    payload={
                        "focus_object_ids": seed_ids,
                        "relationships": [
                            {
                                "relationship_id": rel.relationship_id,
                                "subject_object_id": rel.subject_object_id,
                                "predicate": rel.predicate,
                                "object_object_id": rel.object_object_id,
                            }
                            for rel in relationships
                        ],
                    },
                )
            )
        if evidence:
            projections.append(
                SemanticProjection(
                    projection_id=_stable_id("proj", request_id, "evidence"),
                    kind="evidence_summary",
                    payload={
                        "evidence_ref_ids": [item.evidence_ref_id for item in evidence],
                    },
                )
            )
        return projections


class PersistenceWorldMismatch(ScopeResolutionError):
    def __init__(self, graph_world_id: str, request_world_id: str) -> None:
        super().__init__(
            f"graph payload world_id {graph_world_id!r} disagrees with "
            f"request world_id {request_world_id!r}",
            details={
                "graph_world_id": graph_world_id,
                "request_world_id": request_world_id,
            },
        )
