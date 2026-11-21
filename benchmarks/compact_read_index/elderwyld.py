"""Replay one exact Elderwyld query and its authorized citation reads.

Requires the pinned Buddy adapter on PYTHONPATH and its verified read-only
snapshot configuration. This module never starts a turn or invokes a model.
"""
import json
from itertools import groupby
from types import SimpleNamespace
from unittest.mock import patch


def prepare(capture, historical_revision=None):
    from apps.live_control_server.integrations.dungeonmind import native_corpus_source as owner
    from apps.live_control_server.services.native_graph_reads import prepare_query, read_selected
    from application_state.agent_conversation.native_plan_assertions import compact_assertion_read
    from application_state.agent_conversation.native_reads import observe_body_reads_locked
    from evals.buddy_benchmark.context_capture import validate_context_packet

    packet = validate_context_packet(*[
        json.loads((capture / f"context-{name}.json").read_text())
        for name in ("ready", "request", "stop")
    ])
    turn = packet["turn"]
    receipt = turn.graph_context_receipt
    authority = receipt.source_authority
    retained = receipt.native_query
    revision_id = historical_revision or authority.revision_id
    if getattr(retained, "authored_targets", ()):
        raise ValueError("probe requires a capture without authored targets")
    binding = SimpleNamespace(
        managed_world_id=authority.managed_world_id,
        native_world_id=authority.native_world_id,
        binding_version=authority.binding_version,
        provisioning_id=authority.provisioning_id,
    )
    principal = SimpleNamespace(role="gm")
    legacy_open = owner.open_native_text_source_access_context

    def open_revision(parser=None):
        def open_with_parser(**kwargs):
            return legacy_open(**kwargs, _parse_verified_rows=parser)

        with patch.object(owner, "open_native_text_source_access_context", open_with_parser):
            prepared = owner.prepare_native_source_context(
                managed_world_id=authority.managed_world_id, revision_id=revision_id,
                principal=principal, resolve_identity=lambda _: binding,
                repository=owner.turn_source_repository(read_only=True),
            )
        current_head = prepared.repository.get_head(authority.native_world_id) if historical_revision else None
        if historical_revision and (current_head is None or current_head.head_revision_id == revision_id):
            raise ValueError("historical witness must differ from the live head")
        if not historical_revision and prepared.authority != authority:
            raise ValueError("snapshot source authority differs from captured authority")
        return prepared

    def query(prepared):
        context, result = prepare_query(
            authority.managed_world_id, retained.question, principal,
            source_context=prepared, resolve_binding=lambda _: binding,
            scope_mode=retained.authority.scope_mode, campaign_id=retained.authority.campaign_id,
        )
        if historical_revision:
            return result, [], []
        execution = turn.graph_context_execution
        events = execution.events
        grants = {event.event_id: event for event in events}
        reads, citations = [], []
        for kind, group in groupby(events, key=lambda event: event.kind):
            if kind in {"native_plan_assertion_read_observed_v2",
                        "native_plan_statement_read_observed_v1"}:
                for original in group:
                    selected, missing = read_selected(
                        context, grants[original.authorization_event_id], principal,
                    )
                    if kind == "native_plan_assertion_read_observed_v2":
                        selected = tuple(map(compact_assertion_read, selected))
                    reads.append((original, tuple(selected), tuple(missing)))
            elif kind == "native_body_read_observed_v1":
                originals = tuple(group)
                before = execution.model_copy(update={"events": events[:originals[0].sequence]})
                entering = turn.model_copy(update={"graph_context_execution": before,
                                                   "status": "running"})
                reopened = observe_body_reads_locked(
                    entering, reads=tuple(
                        dict(event_id=o.event_id, authorization_event_id=o.authorization_event_id)
                        for o in originals
                    ),
                    read=lambda authority, member: owner.read_native_corpus_member(
                        authority=authority, member=member, principal=principal, prepared=prepared,
                    ),
                )
                citations.extend(zip(originals, reopened, strict=True))
        return result, reads, citations

    def witness(prepared, value):
        result, reads, citations = value
        if not historical_revision and (result != retained or not reads or not citations):
            raise ValueError("query parity failed or capture has no graph and citation reads")
        for original, selected, missing in reads:
            expected_missing = getattr(
                original, "unavailable_assertion_ids",
                getattr(original, "unavailable_statement_ids", ()),
            )
            if selected != tuple(original.reads) or missing != tuple(expected_missing):
                raise ValueError("ordered graph read differs from capture")
        for original, reopened in citations:
            expected_text = getattr(original.excerpt, "text", None)
            reopened_text = getattr(reopened.excerpt, "text", None)
            if expected_text != reopened_text or original.failure_code != reopened.failure_code:
                raise ValueError("citation bytes differ from capture")
        return {
            "semantic_digest": prepared.access.parsed.semantic_digest,
            "query": result.model_dump(mode="json"),
            "graph_reads": len(reads), "exact_citation_reads": len(citations),
        }

    return open_revision, query, witness
