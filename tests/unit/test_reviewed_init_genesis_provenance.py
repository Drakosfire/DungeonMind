"""#645-family genesis provenance compatibility and dual replay identity."""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from dungeonmind.application.graph_snapshot import GRAPH_SCHEMA_V5, GRAPH_SCHEMA_V6
from dungeonmind.application.reviewed_world_initialization import (
    initialize_reviewed_world,
    materialize_reviewed_world_initialization_v6,
    reviewed_world_initialization_command_sha256,
    reviewed_world_initialization_replay_identity,
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
    PersistenceUnavailableError,
)
from tests.unit.test_reviewed_world_initialization import make_stores
from tests.unit.test_reviewed_world_initialization_materialization_v6 import (
    CAMPAIGN_ID,
    FAMILY_EVIDENCE_ID,
    FIRST_WORLD_INIT_ID,
    NOW,
    WORLD_ID,
    graph_reader,
    make_command,
    make_first_world_family_command,
    make_non_family_other_evidence_command,
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


def _adapter_initialize(inits, command):
    materialization = materialize_reviewed_world_initialization_v6(
        command, graph_reader=graph_reader()
    )
    return inits.initialize(
        command,
        graph_payload=materialization.graph_payload,
        graph_payload_sha256=materialization.graph_payload_sha256,
        accepted_assertion_ids=materialization.accepted_assertion_ids,
    )


def test_corrected_family_command_has_historical_other_digest() -> None:
    historical = make_first_world_family_command(evidence_domain=SourceDomain.OTHER)
    corrected = make_first_world_family_command(
        evidence_domain=SourceDomain.WORLDBUILDING
    )
    hist_identity = reviewed_world_initialization_replay_identity(historical)
    corr_identity = reviewed_world_initialization_replay_identity(corrected)
    assert hist_identity.historical_other_normalized_sha256 is None
    assert corr_identity.historical_other_normalized_sha256 == hist_identity.current_command_sha256
    assert corr_identity.current_command_sha256 != hist_identity.current_command_sha256
    assert corr_identity.current_command_sha256 == reviewed_world_initialization_command_sha256(
        corrected
    )


def test_non_family_command_has_no_historical_digest() -> None:
    other = make_non_family_other_evidence_command()
    corrected = make_non_family_other_evidence_command()
    assertions = [
        item.model_copy(
            update={
                "evidence_refs": [
                    ref.model_copy(update={"source_domain": SourceDomain.WORLDBUILDING})
                    for ref in item.evidence_refs
                ]
            }
        )
        for item in corrected.reviewed_contribution.assertions
    ]
    corrected = corrected.model_copy(
        update={
            "reviewed_contribution": corrected.reviewed_contribution.model_copy(
                update={"assertions": assertions}
            )
        }
    )
    identity = reviewed_world_initialization_replay_identity(corrected)
    assert identity.historical_other_normalized_sha256 is None
    assert identity.current_command_sha256 != reviewed_world_initialization_command_sha256(
        other
    )


def test_family_other_exact_replay_and_corrected_retry_return_stored_receipt() -> None:
    graph, _sources, _contributions, _identity, inits, _adoptions = make_stores()
    historical = make_first_world_family_command(evidence_domain=SourceDomain.OTHER)
    first = _initialize(inits, historical)
    assert first.initialization_id == FIRST_WORLD_INIT_ID
    stored_hash = first.command_sha256
    replayed = _initialize(inits, historical)
    assert replayed == first
    corrected = make_first_world_family_command(
        evidence_domain=SourceDomain.WORLDBUILDING
    )
    recovered = _initialize(inits, corrected)
    assert recovered == first
    assert inits.get_for_world(WORLD_ID).command_sha256 == stored_hash
    assert len(graph._revisions) == 1


def test_family_any_other_delta_still_conflicts() -> None:
    _graph, _sources, _contributions, _identity, inits, _adoptions = make_stores()
    stored = _initialize(
        inits, make_first_world_family_command(evidence_domain=SourceDomain.OTHER)
    )
    conflicting = make_first_world_family_command(
        evidence_domain=SourceDomain.OTHER
    ).model_copy(update={"source_plan_id": "plan:different"})
    with pytest.raises(IdempotencyConflictError) as exc:
        _initialize(inits, conflicting)
    assert "command_sha256" in exc.value.details
    assert inits.get_for_world(WORLD_ID) == stored


def test_family_d0_other_projects_while_raw_revision_stays_other() -> None:
    graph, sources, _contributions, _identity, inits, _adoptions = make_stores()
    receipt = _initialize(
        inits, make_first_world_family_command(evidence_domain=SourceDomain.OTHER)
    )
    stored = graph.get_revision(WORLD_ID, receipt.published_revision_id)
    assert stored is not None
    for record in stored.graph_payload["evidence_refs"]:
        assert record["source_domain"] == "other"
        assert record["source_domain_key"] == "other"
    result = _project(graph, sources, inits)
    assert _admitted_object_ids(result) == {"obj:college", "obj:headmaster"}
    admitted = result.scoped_graph.snapshot.evidence[FAMILY_EVIDENCE_ID]
    assert admitted.source_domain is SourceDomain.OTHER
    assert admitted.source_domain_key == "other"


def test_non_family_other_evidence_still_rejects_projection() -> None:
    graph, sources, _contributions, _identity, inits, _adoptions = make_stores()
    _initialize(inits, make_non_family_other_evidence_command())
    result = _project(graph, sources, inits)
    assert _admitted_object_ids(result) == set()
    assert result.scoped_graph.object_exclusions


def test_family_non_worldbuilding_artifact_still_rejects_projection() -> None:
    graph, sources, _contributions, _identity, inits, _adoptions = make_stores()
    _initialize(
        inits,
        make_first_world_family_command(
            evidence_domain=SourceDomain.OTHER,
            artifact_domain=SourceDomain.RULEBOOK,
            artifact_key="rulebook",
        ),
    )
    result = _project(graph, sources, inits)
    assert _admitted_object_ids(result) == set()


def test_family_session_recap_evidence_still_rejects_projection() -> None:
    graph, sources, _contributions, _identity, inits, _adoptions = make_stores()
    _initialize(
        inits,
        make_first_world_family_command(evidence_domain=SourceDomain.SESSION_RECAP),
    )
    result = _project(graph, sources, inits)
    assert _admitted_object_ids(result) == set()


def test_identical_descendant_keeps_compatibility() -> None:
    graph, sources, _contributions, _identity, inits, _adoptions = make_stores()
    receipt = _initialize(
        inits, make_first_world_family_command(evidence_domain=SourceDomain.OTHER)
    )
    stored = graph.get_revision(WORLD_ID, receipt.published_revision_id)
    assert stored is not None
    child = graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=receipt.published_revision_id,
            expected_parent_revision_id=receipt.published_revision_id,
            operation_ids=["op:identical-descendant"],
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload=copy.deepcopy(stored.graph_payload),
            created_at=LATER,
        )
    )
    result = _project(graph, sources, inits, revision_pin=child.revision_id)
    assert _admitted_object_ids(result) == {"obj:college", "obj:headmaster"}


