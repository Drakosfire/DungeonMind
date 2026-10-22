"""Current typed genesis, immutable history and exact replay boundaries."""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from dungeonmind.application.graph_snapshot import GRAPH_SCHEMA_V5, GRAPH_SCHEMA_V6
from dungeonmind.application.reviewed_world_initialization import (
    initialize_reviewed_world,
    materialize_reviewed_world_initialization_v6,
)
from dungeonmind.application.world_graph_projection import WorldGraphProjectionService
from dungeonmind.contracts.evidence import SourceDomain
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.projection_v2 import ScopeModeV2, WorldGraphProjectionRequestV2
from dungeonmind.contracts.reviewed_world_initialization import (
    ReviewedWorldInitializationReceiptV1,
)
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import (
    IdempotencyConflictError,
    PersistenceIntegrityError,
)
from tests.unit.test_reviewed_world_initialization import make_stores
from tests.unit.test_reviewed_world_initialization_materialization_v6 import (
    CAMPAIGN_ID,
    NOW,
    WORLD_ID,
    graph_reader,
    make_command,
    make_first_world_family_command,
)

LATER = NOW + timedelta(seconds=1)
FOREIGN_WORLD = "world:foreign-genesis-payload"


class _FixedClock:
    def now(self):
        return datetime(2026, 8, 26, 20, 0, tzinfo=UTC)


def _initialize(inits, command):
    return initialize_reviewed_world(
        command,
        initialization_repository=inits,
        graph_reader=graph_reader(),
    )


def _project(graph, sources, inits, *, revision_pin=None, admissibility=Admissibility.GM):
    return WorldGraphProjectionService(
        world_graph=graph,
        sources=sources,
        graph_reader=graph_reader(),
        reviewed_world_initializations=inits,
        clock=_FixedClock(),
    ).project(
        WorldGraphProjectionRequestV2(
            world_id=WORLD_ID,
            campaign_id=CAMPAIGN_ID,
            admissibility=admissibility,
            revision_pin=revision_pin,
            scope_mode=ScopeModeV2.CAMPAIGN,
        )
    )


def _admitted_object_ids(result) -> set[str]:
    return set(result.scoped_graph.snapshot.objects)


def _publish_identical_child(graph, receipt):
    stored = graph.get_revision(WORLD_ID, receipt.published_revision_id)
    assert stored is not None
    return graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=receipt.published_revision_id,
            expected_parent_revision_id=receipt.published_revision_id,
            operation_ids=["op:genesis-integrity-child"],
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload=copy.deepcopy(stored.graph_payload),
            created_at=LATER,
        )
    )


class _RawReceiptRepository:
    """Return a stored receipt without adapter reconstruction so projection owns D0 checks."""

    def __init__(self, receipt: ReviewedWorldInitializationReceiptV1) -> None:
        self._receipt = receipt

    def get_for_world(self, world_id: str) -> ReviewedWorldInitializationReceiptV1 | None:
        if world_id != self._receipt.world_id:
            return None
        return self._receipt

    def get(
        self, world_id: str, initialization_id: str
    ) -> ReviewedWorldInitializationReceiptV1 | None:
        if (
            world_id != self._receipt.world_id
            or initialization_id != self._receipt.initialization_id
        ):
            return None
        return self._receipt

    def initialize(self, *args: Any, **kwargs: Any) -> ReviewedWorldInitializationReceiptV1:
        raise AssertionError("initialize is not used by genesis integrity projection tests")


def _d0_key(receipt) -> tuple[str, str]:
    return (WORLD_ID, receipt.published_revision_id)


def _replace_d0(graph, receipt, stored) -> None:
    graph._revisions[_d0_key(receipt)] = stored


