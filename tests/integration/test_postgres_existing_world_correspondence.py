"""PostgreSQL owning-boundary proof for existing-world correspondence.

The checker runs against the real adopted Eldyrwild world produced by the
unchanged #34 adoption path. Every proof asserts zero durable mutation:
classifications are returned, corruption raises typed integrity errors, and
no check ever writes a row, advances a head, or manufactures a receipt.
"""

from __future__ import annotations

import copy

import pytest
from psycopg.types.json import Jsonb

from dungeonmind.application.existing_world_adoption import (
    adopt_existing_world,
    parse_existing_world_adoption_bundle,
)
from dungeonmind.application.existing_world_correspondence import (
    ExistingWorldCorrespondenceService,
)
from dungeonmind.contracts.existing_world_adoption import (
    existing_world_adoption_bundle_v2_canonical_bytes,
)
from dungeonmind.contracts.existing_world_correspondence import (
    CORRESPONDENCE_CHECK_ORDER,
)
from dungeonmind.contracts.graph import StoredGraphRevision
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.postgres.serialization import model_fingerprint
from tests.integration.test_postgres_eldyrwild_existing_world_adoption import (
    _adopted_counts,
    _counts,
    _zero_counts,
)
from tests.unit.test_eldyrwild_existing_world_adoption_bundle_v2 import (
    ADOPTION_ID,
    NOW,
    PUBLISHED_REVISION_ID,
    SOURCE_WORLD_REVISION_ID,
    WITNESS_CONTRIBUTION_ID,
    WORLD_ID,
    eldyrwild_graph_reader,
    parse_sealed_bundle,
    raw_bundle,
)

pytestmark = pytest.mark.integration

CHANGED_SOURCE_REVISION_ID = "rev:" + "f0" * 16


def _service(pg) -> ExistingWorldCorrespondenceService:
    return ExistingWorldCorrespondenceService(
        adoption_repository=pg.existing_world_adoptions,
        world_graph_repository=pg.world_graph,
        contribution_repository=pg.contributions,
        identity_repository=pg.identity_decisions,
        source_repository=pg.sources,
        graph_reader=eldyrwild_graph_reader(),
    )


def _adopt(pg) -> None:
    adopt_existing_world(
        raw_bundle(),
        adopted_at=NOW,
        adoption_repository=pg.existing_world_adoptions,
        graph_reader=eldyrwild_graph_reader(),
    )


def _changed_source_snapshot_bytes() -> bytes:
    bundle = parse_sealed_bundle()
    changed = bundle.model_copy(
        update={
            "source_provenance": bundle.source_provenance.model_copy(
                update={"source_world_revision_id": CHANGED_SOURCE_REVISION_ID}
            )
        }
    )
    raw = existing_world_adoption_bundle_v2_canonical_bytes(changed)
    reparsed = parse_existing_world_adoption_bundle(
        raw,
        graph_reader=eldyrwild_graph_reader(),
    )
    assert reparsed.source_provenance.source_world_revision_id == CHANGED_SOURCE_REVISION_ID
    return raw


def _changed_adoption_id_snapshot_bytes() -> bytes:
    """Canonical bundle identical to the adopted one except ``adoption_id``."""
    bundle = parse_sealed_bundle()
    changed = bundle.model_copy(update={"adoption_id": ADOPTION_ID + "-tampered"})
    raw = existing_world_adoption_bundle_v2_canonical_bytes(changed)
    reparsed = parse_existing_world_adoption_bundle(
        raw,
        graph_reader=eldyrwild_graph_reader(),
    )
    assert reparsed.adoption_id == ADOPTION_ID + "-tampered"
    assert (
        reparsed.source_provenance.source_world_revision_id == SOURCE_WORLD_REVISION_ID
    )
    return raw


def _evidence_referenced_source_revision_id() -> str:
    bundle = parse_sealed_bundle()
    snapshot = eldyrwild_graph_reader().parse(
        graph_schema=bundle.graph_schema,
        graph_payload=bundle.graph_payload,
    )
    for record in snapshot.evidence.values():
        if record.source_revision_id is not None:
            return record.source_revision_id
    raise AssertionError("fixture evidence must reference at least one source revision")


def _coherent_contribution_tamper(pg) -> str:
    """Rewrite one durable contribution the way a coherent future writer would:
    same identity columns, new payload content, matching fingerprint."""
    stored = pg.contributions.get(WORLD_ID, WITNESS_CONTRIBUTION_ID)
    assert stored is not None
    mutated = stored.model_copy(update={"extraction_profile": "tampered-postgres-profile"})
    with pg.database.connect() as conn:
        conn.execute(
            """
            UPDATE dungeonmind.graph_contributions
            SET payload = %s, record_fingerprint = %s
            WHERE world_id = %s AND contribution_id = %s
            """,
            (
                Jsonb(mutated.model_dump(mode="json")),
                model_fingerprint(mutated),
                WORLD_ID,
                WITNESS_CONTRIBUTION_ID,
            ),
        )
        conn.commit()
    return WITNESS_CONTRIBUTION_ID


