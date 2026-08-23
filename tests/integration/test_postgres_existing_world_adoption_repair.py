"""PostgreSQL owning-boundary proofs for existing-world adoption repair."""

from __future__ import annotations

import pytest
from psycopg.types.json import Jsonb

from dungeonmind.application.existing_world_adoption import adopt_existing_world
from dungeonmind.application.existing_world_adoption_repair import (
    repair_existing_world_adoption_source_classification,
    sealed_membership_sha256,
)
from dungeonmind.contracts.existing_world_adoption import (
    ExistingWorldAdoptionReceiptV3,
    ExistingWorldAdoptionReceiptV4,
)
from dungeonmind.contracts.vocabulary import Visibility
from dungeonmind.domain.errors import (
    ExistingWorldAdoptionOutcomeUnknownError,
    PersistenceIntegrityError,
)
from dungeonmind.domain.existing_world_membership import (
    existing_world_adoption_membership_sha256,
)
from dungeonmind.infrastructure.postgres import (
    PostgresDatabase,
    PostgresExistingWorldAdoptionRepository,
)
from dungeonmind.infrastructure.postgres.serialization import model_fingerprint
from tests.integration.test_postgres_existing_world_adoption import (
    _counts,
    _graph_revision_ids,
)
from tests.unit.test_existing_world_adoption import (
    NOW,
    WORLD_ID,
    graph_reader,
    v2_bundle_bytes,
)
from tests.unit.test_existing_world_adoption_repair import (
    REPAIRED_AT,
    _intent,
    _repairable_bundle,
)

pytestmark = pytest.mark.integration


def _adopt_repairable(pg):
    bundle = _repairable_bundle()
    raw = v2_bundle_bytes(bundle)
    receipt = adopt_existing_world(
        raw,
        adopted_at=NOW,
        adoption_repository=pg.existing_world_adoptions,
        graph_reader=graph_reader(),
    )
    assert isinstance(receipt, ExistingWorldAdoptionReceiptV3)
    return bundle, raw, receipt


def _durable_membership(pg, world_id: str) -> str:
    artifacts = pg.sources.list_artifacts_for_world(world_id)
    return existing_world_adoption_membership_sha256(
        source_artifacts=artifacts,
        source_revisions=[
            revision
            for artifact in artifacts
            for revision in pg.sources.list_revisions(artifact.source_artifact_id)
        ],
        contributions=pg.contributions.list_for_world(world_id),
        identity_decisions=pg.identity_decisions.list_for_world(world_id),
    )


def _rewrite_artifact(pg, artifact) -> None:
    with pg.database.connect() as conn:
        conn.execute(
            """
            UPDATE dungeonmind.source_artifacts
            SET campaign_id = %s,
                visibility = %s,
                record_fingerprint = %s,
                payload = %s
            WHERE source_artifact_id = %s
            """,
            (
                artifact.campaign_id,
                artifact.visibility.value if artifact.visibility is not None else None,
                model_fingerprint(artifact),
                Jsonb(artifact.model_dump(mode="json")),
                artifact.source_artifact_id,
            ),
        )
        conn.commit()


def _rewrite_v3_membership(pg, world_id: str, digest: str) -> None:
    stored = pg.existing_world_adoptions.get_for_world(world_id)
    assert isinstance(stored, ExistingWorldAdoptionReceiptV3)
    rewritten = stored.model_copy(update={"membership_sha256": digest})
    with pg.database.connect() as conn:
        conn.execute(
            """
            UPDATE dungeonmind.existing_world_adoptions
            SET record_fingerprint = %s, payload = %s
            WHERE world_id = %s
            """,
            (
                model_fingerprint(rewritten),
                Jsonb(rewritten.model_dump(mode="json")),
                world_id,
            ),
        )
        conn.commit()


def _inject_allowed_corruption(pg, bundle) -> str:
    first = bundle.source_artifacts[0].model_copy(update={"visibility": Visibility.GM})
    second = bundle.source_artifacts[1].model_copy(update={"campaign_id": None})
    _rewrite_artifact(pg, first)
    _rewrite_artifact(pg, second)
    digest = _durable_membership(pg, bundle.world_id)
    _rewrite_v3_membership(pg, bundle.world_id, digest)
    return digest


def _repair(pg, raw, bundle, *, apply: bool = True, repository=None):
    return repair_existing_world_adoption_source_classification(
        raw,
        repair_intent=_intent(bundle),
        repaired_at=REPAIRED_AT,
        adoption_repository=(
            repository if repository is not None else pg.existing_world_adoptions
        ),
        graph_reader=graph_reader(),
        apply=apply,
    )