def test_typed_evidence_survives_materialization_and_exact_replay() -> None:
    graph, sources, contributions, _identity, inits, _adoptions = make_stores()
    command = make_command()
    receipt = _initialize(inits, command)
    assert receipt.schema_version == "dm_reviewed_world_initialization_receipt_v2"
    assert _initialize(inits, command) == receipt
    expected = {
        ref.evidence_ref_id: ref.model_dump(mode="json")
        for assertion in command.reviewed_contribution.assertions
        for ref in assertion.evidence_refs
    }
    stored = graph.get_revision(WORLD_ID, receipt.published_revision_id)
    assert {
        row["evidence_ref_id"]: row for row in stored.graph_payload["evidence_refs"]
    } == expected
    assert all(row["source_span_ref_id"] for row in stored.graph_payload["evidence_refs"])
    assert _admitted_object_ids(_project(graph, sources, inits)) == {
        "obj:college",
        "obj:headmaster",
    }
    assert (
        contributions.get(WORLD_ID, command.reviewed_contribution.contribution_id)
        == command.reviewed_contribution
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_span_ref_id", None),
        ("can_open_source", False),
        ("can_highlight_span", False),
        ("source_artifact_id", "foreign"),
        ("source_revision_id", "foreign"),
        ("source_domain_key", "other"),
        ("source_domain", SourceDomain.OTHER),
        ("session_id", "session:foreign"),
    ],
)
def test_invalid_worldbuilding_pointer_rejected_before_repository_read(field, value) -> None:
    from tests.unit.test_reviewed_world_initialization import _assert_zero_mutation

    graph, sources, contributions, _identity, inits, _adoptions = make_stores()
    command = make_command()
    payload = command.model_dump(mode="json")
    payload["reviewed_contribution"]["assertions"][0]["evidence_refs"][0][field] = value
    assertion = command.reviewed_contribution.assertions[0]
    ref = assertion.evidence_refs[0].model_copy(update={field: value})
    invalid = command.model_copy(
        update={
            "reviewed_contribution": command.reviewed_contribution.model_copy(
                update={
                    "assertions": [
                        assertion.model_copy(update={"evidence_refs": [ref]}),
                        *command.reviewed_contribution.assertions[1:],
                    ]
                }
            )
        }
    )
    with pytest.raises(PersistenceIntegrityError):
        _initialize(inits, invalid)
    _assert_zero_mutation(graph, sources, contributions, inits)


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_span_ref_id", "span:changed"),
        ("evidence_role", "context"),
    ],
)
def test_changed_typed_binding_cannot_replay_existing_identity(field, value) -> None:
    graph, _sources, _contributions, _identity, inits, _adoptions = make_stores()
    command = make_command()
    receipt = _initialize(inits, command)
    payload = command.model_dump(mode="json")
    payload["reviewed_contribution"]["assertions"][0]["evidence_refs"][0][field] = value
    changed = type(command).model_validate(payload)
    with pytest.raises(IdempotencyConflictError):
        _initialize(inits, changed)
    assert inits.get_for_world(WORLD_ID) == receipt
    assert graph.get_head(WORLD_ID).head_revision_id == receipt.published_revision_id


def test_historical_receipt_is_read_only_and_cannot_satisfy_current_replay() -> None:
    from dungeonmind.application.reviewed_world_initialization import (
        is_first_world_producer_family_receipt,
    )

    _graph, _sources, _contributions, _identity, inits, _adoptions = make_stores()
    command = make_first_world_family_command(evidence_domain=SourceDomain.WORLDBUILDING)
    receipt = _initialize(inits, command)
    assert not is_first_world_producer_family_receipt(receipt)
    history = ReviewedWorldInitializationReceiptV1.model_validate(
        {
            **receipt.model_dump(mode="json"),
            "schema_version": "dm_reviewed_world_initialization_receipt_v1",
        }
    )
    original = history.model_dump_json()
    inits._receipts_by_world[WORLD_ID] = history
    inits._receipts_by_initialization[history.initialization_id] = history
    assert inits.get_for_world(WORLD_ID).model_dump_json() == original
    with pytest.raises(IdempotencyConflictError):
        _initialize(inits, command)
    assert inits.get_for_world(WORLD_ID).model_dump_json() == original


def test_old_command_schema_rejected_without_repository_access() -> None:
    from types import SimpleNamespace

    class NoIO:
        def get_for_world(self, *_args):
            raise AssertionError("old command must not read storage")

    with pytest.raises(PersistenceIntegrityError) as exc:
        _initialize(
            NoIO(), SimpleNamespace(schema_version="dm_reviewed_world_initialization_command_v1")
        )
    assert exc.value.details["reason"] == "unsupported_initialization_command_schema"


