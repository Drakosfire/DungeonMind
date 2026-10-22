"""PostgreSQL owning-boundary proofs for reviewed first-world initialization."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from dungeonmind.application.existing_world_adoption import adopt_existing_world
from dungeonmind.application.reviewed_world_initialization import (
    initialize_reviewed_world,
    materialize_reviewed_world_initialization_v6,
)
from dungeonmind.contracts.evidence import SourceDomain
from dungeonmind.contracts.existing_world_adoption import (
    existing_world_adoption_bundle_canonical_bytes,
)
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.contracts.identity import IdentityOutcome
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import (
    IdempotencyConflictError,
    PersistenceIntegrityError,
    PersistenceUnavailableError,
    ReviewedWorldInitializationOutcomeUnknownError,
)
from dungeonmind.infrastructure.postgres import (
    PostgresDatabase,
    PostgresReviewedWorldInitializationRepository,
)
from tests.unit.test_existing_world_adoption import (
    graph_reader as adoption_graph_reader,
)
from tests.unit.test_existing_world_adoption import (
    make_isolated_bundle,
)
from tests.unit.test_reviewed_world_initialization_materialization_v6 import (
    INIT_ID,
    NOW,
    REV,
    WORLD_ID,
    graph_reader,
    make_accepted_edge_identity_command,
    make_accepted_node_non_create_new_command,
    make_artifact_only_command,
    make_command,
    make_created_new_edge_command,
    make_first_world_family_command,
    make_revision_only_assertion_command,
    make_unreferenced_extra_artifact_command,
    make_unreferenced_extra_revision_command,
)

pytestmark = pytest.mark.integration

OTHER_WORLD = "world:reviewed-init-other"


def _counts(pg, world_id: str = WORLD_ID) -> dict[str, int]:
    queries = {
        "heads": (
            "SELECT COUNT(*) AS count FROM dungeonmind.world_graph_heads WHERE world_id = %s"
        ),
        "revisions": (
            "SELECT COUNT(*) AS count FROM dungeonmind.graph_revisions WHERE world_id = %s"
        ),
        "head_events": (
            "SELECT COUNT(*) AS count FROM dungeonmind.world_graph_head_events WHERE world_id = %s"
        ),
        "contributions": (
            "SELECT COUNT(*) AS count FROM dungeonmind.graph_contributions WHERE world_id = %s"
        ),
        "identity": (
            "SELECT COUNT(*) AS count FROM dungeonmind.identity_decisions WHERE world_id = %s"
        ),
        "artifacts": (
            "SELECT COUNT(*) AS count FROM dungeonmind.source_artifacts WHERE world_id = %s"
        ),
        "init_receipts": (
            "SELECT COUNT(*) AS count FROM dungeonmind.reviewed_world_initializations "
            "WHERE world_id = %s"
        ),
        "adoption_receipts": (
            "SELECT COUNT(*) AS count FROM dungeonmind.existing_world_adoptions WHERE world_id = %s"
        ),
    }
    counts: dict[str, int] = {}
    with pg.database.connect() as conn:
        for name, query in queries.items():
            row = conn.execute(query, (world_id,)).fetchone()
            counts[name] = int(row["count"])
        rev_row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM dungeonmind.source_revisions
            WHERE source_artifact_id IN (
                SELECT source_artifact_id FROM dungeonmind.source_artifacts WHERE world_id = %s
            )
            """,
            (world_id,),
        ).fetchone()
        counts["revisions_source"] = int(rev_row["count"])
    return counts


def _initialize(pg, command=None):
    return initialize_reviewed_world(
        command or make_command(),
        initialization_repository=pg.reviewed_world_initializations,
        graph_reader=graph_reader(),
    )


def _adoption_bytes(*, world_id: str = WORLD_ID, token: str = "init-pg"):
    return existing_world_adoption_bundle_canonical_bytes(
        make_isolated_bundle(
            world_id=world_id,
            adoption_id=f"adopt:reviewed-init-{token}",
            token=token,
        )
    )