def test_same_id_changed_descendant_record_rejects() -> None:
    graph, sources, _contributions, _identity, inits, _adoptions = make_stores()
    receipt = _initialize(
        inits, make_first_world_family_command(evidence_domain=SourceDomain.OTHER)
    )
    stored = graph.get_revision(WORLD_ID, receipt.published_revision_id)
    assert stored is not None
    payload = copy.deepcopy(stored.graph_payload)
    payload["evidence_refs"][0]["locator"] = "mutated://locator"
    child = graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=receipt.published_revision_id,
            expected_parent_revision_id=receipt.published_revision_id,
            operation_ids=["op:changed-descendant"],
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload=payload,
            created_at=LATER,
        )
    )
    result = _project(graph, sources, inits, revision_pin=child.revision_id)
    assert _admitted_object_ids(result) == set()


def test_new_descendant_other_id_rejects() -> None:
    graph, sources, _contributions, _identity, inits, _adoptions = make_stores()
    receipt = _initialize(
        inits, make_first_world_family_command(evidence_domain=SourceDomain.OTHER)
    )
    stored = graph.get_revision(WORLD_ID, receipt.published_revision_id)
    assert stored is not None
    payload = copy.deepcopy(stored.graph_payload)
    extra = copy.deepcopy(payload["evidence_refs"][0])
    extra["evidence_ref_id"] = "ev:descendant-other"
    payload["evidence_refs"].append(extra)
    payload["objects"][0]["assertion_metadata"]["evidence_ref_ids"].append(
        "ev:descendant-other"
    )
    child = graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=receipt.published_revision_id,
            expected_parent_revision_id=receipt.published_revision_id,
            operation_ids=["op:new-other-descendant"],
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload=payload,
            created_at=LATER,
        )
    )
    result = _project(graph, sources, inits, revision_pin=child.revision_id)
    assert "obj:college" not in _admitted_object_ids(result)