def _coherent_graph_payload_tamper(pg) -> str:
    """Coherently rewrite the adopted graph payload across every durable
    authority (revision payload, envelope digest, receipt pin) so the durable
    world reconstructs successfully but no longer matches the snapshot."""
    stored = pg.world_graph.get_revision(WORLD_ID, PUBLISHED_REVISION_ID)
    assert stored is not None
    payload = copy.deepcopy(stored.graph_payload)
    payload["objects"][0]["label"] = "Tampered Wizard College"
    new_hash = canonical_sha256(payload)
    new_envelope = stored.revision.model_copy(update={"graph_payload_sha256": new_hash})
    new_stored = StoredGraphRevision(revision=new_envelope, graph_payload=payload)
    receipt = pg.existing_world_adoptions.get_for_world(WORLD_ID)
    assert receipt is not None
    new_receipt = receipt.model_copy(update={"graph_payload_sha256": new_hash})
    with pg.database.connect() as conn:
        conn.execute(
            """
            UPDATE dungeonmind.graph_revisions
            SET graph_payload = %s,
                revision_payload = %s,
                graph_payload_sha256 = %s,
                record_fingerprint = %s
            WHERE world_id = %s AND revision_id = %s
            """,
            (
                Jsonb(payload),
                Jsonb(new_envelope.model_dump(mode="json")),
                new_hash,
                model_fingerprint(new_stored),
                WORLD_ID,
                PUBLISHED_REVISION_ID,
            ),
        )
        conn.execute(
            """
            UPDATE dungeonmind.existing_world_adoptions
            SET graph_payload_sha256 = %s, payload = %s, record_fingerprint = %s
            WHERE world_id = %s
            """,
            (
                new_hash,
                Jsonb(new_receipt.model_dump(mode="json")),
                model_fingerprint(new_receipt),
                WORLD_ID,
            ),
        )
        conn.commit()
    return new_hash


def test_postgres_exact_adopted_state_corresponds_and_stays_read_only(pg) -> None:
    _adopt(pg)
    before = _counts(pg)
    assert before == _adopted_counts()
    result = _service(pg).check(raw_bundle(), world_id=WORLD_ID)
    assert result.classification == "CORRESPONDING"
    assert result.world_id == WORLD_ID
    assert result.observed_source_revision == SOURCE_WORLD_REVISION_ID
    assert result.adopted_source_revision == SOURCE_WORLD_REVISION_ID
    assert result.adoption_id == ADOPTION_ID
    assert result.adopted_revision == PUBLISHED_REVISION_ID
    assert [check.check for check in result.checks] == list(CORRESPONDENCE_CHECK_ORDER)
    assert all(check.outcome == "match" for check in result.checks)
    repeated = _service(pg).check(raw_bundle(), world_id=WORLD_ID)
    assert repeated.model_dump(mode="json") == result.model_dump(mode="json")
    after = _counts(pg)
    assert after == before
    assert after["head_events"] == 1
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == PUBLISHED_REVISION_ID


def test_postgres_changed_valid_snapshot_is_stale_and_read_only(pg) -> None:
    _adopt(pg)
    before = _counts(pg)
    result = _service(pg).check(_changed_source_snapshot_bytes(), world_id=WORLD_ID)
    assert result.classification == "STALE"
    assert result.observed_source_revision == CHANGED_SOURCE_REVISION_ID
    assert result.adopted_source_revision == SOURCE_WORLD_REVISION_ID
    assert result.adoption_id == ADOPTION_ID
    assert result.adopted_revision == PUBLISHED_REVISION_ID
    checks = {check.check: check for check in result.checks}
    assert checks["source_identity"].outcome == "diverged"
    assert CHANGED_SOURCE_REVISION_ID in checks["source_identity"].detail
    assert SOURCE_WORLD_REVISION_ID in checks["source_identity"].detail
    for name in CORRESPONDENCE_CHECK_ORDER[1:]:
        assert checks[name].outcome == "not_evaluated"
    assert _counts(pg) == before