def test_postgres_empty_world_initializes_d0_and_receipt(pg) -> None:
    receipt = _initialize(pg)
    assert receipt.world_id == WORLD_ID
    assert receipt.initialization_id == INIT_ID
    assert receipt.published_graph_schema == "dm_union_graph_v6"
    stored = pg.world_graph.get_revision(WORLD_ID, receipt.published_revision_id)
    assert stored is not None
    assert stored.revision.parent_revision_id is None
    head = pg.world_graph.get_head(WORLD_ID)
    assert head is not None
    assert head.head_revision_id == receipt.published_revision_id
    counts = _counts(pg)
    assert counts["heads"] == 1
    assert counts["revisions"] == 1
    assert counts["contributions"] == 1
    assert counts["artifacts"] == 1
    assert counts["revisions_source"] == 1
    assert counts["init_receipts"] == 1
    assert counts["adoption_receipts"] == 0
    assert counts["identity"] == 0
    reloaded = pg.reviewed_world_initializations.get_for_world(WORLD_ID)
    assert reloaded == receipt


def test_postgres_exact_retry_zero_new_rows(pg) -> None:
    first = _initialize(pg)
    before = _counts(pg)
    replayed = _initialize(pg)
    assert replayed == first
    assert _counts(pg) == before


def test_postgres_same_id_different_command_sha256_conflicts(pg) -> None:
    stored = _initialize(pg)
    before = _counts(pg)
    with pytest.raises(IdempotencyConflictError):
        _initialize(pg, make_command(actor="gm:other-reviewer"))
    assert pg.reviewed_world_initializations.get_for_world(WORLD_ID) == stored
    assert _counts(pg) == before


def test_postgres_different_initialization_id_conflicts(pg) -> None:
    stored = _initialize(pg)
    before = _counts(pg)
    with pytest.raises(IdempotencyConflictError):
        _initialize(pg, make_command(initialization_id="init:second"))
    assert pg.reviewed_world_initializations.get_for_world(WORLD_ID) == stored
    assert _counts(pg) == before


def test_postgres_initialization_id_reused_across_worlds_conflicts(pg) -> None:
    first = _initialize(pg)
    other = make_command(world_id=OTHER_WORLD)
    with pytest.raises(IdempotencyConflictError):
        _initialize(pg, other)
    assert pg.reviewed_world_initializations.get_for_world(WORLD_ID) == first
    assert pg.reviewed_world_initializations.get_for_world(OTHER_WORLD) is None
    assert _counts(pg, OTHER_WORLD)["init_receipts"] == 0
    assert _counts(pg, OTHER_WORLD)["revisions"] == 0


@pytest.mark.parametrize("stage", ["source_records", "contributions", "graph", "receipt"])
def test_postgres_failure_before_commit_leaves_zero_partial_rows(
    migrated_database: str,
    pg,
    stage: str,
) -> None:
    def hook(current: str) -> None:
        if current == stage:
            raise RuntimeError(f"injected {stage} abort")

    repository = PostgresReviewedWorldInitializationRepository(
        PostgresDatabase(migrated_database),
        failure_hook=hook,
    )
    with pytest.raises(ReviewedWorldInitializationOutcomeUnknownError):
        initialize_reviewed_world(
            make_command(),
            initialization_repository=repository,
            graph_reader=graph_reader(),
        )
    assert _counts(pg) == {
        "heads": 0,
        "revisions": 0,
        "head_events": 0,
        "contributions": 0,
        "identity": 0,
        "artifacts": 0,
        "init_receipts": 0,
        "adoption_receipts": 0,
        "revisions_source": 0,
    }


def test_postgres_lost_response_retry_returns_same_receipt(pg) -> None:
    inner = pg.reviewed_world_initializations

    class _CommitThenUnavailable:
        def __init__(self) -> None:
            self.initialize_calls = 0
            self.recovery_probes = 0

        def initialize(self, command, **kwargs: Any):
            self.initialize_calls += 1
            inner.initialize(command, **kwargs)
            raise PersistenceUnavailableError("response lost")

        def get(self, world_id: str, initialization_id: str):
            return inner.get(world_id, initialization_id)

        def get_for_world(self, world_id: str):
            receipt = inner.get_for_world(world_id)
            if self.initialize_calls:
                self.recovery_probes += 1
            return receipt

    wrapper = _CommitThenUnavailable()
    receipt = initialize_reviewed_world(
        make_command(),
        initialization_repository=wrapper,  # type: ignore[arg-type]
        graph_reader=graph_reader(),
    )
    assert wrapper.initialize_calls == 1
    assert wrapper.recovery_probes == 1
    replayed = _initialize(pg)
    assert replayed == receipt
    assert _counts(pg)["init_receipts"] == 1
    assert _counts(pg)["revisions"] == 1