def test_raw_repository_rejects_a_payload_that_drops_or_changes_reviewed_spans() -> None:
    from tests.unit.test_reviewed_world_initialization import _assert_zero_mutation

    graph, sources, contributions, _identity, inits, _adoptions = make_stores()
    command = make_command()
    materialization = materialize_reviewed_world_initialization_v6(
        command, graph_reader=graph_reader()
    )
    payload = materialization.graph_payload
    payload["evidence_refs"][0]["source_span_ref_id"] = "span:forged"
    with pytest.raises(PersistenceIntegrityError):
        inits.initialize(
            command,
            graph_payload=payload,
            graph_payload_sha256=canonical_sha256(payload),
            accepted_assertion_ids=materialization.accepted_assertion_ids,
        )
    _assert_zero_mutation(graph, sources, contributions, inits)


def test_receipt_d0_missing_revision_is_integrity_error() -> None:
    graph, sources, _contributions, _identity, inits, _adoptions = make_stores()
    receipt = _initialize(
        inits, make_first_world_family_command(evidence_domain=SourceDomain.WORLDBUILDING)
    )
    child = _publish_identical_child(graph, receipt)
    del graph._revisions[_d0_key(receipt)]
    with pytest.raises(PersistenceIntegrityError):
        _project(
            graph,
            sources,
            _RawReceiptRepository(receipt),
            revision_pin=child.revision_id,
        )


def test_receipt_d0_revision_identity_mismatch_is_integrity_error() -> None:
    graph, sources, _contributions, _identity, inits, _adoptions = make_stores()
    receipt = _initialize(
        inits, make_first_world_family_command(evidence_domain=SourceDomain.WORLDBUILDING)
    )
    child = _publish_identical_child(graph, receipt)
    stored = graph._revisions[_d0_key(receipt)]
    _replace_d0(
        graph,
        receipt,
        stored.model_copy(
            update={
                "revision": stored.revision.model_copy(
                    update={"revision_id": "rev:imposter-genesis"}
                )
            }
        ),
    )
    with pytest.raises(PersistenceIntegrityError):
        _project(
            graph,
            sources,
            _RawReceiptRepository(receipt),
            revision_pin=child.revision_id,
        )


def test_receipt_d0_envelope_world_mismatch_is_integrity_error() -> None:
    graph, sources, _contributions, _identity, inits, _adoptions = make_stores()
    receipt = _initialize(
        inits, make_first_world_family_command(evidence_domain=SourceDomain.WORLDBUILDING)
    )
    child = _publish_identical_child(graph, receipt)
    stored = graph._revisions[_d0_key(receipt)]
    _replace_d0(
        graph,
        receipt,
        stored.model_copy(
            update={"revision": stored.revision.model_copy(update={"world_id": FOREIGN_WORLD})}
        ),
    )
    with pytest.raises(PersistenceIntegrityError):
        _project(
            graph,
            sources,
            _RawReceiptRepository(receipt),
            revision_pin=child.revision_id,
        )


def test_receipt_d0_payload_world_mismatch_is_integrity_error() -> None:
    graph, sources, _contributions, _identity, inits, _adoptions = make_stores()
    receipt = _initialize(
        inits, make_first_world_family_command(evidence_domain=SourceDomain.WORLDBUILDING)
    )
    child = _publish_identical_child(graph, receipt)
    stored = graph._revisions[_d0_key(receipt)]
    payload = copy.deepcopy(stored.graph_payload)
    payload["world_id"] = FOREIGN_WORLD
    new_sha = canonical_sha256(payload)
    _replace_d0(
        graph,
        receipt,
        stored.model_copy(
            update={
                "graph_payload": payload,
                "revision": stored.revision.model_copy(update={"graph_payload_sha256": new_sha}),
            }
        ),
    )
    drifted = receipt.model_copy(update={"published_graph_payload_sha256": new_sha})
    with pytest.raises(PersistenceIntegrityError):
        _project(
            graph,
            sources,
            _RawReceiptRepository(drifted),
            revision_pin=child.revision_id,
        )


def test_receipt_d0_graph_schema_mismatch_is_integrity_error() -> None:
    graph, sources, _contributions, _identity, inits, _adoptions = make_stores()
    receipt = _initialize(
        inits, make_first_world_family_command(evidence_domain=SourceDomain.WORLDBUILDING)
    )
    child = _publish_identical_child(graph, receipt)
    stored = graph._revisions[_d0_key(receipt)]
    _replace_d0(
        graph,
        receipt,
        stored.model_copy(
            update={
                "revision": stored.revision.model_copy(update={"graph_schema": GRAPH_SCHEMA_V5})
            }
        ),
    )
    with pytest.raises(PersistenceIntegrityError):
        _project(
            graph,
            sources,
            _RawReceiptRepository(receipt),
            revision_pin=child.revision_id,
        )