def test_postgres_coherent_contribution_drift_is_mismatch_with_matching_counts(pg) -> None:
    _adopt(pg)
    before = _counts(pg)
    tampered_id = _coherent_contribution_tamper(pg)
    assert _counts(pg) == before
    result = _service(pg).check(raw_bundle(), world_id=WORLD_ID)
    assert result.classification == "MISMATCH"
    checks = {check.check: check for check in result.checks}
    assert checks["source_identity"].outcome == "match"
    assert checks["graph_payload"].outcome == "match"
    assert checks["source_history"].outcome == "match"
    assert checks["contribution_history"].outcome == "diverged"
    assert tampered_id in checks["contribution_history"].detail
    assert checks["identity_history"].outcome == "match"
    assert checks["evidence_identity"].outcome == "match"
    assert _counts(pg) == before


def test_postgres_coherent_graph_payload_drift_is_mismatch(pg) -> None:
    _adopt(pg)
    before = _counts(pg)
    new_hash = _coherent_graph_payload_tamper(pg)
    result = _service(pg).check(raw_bundle(), world_id=WORLD_ID)
    assert result.classification == "MISMATCH"
    checks = {check.check: check for check in result.checks}
    assert checks["source_identity"].outcome == "match"
    assert checks["graph_payload"].outcome == "diverged"
    assert new_hash in checks["graph_payload"].detail
    assert checks["evidence_identity"].outcome == "match"
    assert _counts(pg) == before


def _coherent_receipt_bundle_identity_tamper(pg) -> str:
    """Rewrite the receipt's bundle identity pin the way a coherent future
    writer would: identity column, payload, and fingerprint all agree on the
    forged sha, so read-time verification passes and only the correspondence
    check itself can catch the drift."""
    receipt = pg.existing_world_adoptions.get_for_world(WORLD_ID)
    assert receipt is not None
    forged_sha = "0" * 64
    forged = receipt.model_copy(update={"bundle_sha256": forged_sha})
    with pg.database.connect() as conn:
        conn.execute(
            """
            UPDATE dungeonmind.existing_world_adoptions
            SET bundle_sha256 = %s, payload = %s, record_fingerprint = %s
            WHERE world_id = %s
            """,
            (
                forged_sha,
                Jsonb(forged.model_dump(mode="json")),
                model_fingerprint(forged),
                WORLD_ID,
            ),
        )
        conn.commit()
    return forged_sha


def test_postgres_dangling_contribution_fails_closed(pg) -> None:
    _adopt(pg)
    before = _counts(pg)
    with pg.database.connect() as conn:
        conn.execute(
            """
            DELETE FROM dungeonmind.graph_contributions
            WHERE world_id = %s AND contribution_id = %s
            """,
            (WORLD_ID, WITNESS_CONTRIBUTION_ID),
        )
        conn.commit()
    with pytest.raises(PersistenceIntegrityError) as exc:
        _service(pg).check(raw_bundle(), world_id=WORLD_ID)
    assert exc.value.details["reason"] == "adopted_contribution_missing"
    assert exc.value.details["adopted_contribution_count"] == before["contributions"]
    assert exc.value.details["durable_contribution_count"] == before["contributions"] - 1
    assert _counts(pg) == {**before, "contributions": before["contributions"] - 1}


def test_postgres_dangling_source_revision_fails_closed(pg) -> None:
    _adopt(pg)
    before = _counts(pg)
    target = parse_sealed_bundle().source_revisions[0].source_revision_id
    with pg.database.connect() as conn:
        conn.execute(
            "DELETE FROM dungeonmind.source_revisions WHERE source_revision_id = %s",
            (target,),
        )
        conn.commit()
    with pytest.raises(PersistenceIntegrityError) as exc:
        _service(pg).check(raw_bundle(), world_id=WORLD_ID)
    assert exc.value.details["reason"] == "adopted_source_revision_missing"
    assert exc.value.details["source_revision_id"] == target
    assert _counts(pg) == {**before, "revisions_source": before["revisions_source"] - 1}


def test_postgres_corrupted_graph_payload_fails_closed(pg) -> None:
    _adopt(pg)
    before = _counts(pg)
    with pg.database.connect() as conn:
        conn.execute(
            """
            UPDATE dungeonmind.graph_revisions
            SET graph_payload = jsonb_set(
                graph_payload, '{objects,0,label}', '"Tampered Wizard College"'
            )
            WHERE world_id = %s AND revision_id = %s
            """,
            (WORLD_ID, PUBLISHED_REVISION_ID),
        )
        conn.commit()
    with pytest.raises(PersistenceIntegrityError):
        _service(pg).check(raw_bundle(), world_id=WORLD_ID)
    assert _counts(pg) == before


def test_postgres_missing_receipt_is_not_adopted(pg) -> None:
    assert _counts(pg) == _zero_counts()
    result = _service(pg).check(raw_bundle(), world_id=WORLD_ID)
    assert result.classification == "NOT_ADOPTED"
    assert result.world_id == WORLD_ID
    assert result.observed_source_revision == SOURCE_WORLD_REVISION_ID
    assert result.adopted_source_revision is None
    assert result.adoption_id is None
    assert result.adopted_revision is None
    assert result.checks == []
    assert _counts(pg) == _zero_counts()