def test_postgres_receipt_survives_later_child_revision(pg) -> None:
    receipt = _initialize(pg)
    stored = pg.world_graph.get_revision(WORLD_ID, receipt.published_revision_id)
    assert stored is not None
    child_payload = copy.deepcopy(stored.graph_payload)
    child_payload["objects"][0]["label"] = f"{child_payload['objects'][0]['label']} Child"
    child = pg.world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=receipt.published_revision_id,
            expected_parent_revision_id=receipt.published_revision_id,
            operation_ids=["op:reviewed-init-child"],
            graph_schema=stored.revision.graph_schema,
            graph_payload=child_payload,
            created_at=NOW,
        )
    )
    assert child.parent_revision_id == receipt.published_revision_id
    head = pg.world_graph.get_head(WORLD_ID)
    assert head is not None
    assert head.head_revision_id == child.revision_id
    assert head.head_revision_id != receipt.published_revision_id
    historical = pg.reviewed_world_initializations.get_for_world(WORLD_ID)
    assert historical == receipt
    genesis = pg.world_graph.get_revision(WORLD_ID, receipt.published_revision_id)
    assert genesis is not None
    assert genesis.revision.parent_revision_id is None
    assert canonical_sha256(genesis.graph_payload) == receipt.published_graph_payload_sha256


def test_postgres_adoption_rejects_initialized_world(pg) -> None:
    _initialize(pg)
    with pytest.raises(PersistenceIntegrityError) as exc:
        adopt_existing_world(
            _adoption_bytes(),
            adopted_at=NOW,
            adoption_repository=pg.existing_world_adoptions,
            graph_reader=adoption_graph_reader(),
        )
    assert exc.value.details["reason"] == "non_pristine_target"
    assert exc.value.details["family"] == "reviewed_world_initialization"
    assert _counts(pg)["adoption_receipts"] == 0


def test_postgres_initialization_rejects_adopted_world(pg) -> None:
    adopt_existing_world(
        _adoption_bytes(),
        adopted_at=NOW,
        adoption_repository=pg.existing_world_adoptions,
        graph_reader=adoption_graph_reader(),
    )
    with pytest.raises(PersistenceIntegrityError) as exc:
        _initialize(pg)
    assert exc.value.details["reason"] == "non_pristine_target"
    assert exc.value.details["family"] == "existing_world_adoption"
    assert _counts(pg)["init_receipts"] == 0


_EMPTY_COUNTS = {
    "heads": 0,
    "revisions": 0,
    "head_events": 0,
    "contributions": 0,
    "identity": 0,
    "artifacts": 0,
    "init_receipts": 0,
    "adoption_receipts": 0,
    "revisions_source": 0,
}


def _assert_initialized_edge(pg, receipt) -> None:
    assert "asrt:leads" in receipt.accepted_assertion_ids
    stored = pg.world_graph.get_revision(WORLD_ID, receipt.published_revision_id)
    assert stored is not None
    assert stored.revision.parent_revision_id is None
    rels = stored.graph_payload["relationships"]
    assert {item["relationship_id"] for item in rels} == {"rel:leads"}
    for record in stored.graph_payload["evidence_refs"]:
        assert record["source_revision_id"] == REV
    counts = _counts(pg)
    assert counts["heads"] == 1
    assert counts["revisions"] == 1
    assert counts["contributions"] == 1
    assert counts["artifacts"] == 1
    assert counts["revisions_source"] == 1
    assert counts["init_receipts"] == 1