def test_receipt_d0_payload_sha_mismatch_is_integrity_error() -> None:
    graph, sources, _contributions, _identity, inits, _adoptions = make_stores()
    receipt = _initialize(
        inits, make_first_world_family_command(evidence_domain=SourceDomain.WORLDBUILDING)
    )
    child = _publish_identical_child(graph, receipt)
    stored = graph._revisions[_d0_key(receipt)]
    payload = copy.deepcopy(stored.graph_payload)
    payload["objects"][0]["label"] = "mutated-without-hash-update"
    _replace_d0(graph, receipt, stored.model_copy(update={"graph_payload": payload}))
    with pytest.raises(PersistenceIntegrityError):
        _project(
            graph,
            sources,
            _RawReceiptRepository(receipt),
            revision_pin=child.revision_id,
        )


@pytest.mark.parametrize("conflicting", [False, True])
def test_duplicate_or_conflicting_evidence_ids_are_rejected(conflicting):
    command = make_command()
    payload = command.model_dump(mode="json")
    rows = payload["reviewed_contribution"]["assertions"]
    original = rows[0]["evidence_refs"][0]
    if conflicting:
        rows[1]["evidence_refs"] = [{**original, "source_span_ref_id": "span:conflict"}]
    else:
        rows[0]["evidence_refs"].append(dict(original))
    invalid = type(command).model_validate(payload)
    _graph, _sources, _contributions, _identity, inits, _adoptions = make_stores()
    with pytest.raises(PersistenceIntegrityError):
        _initialize(inits, invalid)
    assert inits.get_for_world(WORLD_ID) is None


@pytest.mark.parametrize("target", ["node", "alias", "edge", "endpoint"])
def test_raw_repository_cannot_rebind_a_reviewed_passage(target):
    graph, sources, contributions, _identity, inits, _adoptions = make_stores()
    command = make_command()
    materialized = materialize_reviewed_world_initialization_v6(
        command, graph_reader=graph_reader()
    )
    payload = materialized.graph_payload
    if target == "node":
        payload["objects"][0]["assertion_metadata"]["evidence_ref_ids"] = ["ev:asrt:headmaster"]
    elif target == "alias":
        payload["objects"][0]["aliases"][0]["assertion_metadata"]["evidence_ref_ids"] = [
            "ev:asrt:headmaster"
        ]
    elif target == "edge":
        payload["relationships"][0]["assertion_metadata"]["evidence_ref_ids"] = [
            "ev:asrt:headmaster"
        ]
    else:
        payload["relationships"][0]["source_object_id"] = "obj:college"
    with pytest.raises(PersistenceIntegrityError):
        inits.initialize(
            command,
            graph_payload=payload,
            graph_payload_sha256=canonical_sha256(payload),
            accepted_assertion_ids=materialized.accepted_assertion_ids,
        )
    assert graph.get_head(WORLD_ID) is None
    assert not sources._artifacts and not contributions._items


def test_raw_repository_freezes_caller_payload_before_source_writes():
    command = make_command()
    materialized = materialize_reviewed_world_initialization_v6(
        command, graph_reader=graph_reader()
    )
    payload = materialized.graph_payload
    expected = copy.deepcopy(payload)
    accepted = list(materialized.accepted_assertion_ids)

    def mutate_caller(stage):
        if stage == "source_records":
            payload["objects"][0]["assertion_metadata"]["evidence_ref_ids"] = ["ev:asrt:headmaster"]
            accepted.clear()

    graph, _sources, _contributions, _identity, inits, _adoptions = make_stores(
        failure_hook=mutate_caller
    )
    receipt = inits.initialize(
        command,
        graph_payload=payload,
        graph_payload_sha256=canonical_sha256(expected),
        accepted_assertion_ids=accepted,
    )
    assert payload != expected and not accepted
    assert graph.get_revision(WORLD_ID, receipt.published_revision_id).graph_payload == expected
    assert tuple(receipt.accepted_assertion_ids) == materialized.accepted_assertion_ids