def test_receipt_d0_non_null_parent_is_integrity_error() -> None:
    graph, sources, _contributions, _identity, inits, _adoptions = make_stores()
    receipt = _initialize(
        inits, make_first_world_family_command(evidence_domain=SourceDomain.OTHER)
    )
    key = (WORLD_ID, receipt.published_revision_id)
    stored = graph._revisions[key]
    graph._revisions[key] = stored.model_copy(
        update={
            "revision": stored.revision.model_copy(
                update={"parent_revision_id": "rev:not-genesis"}
            )
        }
    )
    with pytest.raises(PersistenceIntegrityError):
        _project(graph, sources, inits)


def test_player_admissibility_stays_fail_closed() -> None:
    graph, sources, _contributions, _identity, inits, _adoptions = make_stores()
    _initialize(
        inits, make_first_world_family_command(evidence_domain=SourceDomain.OTHER)
    )
    result = _project(graph, sources, inits, admissibility=Admissibility.PLAYER)
    assert _admitted_object_ids(result) == set()


def test_ordinary_exact_replay_unchanged_for_non_family() -> None:
    _graph, _sources, _contributions, _identity, inits, _adoptions = make_stores()
    first = _initialize(inits, make_command())
    replayed = _initialize(inits, make_command())
    assert replayed == first
    with pytest.raises(IdempotencyConflictError):
        _initialize(inits, make_command(actor="gm:other-reviewer"))


def test_family_corrected_preflight_does_not_enter_initialize() -> None:
    _graph, _sources, _contributions, _identity, inner, _adoptions = make_stores()
    stored = _initialize(
        inner, make_first_world_family_command(evidence_domain=SourceDomain.OTHER)
    )

    class _CountInitialize:
        def __init__(self) -> None:
            self.initialize_calls = 0

        def get(self, world_id: str, initialization_id: str):
            return inner.get(world_id, initialization_id)

        def get_for_world(self, world_id: str):
            return inner.get_for_world(world_id)

        def initialize(self, command, **kwargs):
            self.initialize_calls += 1
            return inner.initialize(command, **kwargs)

    wrapper = _CountInitialize()
    recovered = initialize_reviewed_world(
        make_first_world_family_command(evidence_domain=SourceDomain.WORLDBUILDING),
        initialization_repository=wrapper,  # type: ignore[arg-type]
        graph_reader=graph_reader(),
    )
    assert recovered == stored
    assert wrapper.initialize_calls == 0


def test_family_corrected_lost_response_recovery_returns_stored_receipt() -> None:
    _graph, _sources, _contributions, _identity, inner, _adoptions = make_stores()
    stored = _initialize(
        inner, make_first_world_family_command(evidence_domain=SourceDomain.OTHER)
    )

    class _HidePreflightThenUnavailable:
        def __init__(self) -> None:
            self.initialize_calls = 0
            self.recovery_probes = 0

        def get(self, world_id: str, initialization_id: str):
            return inner.get(world_id, initialization_id)

        def get_for_world(self, world_id: str):
            if self.initialize_calls == 0:
                return None
            self.recovery_probes += 1
            return inner.get_for_world(world_id)

        def initialize(self, command, **kwargs):
            self.initialize_calls += 1
            inner.initialize(command, **kwargs)
            raise PersistenceUnavailableError("response lost")

    wrapper = _HidePreflightThenUnavailable()
    recovered = initialize_reviewed_world(
        make_first_world_family_command(evidence_domain=SourceDomain.WORLDBUILDING),
        initialization_repository=wrapper,  # type: ignore[arg-type]
        graph_reader=graph_reader(),
    )
    assert recovered == stored
    assert wrapper.initialize_calls == 1
    assert wrapper.recovery_probes == 1
    assert inner.get_for_world(WORLD_ID) == stored