def test_postgres_neutral_edge_identity_persists_relationship(pg) -> None:
    receipt = _initialize(pg)
    _assert_initialized_edge(pg, receipt)


def test_postgres_created_new_edge_identity_persists_relationship(pg) -> None:
    receipt = _initialize(pg, make_created_new_edge_command())
    _assert_initialized_edge(pg, receipt)


def test_postgres_non_create_new_node_identity_zero_mutation(pg) -> None:
    with pytest.raises(PersistenceIntegrityError) as exc:
        _initialize(pg, make_accepted_node_non_create_new_command())
    assert exc.value.details["reason"] == "accepted_identity_not_create_new"
    assert _counts(pg) == _EMPTY_COUNTS


def test_postgres_unsupported_edge_identity_zero_mutation(pg) -> None:
    with pytest.raises(PersistenceIntegrityError) as exc:
        _initialize(pg, make_accepted_edge_identity_command(IdentityOutcome.AMBIGUOUS))
    assert exc.value.details["reason"] == "accepted_edge_identity_unsupported"
    assert _counts(pg) == _EMPTY_COUNTS


def test_postgres_artifact_only_provenance_is_rejected(pg) -> None:
    with pytest.raises(PersistenceIntegrityError):
        _initialize(pg, make_artifact_only_command())
    assert _counts(pg) == _EMPTY_COUNTS


def test_postgres_revision_only_assertion_is_rejected(pg) -> None:
    with pytest.raises(PersistenceIntegrityError):
        _initialize(pg, make_revision_only_assertion_command())
    assert _counts(pg) == _EMPTY_COUNTS


def test_postgres_unreferenced_extra_artifact_zero_mutation(pg) -> None:
    with pytest.raises(PersistenceIntegrityError) as exc:
        _initialize(pg, make_unreferenced_extra_artifact_command())
    assert exc.value.details["reason"] == "unreferenced_source_artifact"
    assert _counts(pg) == _EMPTY_COUNTS


def test_postgres_unreferenced_extra_revision_zero_mutation(pg) -> None:
    with pytest.raises(PersistenceIntegrityError) as exc:
        _initialize(pg, make_unreferenced_extra_revision_command())
    assert exc.value.details["reason"] == "unreferenced_source_revision"
    assert _counts(pg) == _EMPTY_COUNTS


def test_postgres_typed_exact_retry_returns_stored_receipt(pg) -> None:
    first = _initialize(
        pg, make_first_world_family_command(evidence_domain=SourceDomain.WORLDBUILDING)
    )
    stored_hash = first.command_sha256
    before = _counts(pg)
    inner = pg.reviewed_world_initializations

    class _CountInitialize:
        def __init__(self) -> None:
            self.initialize_calls = 0

        def get(self, world_id: str, initialization_id: str):
            return inner.get(world_id, initialization_id)

        def get_for_world(self, world_id: str):
            return inner.get_for_world(world_id)

        def initialize(self, command, **kwargs: Any):
            self.initialize_calls += 1
            return inner.initialize(command, **kwargs)

    wrapper = _CountInitialize()
    recovered = initialize_reviewed_world(
        make_first_world_family_command(evidence_domain=SourceDomain.WORLDBUILDING),
        initialization_repository=wrapper,  # type: ignore[arg-type]
        graph_reader=graph_reader(),
    )
    assert recovered == first
    assert recovered.command_sha256 == stored_hash
    assert wrapper.initialize_calls == 0
    assert _counts(pg) == before


def test_postgres_typed_exact_under_lock_returns_stored_receipt(pg) -> None:
    stored = _initialize(
        pg, make_first_world_family_command(evidence_domain=SourceDomain.WORLDBUILDING)
    )
    before = _counts(pg)
    corrected = make_first_world_family_command(evidence_domain=SourceDomain.WORLDBUILDING)
    materialization = materialize_reviewed_world_initialization_v6(
        corrected, graph_reader=graph_reader()
    )
    replayed = pg.reviewed_world_initializations.initialize(
        corrected,
        graph_payload=materialization.graph_payload,
        graph_payload_sha256=materialization.graph_payload_sha256,
        accepted_assertion_ids=materialization.accepted_assertion_ids,
    )
    assert replayed == stored
    assert _counts(pg) == before