def test_postgres_same_revision_changed_adoption_id_is_stale(pg) -> None:
    """Revision-compatible is not corresponding: the exact adoption identity
    must match the receipt, or the snapshot is a different snapshot."""
    _adopt(pg)
    before = _counts(pg)
    result = _service(pg).check(_changed_adoption_id_snapshot_bytes(), world_id=WORLD_ID)
    assert result.classification == "STALE"
    assert result.observed_source_revision == SOURCE_WORLD_REVISION_ID
    assert result.adopted_source_revision == SOURCE_WORLD_REVISION_ID
    assert result.adoption_id == ADOPTION_ID
    checks = {check.check: check for check in result.checks}
    assert checks["source_identity"].outcome == "diverged"
    assert ADOPTION_ID in checks["source_identity"].detail
    assert f"{ADOPTION_ID}-tampered" in checks["source_identity"].detail
    for name in CORRESPONDENCE_CHECK_ORDER[1:]:
        assert checks[name].outcome == "not_evaluated"
    assert _counts(pg) == before


def test_postgres_receipt_bundle_identity_drift_is_stale_never_corresponding(pg) -> None:
    """A coherently rewritten receipt bundle pin makes the exact adopted
    bundle unprovable: the checker must refuse CORRESPONDING."""
    _adopt(pg)
    before = _counts(pg)
    forged_sha = _coherent_receipt_bundle_identity_tamper(pg)
    result = _service(pg).check(raw_bundle(), world_id=WORLD_ID)
    assert result.classification == "STALE"
    checks = {check.check: check for check in result.checks}
    assert checks["source_identity"].outcome == "diverged"
    assert forged_sha in checks["source_identity"].detail
    for name in CORRESPONDENCE_CHECK_ORDER[1:]:
        assert checks[name].outcome == "not_evaluated"
    assert _counts(pg) == before


def test_postgres_deleted_contribution_fails_closed_before_stale(pg) -> None:
    """adopt A → delete adopted history → present valid B must raise, never STALE."""
    _adopt(pg)
    before = _counts(pg)
    with pg.database.connect() as conn:
        conn.execute(
            """
            DELETE FROM dungeonmind.graph_contributions
            WHERE world_id = %s AND contribution_id = %s
            """,
            (WORLD_ID, WITNESS_CONTRIBUTION_ID),
        )
        conn.commit()
    with pytest.raises(PersistenceIntegrityError) as exc:
        _service(pg).check(_changed_source_snapshot_bytes(), world_id=WORLD_ID)
    assert exc.value.details["reason"] == "adopted_contribution_missing"
    assert _counts(pg) == {**before, "contributions": before["contributions"] - 1}


def test_postgres_incoherent_contribution_tamper_fails_closed_before_stale(pg) -> None:
    """Payload rewritten without its fingerprint: the history read itself
    fails closed, so a stale snapshot can never mask invalid adopted bytes."""
    _adopt(pg)
    before = _counts(pg)
    stored = pg.contributions.get(WORLD_ID, WITNESS_CONTRIBUTION_ID)
    assert stored is not None
    mutated = stored.model_copy(update={"extraction_profile": "tampered-postgres-profile"})
    with pg.database.connect() as conn:
        conn.execute(
            """
            UPDATE dungeonmind.graph_contributions
            SET payload = %s
            WHERE world_id = %s AND contribution_id = %s
            """,
            (Jsonb(mutated.model_dump(mode="json")), WORLD_ID, WITNESS_CONTRIBUTION_ID),
        )
        conn.commit()
    with pytest.raises(PersistenceIntegrityError):
        _service(pg).check(_changed_source_snapshot_bytes(), world_id=WORLD_ID)
    assert _counts(pg) == before


def test_postgres_deleted_evidence_referenced_source_revision_fails_closed_before_stale(
    pg,
) -> None:
    _adopt(pg)
    before = _counts(pg)
    target = _evidence_referenced_source_revision_id()
    with pg.database.connect() as conn:
        conn.execute(
            "DELETE FROM dungeonmind.source_revisions WHERE source_revision_id = %s",
            (target,),
        )
        conn.commit()
    with pytest.raises(PersistenceIntegrityError) as exc:
        _service(pg).check(_changed_source_snapshot_bytes(), world_id=WORLD_ID)
    assert exc.value.details["reason"] == "adopted_source_revision_missing"
    assert exc.value.details["source_revision_id"] == target
    assert _counts(pg) == {**before, "revisions_source": before["revisions_source"] - 1}