def test_family_corrected_in_memory_under_lock_returns_stored_receipt() -> None:
    _graph, _sources, _contributions, _identity, inits, _adoptions = make_stores()
    stored = _initialize(
        inits, make_first_world_family_command(evidence_domain=SourceDomain.OTHER)
    )
    replayed = _adapter_initialize(
        inits,
        make_first_world_family_command(evidence_domain=SourceDomain.WORLDBUILDING),
    )
    assert replayed == stored
    assert inits.get_for_world(WORLD_ID) == stored


def test_family_corrected_in_memory_under_lock_via_hidden_preflight() -> None:
    _graph, _sources, _contributions, _identity, inner, _adoptions = make_stores()
    stored = _initialize(
        inner, make_first_world_family_command(evidence_domain=SourceDomain.OTHER)
    )

    class _HidePreflight:
        def __init__(self) -> None:
            self.initialize_calls = 0

        def get(self, world_id: str, initialization_id: str):
            return inner.get(world_id, initialization_id)

        def get_for_world(self, world_id: str):
            if self.initialize_calls == 0:
                return None
            return inner.get_for_world(world_id)

        def initialize(self, command, **kwargs):
            self.initialize_calls += 1
            return inner.initialize(command, **kwargs)

    wrapper = _HidePreflight()
    recovered = initialize_reviewed_world(
        make_first_world_family_command(evidence_domain=SourceDomain.WORLDBUILDING),
        initialization_repository=wrapper,  # type: ignore[arg-type]
        graph_reader=graph_reader(),
    )
    assert recovered == stored
    assert wrapper.initialize_calls == 1


def test_receipt_d0_missing_revision_is_integrity_error() -> None:
    graph, sources, _contributions, _identity, inits, _adoptions = make_stores()
    receipt = _initialize(
        inits, make_first_world_family_command(evidence_domain=SourceDomain.OTHER)
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
        inits, make_first_world_family_command(evidence_domain=SourceDomain.OTHER)
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
        inits, make_first_world_family_command(evidence_domain=SourceDomain.OTHER)
    )
    child = _publish_identical_child(graph, receipt)
    stored = graph._revisions[_d0_key(receipt)]
    _replace_d0(
        graph,
        receipt,
        stored.model_copy(
            update={
                "revision": stored.revision.model_copy(update={"world_id": FOREIGN_WORLD})
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


def test_receipt_d0_payload_world_mismatch_is_integrity_error() -> None:
    graph, sources, _contributions, _identity, inits, _adoptions = make_stores()
    receipt = _initialize(
        inits, make_first_world_family_command(evidence_domain=SourceDomain.OTHER)
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
                "revision": stored.revision.model_copy(
                    update={"graph_payload_sha256": new_sha}
                ),
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
        inits, make_first_world_family_command(evidence_domain=SourceDomain.OTHER)
    )
    child = _publish_identical_child(graph, receipt)
    stored = graph._revisions[_d0_key(receipt)]
    _replace_d0(
        graph,
        receipt,
        stored.model_copy(
            update={
                "revision": stored.revision.model_copy(
                    update={"graph_schema": GRAPH_SCHEMA_V5}
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


def test_receipt_d0_payload_sha_mismatch_is_integrity_error() -> None:
    graph, sources, _contributions, _identity, inits, _adoptions = make_stores()
    receipt = _initialize(
        inits, make_first_world_family_command(evidence_domain=SourceDomain.OTHER)
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