def test_postgres_typed_exact_lost_response_returns_stored_receipt(pg) -> None:
    stored = _initialize(
        pg, make_first_world_family_command(evidence_domain=SourceDomain.WORLDBUILDING)
    )
    inner = pg.reviewed_world_initializations

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

        def initialize(self, command, **kwargs: Any):
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


def test_postgres_family_other_delta_still_conflicts(pg) -> None:
    stored = _initialize(
        pg, make_first_world_family_command(evidence_domain=SourceDomain.WORLDBUILDING)
    )
    before = _counts(pg)
    with pytest.raises(IdempotencyConflictError):
        _initialize(
            pg,
            make_first_world_family_command(evidence_domain=SourceDomain.WORLDBUILDING).model_copy(
                update={"source_plan_id": "plan:different"}
            ),
        )
    assert pg.reviewed_world_initializations.get_for_world(WORLD_ID) == stored
    assert _counts(pg) == before


def test_postgres_typed_spans_survive_repository_reopen_and_native_index(pg):
    from dungeonmind.application.world_graph_projection import WorldGraphProjectionService
    from dungeonmind.application.world_graph_retrieval import (
        EvidenceTarget,
        SelectedSourceAnchorIndexRequest,
        WorldGraphRetrievalService,
    )
    from dungeonmind.contracts.projection_v2 import WorldGraphProjectionRequestV2
    from dungeonmind.infrastructure.postgres import PostgresRepositoryBundle

    command = make_command()
    # Two distinct reviewed passages on one node, plus independent node/edge support.
    payload = command.model_dump(mode="json")
    first = payload["reviewed_contribution"]["assertions"][0]["evidence_refs"][0]
    payload["reviewed_contribution"]["assertions"][0]["evidence_refs"].append(
        {
            **first,
            "evidence_ref_id": "ev:second-passage",
            "source_span_ref_id": "span:second-passage",
        }
    )
    command = type(command).model_validate(payload)
    receipt = _initialize(pg, command)
    # Reopen every repository/connection instead of using the producer's result.
    reopened = PostgresRepositoryBundle(pg.database)
    stored = reopened.world_graph.get_revision(WORLD_ID, receipt.published_revision_id)
    expected = {
        ref.evidence_ref_id: ref.model_dump(mode="json")
        for assertion in command.reviewed_contribution.assertions
        for ref in assertion.evidence_refs
    }
    assert {
        row["evidence_ref_id"]: row for row in stored.graph_payload["evidence_refs"]
    } == expected
    assert reopened.reviewed_world_initializations.get_for_world(WORLD_ID) == receipt
    assert _initialize(reopened, command) == receipt
    # A fresh Python process reopens persisted receipts/evidence with no producer objects.
    import os
    import subprocess
    import sys

    code = """
import os
from dungeonmind.infrastructure.postgres import PostgresDatabase, PostgresRepositoryBundle
bundle = PostgresRepositoryBundle(PostgresDatabase(os.environ['DUNGEONMIND_DATABASE_URL']))
receipt = bundle.reviewed_world_initializations.get_for_world('world:reviewed-init-fixture')
assert receipt.schema_version == 'dm_reviewed_world_initialization_receipt_v2'
stored = bundle.world_graph.get_revision(receipt.world_id, receipt.published_revision_id)
assert any(
    row['source_span_ref_id'] == 'span:second-passage'
    for row in stored.graph_payload['evidence_refs']
)
contribution = bundle.contributions.get(receipt.world_id, receipt.reviewed_contribution_id)
assert contribution.schema_version == 'dm_graph_contribution_v3'
"""
    child = subprocess.run(
        [sys.executable, "-c", code], env=os.environ.copy(), capture_output=True, text=True
    )
    assert child.returncode == 0, child.stderr
    projection = WorldGraphProjectionService(
        world_graph=reopened.world_graph,
        sources=reopened.sources,
        graph_reader=graph_reader(),
        reviewed_world_initializations=reopened.reviewed_world_initializations,
    )
    retrieval = WorldGraphRetrievalService(projection=projection, sources=reopened.sources)
    request = WorldGraphProjectionRequestV2(
        world_id=WORLD_ID,
        campaign_id=command.campaign_id,
        scope_mode="campaign",
        admissibility="gm",
        revision_pin=receipt.published_revision_id,
    )
    result = retrieval.get_object(request, object_id="obj:college")
    assert result.found
    assert {a.source_span_ref_id for a in result.anchors} >= {"span:fixture", "span:second-passage"}
    assert all(a.can_open_source and a.can_highlight_span for a in result.anchors)
    index = retrieval.list_selected_source_anchor_index(
        SelectedSourceAnchorIndexRequest(
            projection=request,
            targets=(EvidenceTarget("object", "obj:college"),),
        )
    )
    assert index.status == "complete"
    assert index.eligible_count >= 2
    assert index.unavailable_binding_count == 0
    assert _counts(reopened)["init_receipts"] == _counts(reopened)["revisions"] == 1


