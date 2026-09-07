"""Unit proofs for Eldyrwild World authority preflight.

These tests adopt the exact sealed bundle into in-memory repositories so the
membership preflight recomputes the canonical digest over real durable records.
Tamper tests mutate one durable record's payload (not its id or the receipt) to
prove same-cardinality substitution fails closed.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from dungeonmind.application.existing_world_adoption import adopt_existing_world
from dungeonmind.application.world_authority_recovery import (
    ELDYRWILD_D_A,
    ELDYRWILD_D_B,
    ELDYRWILD_PROJECTION_OBJECT_COUNT,
    ELDYRWILD_SCHEMA_REVISION,
    REASON_INTEGRITY_FAILURE,
    REASON_STALE_RECOVERY_POINT,
    REASON_WORLD_MISSING,
    STATUS_NOT_READY,
    STATUS_READY,
    ProjectionWitness,
    _load_sealed_manifest,
    check_world_authority,
)
from dungeonmind.contracts.graph import (
    StoredGraphRevision,
    WorldGraphHead,
    WorldGraphRevision,
)
from dungeonmind.infrastructure.memory import (
    InMemoryContributionRepository,
    InMemoryExistingWorldAdoptionRepository,
    InMemoryIdentityDecisionRepository,
    InMemorySourceRepository,
    InMemoryWorldGraphRepository,
)
from tests.unit.test_eldyrwild_existing_world_adoption_bundle_v2 import (
    NOW,
    eldyrwild_graph_reader,
    raw_bundle,
)

MANIFEST = _load_sealed_manifest()
WHEN = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)

# The two post-adoption contributions that move Eldyrwild from D_A to D_B.
# They carry no correction links, so appending sealed-derived copies with fresh
# ids reproduces the D_B contribution count (95) in the in-memory boundary.
D_B_EXTRA_CONTRIBUTION_IDS = (
    "contrib:fd9fd20f4066584eca01f3b52d1943fb",
    "contribution:1daea04b20b3e1f3",
)

# Authentic content-addressed envelope material for the accepted revisions,
# captured from the restored authority. ``compute_revision_id`` over these
# fields must reproduce the literal revision IDs, so the preflight's
# revision-identity recompute passes only for the exact accepted envelopes.
D_A_ENVELOPE = {
    "world_id": "eldyrwild",
    "parent_revision_id": None,
    "operation_ids": ["adoption:eldyrwild:dungeonmind-v6:rev:0c644e56b45bcaac709012206e3e41c2"],
    "graph_schema": "dm_union_graph_v6",
    "graph_payload_sha256": "047214f19e3a2d22b1cf3e0596283844ef34853dd2e4f38d341c6b212ae320ef",
}
D_B_ENVELOPE = {
    "world_id": "eldyrwild",
    "parent_revision_id": ELDYRWILD_D_A,
    "operation_ids": ["reviewop:0f0916a8b045f34fc7bbe1cf3bc891c9"],
    "graph_schema": "dm_union_graph_v6",
    "graph_payload_sha256": "c58a086f829e446e5fc2762c9453ba452106556e50f8bece89b3a4bdc93bf613",
}


def _stored_revision(revision_id: str, envelope: dict) -> StoredGraphRevision:
    return StoredGraphRevision(
        revision=WorldGraphRevision(
            revision_id=revision_id,
            created_at=WHEN,
            world_id=envelope["world_id"],
            parent_revision_id=envelope["parent_revision_id"],
            operation_ids=list(envelope["operation_ids"]),
            graph_schema=envelope["graph_schema"],
            graph_payload_sha256=envelope["graph_payload_sha256"],
        ),
        graph_payload={},
    )


def _set_head(
    graph: InMemoryWorldGraphRepository, head_revision_id: str, d_b_envelope: dict
) -> None:
    """Install an exact head + lineage directly (test-only authority fixture).

    The adoption seam already stored the real D_A revision; preserve it so the
    receipt↔revision consistency and identity recompute checks keep passing.
    Only add a distinct head revision when the target head is not D_A.
    """
    if head_revision_id == ELDYRWILD_D_B:
        graph._revisions[("eldyrwild", ELDYRWILD_D_B)] = _stored_revision(
            ELDYRWILD_D_B, d_b_envelope
        )
    graph._heads["eldyrwild"] = WorldGraphHead(
        world_id="eldyrwild", head_revision_id=head_revision_id, updated_at=WHEN
    )


class _Harness:
    """Adopted Eldyrwild world in in-memory repos, head driven to D_B."""

    def __init__(self, *, head: str = ELDYRWILD_D_B, d_b_envelope: dict | None = None):
        self.world_graph = InMemoryWorldGraphRepository()
        self.sources = InMemorySourceRepository()
        self.contributions = InMemoryContributionRepository()
        self.identity = InMemoryIdentityDecisionRepository()
        self.adoptions = InMemoryExistingWorldAdoptionRepository(
            self.world_graph, self.sources, self.contributions, self.identity
        )
        self.receipt = adopt_existing_world(
            raw_bundle(),
            adopted_at=NOW,
            adoption_repository=self.adoptions,
            graph_reader=eldyrwild_graph_reader(),
        )
        if head == ELDYRWILD_D_B:
            self._add_d_b_contributions()
        _set_head(self.world_graph, head, d_b_envelope or D_B_ENVELOPE)

    def _add_d_b_contributions(self) -> None:
        template = self.contributions.get("eldyrwild", MANIFEST.contribution_ids[0])
        assert template is not None
        for new_id in D_B_EXTRA_CONTRIBUTION_IDS:
            self.contributions.append(template.model_copy(update={"contribution_id": new_id}))

    def check(self, **overrides):
        kwargs = {
            "world_graph": self.world_graph,
            "adoptions": self.adoptions,
            "sources": self.sources,
            "contributions": self.contributions,
            "identity_decisions": self.identity,
            "schema_revision": ELDYRWILD_SCHEMA_REVISION,
            "membership_manifest": MANIFEST,
            "project": _project,
        }
        kwargs.update(overrides)
        return check_world_authority(**kwargs)


def _project() -> ProjectionWitness:
    return ProjectionWitness(ELDYRWILD_D_B, ELDYRWILD_D_B, ELDYRWILD_PROJECTION_OBJECT_COUNT)


def test_missing_world_is_not_ready() -> None:
    report = check_world_authority(
        world_graph=InMemoryWorldGraphRepository(),
        adoptions=InMemoryExistingWorldAdoptionRepository(
            InMemoryWorldGraphRepository(),
            InMemorySourceRepository(),
            InMemoryContributionRepository(),
            InMemoryIdentityDecisionRepository(),
        ),
        sources=InMemorySourceRepository(),
        contributions=InMemoryContributionRepository(),
        identity_decisions=InMemoryIdentityDecisionRepository(),
        project=_project,
    )
    assert report.status == STATUS_NOT_READY
    assert report.reason == REASON_WORLD_MISSING
    assert report.ready is False


def test_d_a_head_is_stale_when_expected_head_is_d_b() -> None:
    harness = _Harness(head=ELDYRWILD_D_A)
    report = harness.check()
    assert report.status == STATUS_NOT_READY
    assert report.reason == REASON_STALE_RECOVERY_POINT
    assert report.current_head == ELDYRWILD_D_A
    assert report.ready is False


def test_exact_d_b_lineage_is_ready() -> None:
    report = _Harness().check()
    assert report.status == STATUS_READY
    assert report.reason is None
    assert report.current_head == ELDYRWILD_D_B
    assert report.parent_revision_id == ELDYRWILD_D_A
    assert report.adopted_revision_id == ELDYRWILD_D_A
    assert report.schema_revision == ELDYRWILD_SCHEMA_REVISION
    assert report.projection is not None
    assert report.projection.revision_id == ELDYRWILD_D_B
    assert report.projection.object_count == ELDYRWILD_PROJECTION_OBJECT_COUNT


def test_membership_tamper_same_cardinality_fails_closed() -> None:
    """Mutating one durable contribution payload (same id, same count, receipt
    untouched) must flip READY to NOT_READY via the recomputed digest."""
    harness = _Harness()
    baseline = harness.check()
    assert baseline.status == STATUS_READY

    target_id = MANIFEST.contribution_ids[0]
    stored = harness.contributions.get("eldyrwild", target_id)
    assert stored is not None
    mutated = stored.model_copy(update={"extraction_profile": "tampered-profile"})
    harness.contributions._items[("eldyrwild", target_id)] = mutated

    report = harness.check()
    assert report.status == STATUS_NOT_READY
    assert report.reason == REASON_INTEGRITY_FAILURE
    assert any("recomputed adopted-membership digest" in d for d in report.diagnostics)


def test_source_revision_tamper_same_cardinality_fails_closed() -> None:
    harness = _Harness()
    target_id = MANIFEST.source_revision_ids[0]
    stored = harness.sources.get_revision(target_id)
    assert stored is not None
    mutated = stored.model_copy(update={"content_sha256": "1" * 64})
    harness.sources._revisions[target_id] = mutated

    report = harness.check()
    assert report.status == STATUS_NOT_READY
    assert report.reason == REASON_INTEGRITY_FAILURE
    assert any("recomputed adopted-membership digest" in d for d in report.diagnostics)


def test_missing_adopted_member_fails_closed() -> None:
    harness = _Harness()
    target_id = MANIFEST.contribution_ids[0]
    del harness.contributions._items[("eldyrwild", target_id)]

    report = harness.check()
    assert report.status == STATUS_NOT_READY
    assert report.reason == REASON_INTEGRITY_FAILURE
    assert any("is missing" in d for d in report.diagnostics)


def test_wrong_parentage_fails_closed() -> None:
    harness = _Harness(d_b_envelope={**D_B_ENVELOPE, "parent_revision_id": "rev:not-da"})
    report = harness.check()
    assert report.status == STATUS_NOT_READY
    assert report.reason == REASON_INTEGRITY_FAILURE
    assert any("parent(" in d for d in report.diagnostics)


def test_coherent_d_b_identity_rewrite_fails_closed() -> None:
    """A coherent D_B rewrite that keeps the literal revision id but changes the
    graph payload hash must fail the content-addressed identity recompute, even
    though the row is internally consistent and cardinality is unchanged."""
    rewritten = {**D_B_ENVELOPE, "graph_payload_sha256": "9" * 64}
    harness = _Harness(d_b_envelope=rewritten)
    report = harness.check()
    assert report.status == STATUS_NOT_READY
    assert report.reason == REASON_INTEGRITY_FAILURE
    assert any("head revision identity recompute" in d for d in report.diagnostics)


def test_omitting_project_is_rejected() -> None:
    """``project`` is required: omitting it must not be able to yield READY."""
    harness = _Harness()
    with pytest.raises(TypeError):
        check_world_authority(
            world_graph=harness.world_graph,
            adoptions=harness.adoptions,
            sources=harness.sources,
            contributions=harness.contributions,
            identity_decisions=harness.identity,
            schema_revision=ELDYRWILD_SCHEMA_REVISION,
            membership_manifest=MANIFEST,
        )


def test_omitting_manifest_still_verifies_membership() -> None:
    """Omitting ``membership_manifest`` auto-loads the sealed manifest, so a
    same-cardinality tamper is still caught (the plane cannot be skipped)."""
    harness = _Harness()
    target_id = MANIFEST.contribution_ids[0]
    stored = harness.contributions.get("eldyrwild", target_id)
    assert stored is not None
    harness.contributions._items[("eldyrwild", target_id)] = stored.model_copy(
        update={"extraction_profile": "tampered-profile"}
    )
    report = harness.check(membership_manifest=None)
    assert report.status == STATUS_NOT_READY
    assert report.reason == REASON_INTEGRITY_FAILURE
    assert any("recomputed adopted-membership digest" in d for d in report.diagnostics)


def test_incomplete_projection_cardinality_fails_closed() -> None:
    """A severely incomplete projection (wrong object count) must not be READY."""

    def _short_projection() -> ProjectionWitness:
        return ProjectionWitness(ELDYRWILD_D_B, ELDYRWILD_D_B, 80)

    report = _Harness().check(project=_short_projection)
    assert report.status == STATUS_NOT_READY
    assert report.reason == REASON_INTEGRITY_FAILURE
    assert any("projection object count" in d for d in report.diagnostics)


def test_restore_refuses_wrong_dump_digest(tmp_path) -> None:
    dump = tmp_path / "fake.dump"
    dump.write_bytes(b"not-the-accepted-eldyrwild-dump")
    script = (
        Path(__file__).resolve().parents[2] / "scripts" / "eldyrwild_world_authority_recovery.py"
    )
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "restore",
            "--database-url",
            "postgresql://dungeonmind@127.0.0.1:1/unused",
            "--dump-path",
            str(dump),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "digest mismatch" in result.stderr
    assert "refusing to restore" in result.stderr


def test_cli_explicit_dsn_is_not_overwritten_by_environment(tmp_path, monkeypatch) -> None:
    """The supplied --database-url must reach the command, never the env default.

    Regression guard for the argparse double-registration bug: a DSN given for
    the subcommand must not be replaced by
    DUNGEONMIND_WORLD_GRAPH_AUTHORITY_DATABASE_URL.
    """
    monkeypatch.setenv(
        "DUNGEONMIND_WORLD_GRAPH_AUTHORITY_DATABASE_URL",
        "postgresql://dungeonmind@127.0.0.1:1/env-should-not-win",
    )
    dump = tmp_path / "fake.dump"
    dump.write_bytes(b"not-the-accepted-eldyrwild-dump")
    script = (
        Path(__file__).resolve().parents[2] / "scripts" / "eldyrwild_world_authority_recovery.py"
    )
    explicit = "postgresql://dungeonmind@127.0.0.1:2/explicit-witness"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "restore",
            "--database-url",
            explicit,
            "--dump-path",
            str(dump),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    # Digest check runs before any DB work; reaching it proves the explicit DSN
    # was accepted as the target (a missing/emptied target errors earlier).
    assert result.returncode == 2
    assert "digest mismatch" in result.stderr
    assert "required" not in result.stderr