@pytest.mark.integration
def test_postgres_corrupted_v3_repair_is_atomic_and_replayable(pg) -> None:
    bundle, raw, v3 = _adopt_repairable(pg)
    head_before = pg.world_graph.get_head(WORLD_ID)
    m0 = sealed_membership_sha256(bundle)
    observed = _inject_allowed_corruption(pg, bundle)
    assert observed != m0
    dry = _repair(pg, raw, bundle, apply=False)
    assert isinstance(dry, ExistingWorldAdoptionReceiptV4)
    stored = pg.existing_world_adoptions.get_for_world(WORLD_ID)
    assert isinstance(stored, ExistingWorldAdoptionReceiptV3)
    assert not isinstance(stored, ExistingWorldAdoptionReceiptV4)
    repaired = _repair(pg, raw, bundle, apply=True)
    assert isinstance(repaired, ExistingWorldAdoptionReceiptV4)
    assert repaired.membership_sha256 == m0
    assert repaired.effective_membership_sha256 != m0
    assert repaired.published_revision_id == v3.published_revision_id
    assert pg.world_graph.get_head(WORLD_ID) == head_before
    assert (
        repaired.source_classification_repair.observed_pre_repair_membership_sha256
        == observed
    )
    first = pg.sources.get_artifact(bundle.source_artifacts[0].source_artifact_id)
    second = pg.sources.get_artifact(bundle.source_artifacts[1].source_artifact_id)
    assert first is not None and first.visibility is Visibility.GM
    assert second is not None and second.campaign_id is None
    replayed = _repair(pg, raw, bundle, apply=True)
    assert (
        replayed.source_classification_repair.repair_id
        == repaired.source_classification_repair.repair_id
    )
    with pytest.raises(PersistenceIntegrityError) as exc_info:
        repair_existing_world_adoption_source_classification(
            raw,
            repair_intent=_intent(bundle, campaign=False),
            repaired_at=REPAIRED_AT,
            adoption_repository=pg.existing_world_adoptions,
            graph_reader=graph_reader(),
        )
    assert exc_info.value.details.get("reason") == "adoption_repair_identity_mismatch"


@pytest.mark.integration
def test_postgres_repair_precommit_failure_rolls_back(migrated_database: str, pg) -> None:
    bundle, raw, _v3 = _adopt_repairable(pg)
    _inject_allowed_corruption(pg, bundle)

    def hook(stage: str) -> None:
        if stage == "repaired_artifacts":
            raise RuntimeError("injected repaired_artifacts abort")

    repository = PostgresExistingWorldAdoptionRepository(
        PostgresDatabase(migrated_database),
        failure_hook=hook,
    )
    with pytest.raises(ExistingWorldAdoptionOutcomeUnknownError):
        _repair(pg, raw, bundle, repository=repository)
    stored = pg.existing_world_adoptions.get_for_world(WORLD_ID)
    assert isinstance(stored, ExistingWorldAdoptionReceiptV3)
    assert not isinstance(stored, ExistingWorldAdoptionReceiptV4)


@pytest.mark.integration
def test_postgres_repair_receipt_stage_failure_rolls_back(
    migrated_database: str, pg
) -> None:
    bundle, raw, v3 = _adopt_repairable(pg)
    observed = _inject_allowed_corruption(pg, bundle)
    counts_before = _counts(pg)
    graph_ids_before = _graph_revision_ids(pg, WORLD_ID)
    head_before = pg.world_graph.get_head(WORLD_ID)
    stored_before = pg.existing_world_adoptions.get_for_world(WORLD_ID)
    assert isinstance(stored_before, ExistingWorldAdoptionReceiptV3)
    fingerprint_before = model_fingerprint(stored_before)
    first_id = bundle.source_artifacts[0].source_artifact_id
    second_id = bundle.source_artifacts[1].source_artifact_id

    def hook(stage: str) -> None:
        if stage == "receipt":
            raise RuntimeError("injected receipt abort")

    repository = PostgresExistingWorldAdoptionRepository(
        PostgresDatabase(migrated_database),
        failure_hook=hook,
    )
    with pytest.raises(ExistingWorldAdoptionOutcomeUnknownError):
        _repair(pg, raw, bundle, repository=repository)
    stored = pg.existing_world_adoptions.get_for_world(WORLD_ID)
    assert isinstance(stored, ExistingWorldAdoptionReceiptV3)
    assert not isinstance(stored, ExistingWorldAdoptionReceiptV4)
    assert stored.schema_version == v3.schema_version
    assert stored.membership_sha256 == observed
    assert model_fingerprint(stored) == fingerprint_before
    assert _counts(pg) == counts_before
    assert _graph_revision_ids(pg, WORLD_ID) == graph_ids_before
    assert pg.world_graph.get_head(WORLD_ID) == head_before
    first = pg.sources.get_artifact(first_id)
    second = pg.sources.get_artifact(second_id)
    assert first is not None and first.visibility is Visibility.GM
    assert second is not None and second.campaign_id is None


@pytest.mark.integration
def test_postgres_receipt_membership_must_match_observed_rows(pg) -> None:
    bundle, raw, v3 = _adopt_repairable(pg)
    mutated = bundle.source_artifacts[0].model_copy(update={"visibility": Visibility.GM})
    _rewrite_artifact(pg, mutated)
    assert v3.membership_sha256 == sealed_membership_sha256(bundle)
    with pytest.raises(PersistenceIntegrityError) as exc_info:
        _repair(pg, raw, bundle)
    assert exc_info.value.details.get("reason") == "adoption_repair_membership_mismatch"