def test_postgres_party_registry_keeps_unreadable_typed_provenance(pg):
    from tests.unit.test_reviewed_world_initialization_materialization_v6 import (
        _party_registry_six_pc_command,
    )

    command = _party_registry_six_pc_command()
    from dungeonmind.application.graph_snapshot import VersionedUnionGraphSnapshotReader
    from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
    from dungeonmind_dnd.application.world_object_vocabulary import load_builtin_v3_descriptor

    reader = VersionedUnionGraphSnapshotReader(
        profile_registry=StaticSemanticProfileRegistry([load_builtin_v3_descriptor()])
    )
    receipt = initialize_reviewed_world(
        command, initialization_repository=pg.reviewed_world_initializations, graph_reader=reader
    )
    stored = pg.world_graph.get_revision(WORLD_ID, receipt.published_revision_id)
    assert len(stored.graph_payload["objects"]) == 6
    for row in stored.graph_payload["evidence_refs"]:
        assert row["schema_version"] == "dm_evidence_ref_v2"
        assert row["source_domain_key"] == "party_registry"
        assert row["source_span_ref_id"] is None
        assert not row["can_open_source"] and not row["can_highlight_span"]
    assert pg.reviewed_world_initializations.get_for_world(WORLD_ID) == receipt


def test_postgres_raw_writer_rejects_forged_span_before_rows(pg):
    command = make_command()
    materialization = materialize_reviewed_world_initialization_v6(
        command, graph_reader=graph_reader()
    )
    payload = materialization.graph_payload
    payload["evidence_refs"][0]["source_span_ref_id"] = "span:forged"
    with pytest.raises(PersistenceIntegrityError):
        pg.reviewed_world_initializations.initialize(
            command,
            graph_payload=payload,
            graph_payload_sha256=canonical_sha256(payload),
            accepted_assertion_ids=materialization.accepted_assertion_ids,
        )
    assert _counts(pg) == _EMPTY_COUNTS


@pytest.mark.parametrize("target", ["node", "alias", "edge", "endpoint"])
def test_postgres_raw_repository_cannot_rebind_reviewed_passages(pg, target):
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
        payload["relationships"][0]["target_object_id"] = "obj:headmaster"
    with pytest.raises(PersistenceIntegrityError):
        pg.reviewed_world_initializations.initialize(
            command,
            graph_payload=payload,
            graph_payload_sha256=canonical_sha256(payload),
            accepted_assertion_ids=materialized.accepted_assertion_ids,
        )
    assert _counts(pg) == _EMPTY_COUNTS


def test_postgres_raw_writer_freezes_caller_payload_before_source_writes(pg):
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

    writer = PostgresReviewedWorldInitializationRepository(pg.database, failure_hook=mutate_caller)
    receipt = writer.initialize(
        command,
        graph_payload=payload,
        graph_payload_sha256=canonical_sha256(expected),
        accepted_assertion_ids=accepted,
    )
    assert payload != expected and not accepted
    assert (
        pg.world_graph.get_revision(WORLD_ID, receipt.published_revision_id).graph_payload
        == expected
    )
    assert tuple(receipt.accepted_assertion_ids) == materialized.accepted_assertion_ids
