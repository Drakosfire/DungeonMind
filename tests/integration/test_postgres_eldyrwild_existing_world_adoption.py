"""PostgreSQL owning-boundary proof for the sealed Eldyrwild adoption bundle v2."""

from __future__ import annotations

import pytest

from dungeonmind.application.existing_world_adoption import (
    adopt_existing_world,
    parse_existing_world_adoption_bundle,
)
from dungeonmind.contracts.contribution import GraphContributionV2
from dungeonmind.contracts.evidence import EvidenceRef
from dungeonmind.contracts.existing_world_adoption import (
    EXISTING_WORLD_ADOPTION_RECEIPT_V2_SCHEMA,
    existing_world_adoption_bundle_v2_canonical_bytes,
)
from dungeonmind.contracts.identity import IdentityDecisionRecordV2
from dungeonmind.contracts.vocabulary import ContributionEpistemicKind
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import (
    ExistingWorldAdoptionOutcomeUnknownError,
    IdempotencyConflictError,
    PersistenceUnavailableError,
)
from dungeonmind.infrastructure.postgres.serialization import model_fingerprint
from tests.unit.test_eldyrwild_existing_world_adoption_bundle_v2 import (
    ADOPTION_ID,
    BUNDLE_SHA256,
    EXPECTED_ASPECT_OBJECTS,
    EXPECTED_ASPECT_SELECTED_RELATIONSHIPS,
    EXPECTED_CONTRIBUTIONS,
    EXPECTED_IDENTITY_DECISIONS,
    EXPECTED_OBJECTS,
    EXPECTED_RELATIONSHIPS,
    EXPECTED_SECONDARY_ASPECTS,
    EXPECTED_SOURCE_ARTIFACTS,
    EXPECTED_SOURCE_REVISIONS,
    GRAPH_PAYLOAD_SHA256,
    LATER,
    NOW,
    PRECOMMIT_FAILURE_STAGES,
    PUBLISHED_REVISION_ID,
    WITNESS_CONTRIBUTION_ID,
    WITNESS_RAW_EVIDENCE_ID,
    WITNESS_SOURCE_REVISIONS,
    WORLD_ID,
    aspect_selected,
    contribution_evidence_bindings,
    eldyrwild_graph_reader,
    parse_sealed_bundle,
    raw_bundle,
)

pytestmark = pytest.mark.integration


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
        "receipts": (
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


def _zero_counts() -> dict[str, int]:
    return {
        "heads": 0,
        "revisions": 0,
        "head_events": 0,
        "contributions": 0,
        "identity": 0,
        "artifacts": 0,
        "receipts": 0,
        "revisions_source": 0,
    }


def _adopt(pg, raw: bytes | None = None, *, adopted_at=NOW):
    return adopt_existing_world(
        raw if raw is not None else raw_bundle(),
        adopted_at=adopted_at,
        adoption_repository=pg.existing_world_adoptions,
        graph_reader=eldyrwild_graph_reader(),
    )


def _source_ids(pg) -> tuple[set[str], set[str]]:
    with pg.database.connect() as conn:
        artifact_rows = conn.execute(
            """
            SELECT source_artifact_id
            FROM dungeonmind.source_artifacts
            WHERE world_id = %s
            """,
            (WORLD_ID,),
        ).fetchall()
        revision_rows = conn.execute(
            """
            SELECT sr.source_revision_id
            FROM dungeonmind.source_revisions AS sr
            JOIN dungeonmind.source_artifacts AS sa
              ON sa.source_artifact_id = sr.source_artifact_id
            WHERE sa.world_id = %s
            """,
            (WORLD_ID,),
        ).fetchall()
    return (
        {row["source_artifact_id"] for row in artifact_rows},
        {row["source_revision_id"] for row in revision_rows},
    )


def _assert_current_graph(pg) -> None:
    stored = pg.world_graph.get_revision(WORLD_ID, PUBLISHED_REVISION_ID)
    assert stored is not None
    payload = stored.graph_payload
    assert canonical_sha256(payload) == GRAPH_PAYLOAD_SHA256
    assert stored.revision.graph_schema == "dm_union_graph_v6"
    assert stored.revision.parent_revision_id is None
    assert stored.revision.operation_ids == [ADOPTION_ID]
    assert len(payload["objects"]) == EXPECTED_OBJECTS
    assert len(payload["relationships"]) == EXPECTED_RELATIONSHIPS
    aspects = [aspect for obj in payload["objects"] for aspect in obj.get("aspects") or []]
    assert len(aspects) == EXPECTED_SECONDARY_ASPECTS
    aspect_objects = {
        obj["object_id"]: (obj["kind"], aspect["kind"])
        for obj in payload["objects"]
        for aspect in obj.get("aspects") or []
    }
    assert aspect_objects == EXPECTED_ASPECT_OBJECTS
    assert len(aspect_selected(payload["relationships"])) == EXPECTED_ASPECT_SELECTED_RELATIONSHIPS


def _assert_history_round_trip(pg) -> dict[str, int]:
    expected = parse_sealed_bundle()
    loaded_contributions = pg.contributions.list_for_world(WORLD_ID)
    loaded_identity = pg.identity_decisions.list_for_world(WORLD_ID)
    assert all(isinstance(item, GraphContributionV2) for item in loaded_contributions)
    assert all(isinstance(item, IdentityDecisionRecordV2) for item in loaded_identity)
    expected_contribution_ids = {item.contribution_id for item in expected.contributions}
    loaded_contribution_ids = {item.contribution_id for item in loaded_contributions}
    assert loaded_contribution_ids == expected_contribution_ids
    expected_decision_ids = {item.decision_id for item in expected.identity_decisions}
    loaded_decision_ids = {item.decision_id for item in loaded_identity}
    assert loaded_decision_ids == expected_decision_ids
    loaded_by_contribution = {item.contribution_id: item for item in loaded_contributions}
    for contribution in expected.contributions:
        loaded = loaded_by_contribution[contribution.contribution_id]
        assert model_fingerprint(loaded) == model_fingerprint(contribution)
        assert loaded.model_dump(mode="json") == contribution.model_dump(mode="json")
        assert loaded.assertion_corrections == contribution.assertion_corrections
    loaded_by_decision = {item.decision_id: item for item in loaded_identity}
    for decision in expected.identity_decisions:
        loaded = loaded_by_decision[decision.decision_id]
        assert model_fingerprint(loaded) == model_fingerprint(decision)
        assert loaded.model_dump(mode="json") == decision.model_dump(mode="json")
        assert loaded.merge_side_effects == decision.merge_side_effects
    expected_artifact_ids = {item.source_artifact_id for item in expected.source_artifacts}
    expected_revision_ids = {item.source_revision_id for item in expected.source_revisions}
    durable_artifact_ids, durable_revision_ids = _source_ids(pg)
    assert durable_artifact_ids == expected_artifact_ids
    assert durable_revision_ids == expected_revision_ids
    for artifact in expected.source_artifacts:
        loaded = pg.sources.get_artifact(artifact.source_artifact_id)
        assert loaded is not None
        assert model_fingerprint(loaded) == model_fingerprint(artifact)
        assert loaded.model_dump(mode="json") == artifact.model_dump(mode="json")
    for revision in expected.source_revisions:
        loaded = pg.sources.get_revision(revision.source_revision_id)
        assert loaded is not None
        assert model_fingerprint(loaded) == model_fingerprint(revision)
        assert loaded.model_dump(mode="json") == revision.model_dump(mode="json")
        assert loaded.content_sha256 == revision.content_sha256
    expected_corrections = [
        correction.model_dump(mode="json")
        for contribution in expected.contributions
        for correction in contribution.assertion_corrections
    ]
    loaded_corrections = [
        correction.model_dump(mode="json")
        for contribution in loaded_contributions
        for correction in contribution.assertion_corrections
    ]
    expected_candidates = [
        (contribution.contribution_id, assertion.assertion_id, assertion.epistemic_kind.value)
        for contribution in expected.contributions
        for assertion in contribution.assertions
        if assertion.epistemic_kind is ContributionEpistemicKind.SOURCE_DERIVED_CANDIDATE
    ]
    loaded_candidates = [
        (contribution.contribution_id, assertion.assertion_id, assertion.epistemic_kind.value)
        for contribution in loaded_contributions
        for assertion in contribution.assertions
        if assertion.epistemic_kind is ContributionEpistemicKind.SOURCE_DERIVED_CANDIDATE
    ]
    expected_merges = [
        decision.merge_side_effects.model_dump(mode="json")
        for decision in expected.identity_decisions
        if decision.merge_side_effects is not None
    ]
    loaded_merges = [
        decision.merge_side_effects.model_dump(mode="json")
        for decision in loaded_identity
        if decision.merge_side_effects is not None
    ]
    assert expected_corrections
    assert loaded_corrections == expected_corrections
    assert expected_candidates
    assert loaded_candidates == expected_candidates
    assert expected_merges
    assert loaded_merges == expected_merges
    return {
        "corrections": len(expected_corrections),
        "source_derived_candidate": len(expected_candidates),
        "merge_side_effects": len(expected_merges),
        "contributions": len(expected_contribution_ids),
        "identity_decisions": len(expected_decision_ids),
        "source_artifacts": len(expected_artifact_ids),
        "source_revisions": len(expected_revision_ids),
    }


def _assert_evidence_identity(pg) -> None:
    expected = parse_sealed_bundle()
    bindings = contribution_evidence_bindings(expected)
    with pg.database.connect() as conn:
        rows = conn.execute(
            """
            SELECT evidence_ref_id, record_fingerprint
            FROM dungeonmind.evidence_refs
            """
        ).fetchall()
    durable_ids = [row["evidence_ref_id"] for row in rows]
    assert len(durable_ids) == len(set(durable_ids))
    fingerprints = {row["evidence_ref_id"]: row["record_fingerprint"] for row in rows}
    for evidence_id, payload in bindings.items():
        assert evidence_id in fingerprints
        expected_ref = EvidenceRef.model_validate(payload)
        assert fingerprints[evidence_id] == model_fingerprint(expected_ref)
    contribution = next(
        item for item in expected.contributions if item.contribution_id == WITNESS_CONTRIBUTION_ID
    )
    witness_ids = {
        ref.evidence_ref_id
        for assertion in contribution.assertions
        for ref in assertion.evidence_refs
        if ref.evidence_ref_id.startswith(WITNESS_RAW_EVIDENCE_ID + ":dmv1:")
        and ref.source_revision_id in WITNESS_SOURCE_REVISIONS
    }
    assert len(witness_ids) == 2
    assert witness_ids <= set(fingerprints)


def _changed_valid_bundle_bytes() -> bytes:
    bundle = parse_sealed_bundle()
    changed = bundle.model_copy(
        update={
            "source_provenance": bundle.source_provenance.model_copy(
                update={"producer_revision": "ab" * 20}
            )
        }
    )
    raw = existing_world_adoption_bundle_v2_canonical_bytes(changed)
    reparsed = parse_existing_world_adoption_bundle(
        raw,
        graph_reader=eldyrwild_graph_reader(),
    )
    assert reparsed.adoption_id == ADOPTION_ID
    assert reparsed.world_id == WORLD_ID
    assert reparsed.source_provenance.producer_revision == "ab" * 20
    return raw


def test_postgres_first_adoption_commits_receipt_graph_and_history(pg) -> None:
    assert _counts(pg) == _zero_counts()
    receipt = _adopt(pg)
    counts = _counts(pg)
    assert counts["receipts"] == 1
    assert counts["heads"] == 1
    assert counts["revisions"] == 1
    assert counts["head_events"] == 1
    assert counts["contributions"] == EXPECTED_CONTRIBUTIONS
    assert counts["identity"] == EXPECTED_IDENTITY_DECISIONS
    assert counts["artifacts"] == EXPECTED_SOURCE_ARTIFACTS
    assert counts["revisions_source"] == EXPECTED_SOURCE_REVISIONS
    assert receipt.schema_version == EXISTING_WORLD_ADOPTION_RECEIPT_V2_SCHEMA
    assert receipt.world_id == WORLD_ID
    assert receipt.adoption_id == ADOPTION_ID
    assert receipt.bundle_sha256 == BUNDLE_SHA256
    assert receipt.published_revision_id == PUBLISHED_REVISION_ID
    assert receipt.graph_payload_sha256 == GRAPH_PAYLOAD_SHA256
    assert receipt.source_artifact_count == EXPECTED_SOURCE_ARTIFACTS
    assert receipt.source_revision_count == EXPECTED_SOURCE_REVISIONS
    assert receipt.contribution_count == EXPECTED_CONTRIBUTIONS
    assert receipt.identity_decision_count == EXPECTED_IDENTITY_DECISIONS
    loaded = pg.existing_world_adoptions.get(WORLD_ID, ADOPTION_ID)
    assert loaded == receipt
    assert pg.existing_world_adoptions.get_for_world(WORLD_ID) == receipt
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == PUBLISHED_REVISION_ID
    _assert_current_graph(pg)
    totals = _assert_history_round_trip(pg)
    assert totals["contributions"] == EXPECTED_CONTRIBUTIONS
    assert totals["identity_decisions"] == EXPECTED_IDENTITY_DECISIONS
    _assert_evidence_identity(pg)


def test_postgres_exact_retry_is_idempotent(pg) -> None:
    first = _adopt(pg)
    replayed = _adopt(pg, adopted_at=LATER)
    assert replayed == first
    assert replayed.adopted_at == NOW
    counts = _counts(pg)
    assert counts["receipts"] == 1
    assert counts["revisions"] == 1
    assert counts["contributions"] == EXPECTED_CONTRIBUTIONS
    assert counts["identity"] == EXPECTED_IDENTITY_DECISIONS
    assert counts["artifacts"] == EXPECTED_SOURCE_ARTIFACTS
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == PUBLISHED_REVISION_ID
    _assert_current_graph(pg)
    _assert_history_round_trip(pg)


def test_postgres_changed_valid_bundle_conflicts_without_mutation(pg) -> None:
    first = _adopt(pg)
    original_counts = _counts(pg)
    changed = _changed_valid_bundle_bytes()
    with pytest.raises(IdempotencyConflictError) as exc:
        _adopt(pg, changed, adopted_at=LATER)
    assert exc.value.details["world_id"] == WORLD_ID
    assert exc.value.details["adoption_id"] == ADOPTION_ID
    assert pg.existing_world_adoptions.get_for_world(WORLD_ID) == first
    assert _counts(pg) == original_counts
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == PUBLISHED_REVISION_ID
    _assert_current_graph(pg)
    _assert_history_round_trip(pg)


@pytest.mark.parametrize("stage", PRECOMMIT_FAILURE_STAGES)
def test_postgres_every_precommit_failpoint_rolls_back_then_retries(
    migrated_database: str,
    pg,
    stage: str,
) -> None:
    from dungeonmind.infrastructure.postgres import (
        PostgresDatabase,
        PostgresExistingWorldAdoptionRepository,
    )

    def hook(current: str) -> None:
        if current == stage:
            raise RuntimeError(f"injected {stage} abort")

    repository = PostgresExistingWorldAdoptionRepository(
        PostgresDatabase(migrated_database),
        failure_hook=hook,
    )
    with pytest.raises(ExistingWorldAdoptionOutcomeUnknownError):
        adopt_existing_world(
            raw_bundle(),
            adopted_at=NOW,
            adoption_repository=repository,
            graph_reader=eldyrwild_graph_reader(),
        )
    assert _counts(pg) == _zero_counts()
    assert pg.existing_world_adoptions.get_for_world(WORLD_ID) is None
    receipt = _adopt(pg)
    assert receipt.published_revision_id == PUBLISHED_REVISION_ID
    assert _counts(pg)["receipts"] == 1
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == PUBLISHED_REVISION_ID


def test_postgres_postcommit_response_loss_recovers_the_durable_receipt(pg) -> None:
    inner = pg.existing_world_adoptions

    class _CommitThenUnavailable:
        def __init__(self) -> None:
            self.adopt_returned = False
            self.recovery_probes = 0

        def adopt(self, command):
            receipt = inner.adopt(command)
            self.adopt_returned = True
            committed = inner.get_for_world(WORLD_ID)
            assert committed == receipt
            raise PersistenceUnavailableError("response lost after real commit")

        def get(self, world_id: str, adoption_id: str):
            return inner.get(world_id, adoption_id)

        def get_for_world(self, world_id: str):
            receipt = inner.get_for_world(world_id)
            if self.adopt_returned:
                self.recovery_probes += 1
            return receipt

    wrapper = _CommitThenUnavailable()
    receipt = adopt_existing_world(
        raw_bundle(),
        adopted_at=NOW,
        adoption_repository=wrapper,
        graph_reader=eldyrwild_graph_reader(),
    )
    assert wrapper.adopt_returned is True
    assert wrapper.recovery_probes == 1
    assert receipt.adoption_id == ADOPTION_ID
    assert receipt.bundle_sha256 == BUNDLE_SHA256
    assert receipt.published_revision_id == PUBLISHED_REVISION_ID
    assert pg.existing_world_adoptions.get_for_world(WORLD_ID) == receipt
    replayed = _adopt(pg, adopted_at=LATER)
    assert replayed == receipt
    assert replayed.adopted_at == NOW
    counts = _counts(pg)
    assert counts["receipts"] == 1
    assert counts["revisions"] == 1
    assert counts["contributions"] == EXPECTED_CONTRIBUTIONS
    _assert_current_graph(pg)
    _assert_history_round_trip(pg)
