"""Unit proofs for Eldyrwild World authority preflight."""

from __future__ import annotations

from dataclasses import dataclass

from dungeonmind.application.world_authority_recovery import (
    ELDYRWILD_D_A,
    ELDYRWILD_D_B,
    ELDYRWILD_D_B_CONTRIBUTIONS,
    ELDYRWILD_SCHEMA_REVISION,
    REASON_INTEGRITY_FAILURE,
    REASON_STALE_RECOVERY_POINT,
    REASON_WORLD_MISSING,
    STATUS_NOT_READY,
    STATUS_READY,
    ProjectionWitness,
    RecoveryExpectation,
    check_world_authority,
)


@dataclass
class _Revision:
    revision_id: str
    parent_revision_id: str | None
    world_id: str = "eldyrwild"


@dataclass
class _Stored:
    revision: _Revision


@dataclass
class _Head:
    world_id: str
    head_revision_id: str


@dataclass
class _Receipt:
    schema_version: str = "dm_existing_world_adoption_receipt_v4"
    published_revision_id: str = ELDYRWILD_D_A
    bundle_sha256: str = "90574dfc4101e4198c7fd96478d6f49e65aa534d0aa91fa41a9a17da9d49695f"
    membership_sha256: str = "538195e399158bfb4fafce01f9c5af3c63e2137f70694fdead7a26e5800e0890"
    effective_membership_sha256: str | None = (
        "16d3161d270691460ccbf6d183055ad9f29f00bdbecf5c26dfe0189da2b9914e"
    )
    source_artifact_count: int = 83


@dataclass
class _Artifact:
    source_artifact_id: str


class _WorldGraph:
    def __init__(self, head: _Head | None, revisions: dict[str, _Stored]) -> None:
        self.head = head
        self.revisions = revisions

    def get_head(self, world_id: str) -> _Head | None:
        if self.head is None or self.head.world_id != world_id:
            return None
        return self.head

    def get_revision(self, world_id: str, revision_id: str) -> _Stored | None:
        del world_id
        return self.revisions.get(revision_id)


class _Adoptions:
    def __init__(self, receipt: _Receipt | None) -> None:
        self.receipt = receipt

    def get_for_world(self, world_id: str) -> _Receipt | None:
        del world_id
        return self.receipt


class _Sources:
    def __init__(self, artifact_count: int, revision_count: int) -> None:
        self.artifact_count = artifact_count
        self.revision_count = revision_count

    def list_artifacts_for_world(self, world_id: str) -> list[_Artifact]:
        del world_id
        return [_Artifact(f"artifact:{index}") for index in range(self.artifact_count)]

    def list_revisions(self, source_artifact_id: str) -> list[object]:
        index = int(source_artifact_id.rsplit(":", 1)[1])
        if index < self.revision_count:
            return [object()]
        return []


class _Rows:
    def __init__(self, count: int) -> None:
        self.count = count

    def list_for_world(self, world_id: str) -> list[object]:
        del world_id
        return [object() for _ in range(self.count)]


def _d_b_graph() -> _WorldGraph:
    return _WorldGraph(
        head=_Head("eldyrwild", ELDYRWILD_D_B),
        revisions={
            ELDYRWILD_D_A: _Stored(_Revision(ELDYRWILD_D_A, None)),
            ELDYRWILD_D_B: _Stored(_Revision(ELDYRWILD_D_B, ELDYRWILD_D_A)),
        },
    )


def _d_a_graph() -> _WorldGraph:
    return _WorldGraph(
        head=_Head("eldyrwild", ELDYRWILD_D_A),
        revisions={ELDYRWILD_D_A: _Stored(_Revision(ELDYRWILD_D_A, None))},
    )


def _project() -> ProjectionWitness:
    return ProjectionWitness(ELDYRWILD_D_B, ELDYRWILD_D_B, 80)


def test_missing_world_is_not_ready() -> None:
    report = check_world_authority(
        world_graph=_WorldGraph(None, {}),
        adoptions=_Adoptions(None),
        sources=_Sources(0, 0),
        contributions=_Rows(0),
        identity_decisions=_Rows(0),
    )
    assert report.status == STATUS_NOT_READY
    assert report.reason == REASON_WORLD_MISSING
    assert report.ready is False


def test_d_a_head_is_stale_when_expected_head_is_d_b() -> None:
    report = check_world_authority(
        world_graph=_d_a_graph(),
        adoptions=_Adoptions(_Receipt()),
        sources=_Sources(83, 83),
        contributions=_Rows(93),
        identity_decisions=_Rows(13),
        project=_project,
    )
    assert report.status == STATUS_NOT_READY
    assert report.reason == REASON_STALE_RECOVERY_POINT
    assert report.current_head == ELDYRWILD_D_A
    assert report.ready is False


def test_membership_mismatch_fails_closed() -> None:
    receipt = _Receipt(membership_sha256="0" * 64)
    report = check_world_authority(
        world_graph=_d_b_graph(),
        adoptions=_Adoptions(receipt),
        sources=_Sources(83, 83),
        contributions=_Rows(ELDYRWILD_D_B_CONTRIBUTIONS),
        identity_decisions=_Rows(13),
        project=_project,
    )
    assert report.status == STATUS_NOT_READY
    assert report.reason == REASON_INTEGRITY_FAILURE
    assert any("M0" in item for item in report.diagnostics)


def test_wrong_parentage_fails_closed() -> None:
    graph = _WorldGraph(
        head=_Head("eldyrwild", ELDYRWILD_D_B),
        revisions={
            ELDYRWILD_D_A: _Stored(_Revision(ELDYRWILD_D_A, None)),
            ELDYRWILD_D_B: _Stored(_Revision(ELDYRWILD_D_B, "rev:not-da")),
        },
    )
    report = check_world_authority(
        world_graph=graph,
        adoptions=_Adoptions(_Receipt()),
        sources=_Sources(83, 83),
        contributions=_Rows(ELDYRWILD_D_B_CONTRIBUTIONS),
        identity_decisions=_Rows(13),
        project=_project,
    )
    assert report.status == STATUS_NOT_READY
    assert report.reason == REASON_INTEGRITY_FAILURE
    assert any("parent(" in item for item in report.diagnostics)


def test_exact_d_b_with_dump_v3_receipt_is_ready() -> None:
    receipt = _Receipt(
        schema_version="dm_existing_world_adoption_receipt_v3",
        membership_sha256="16d3161d270691460ccbf6d183055ad9f29f00bdbecf5c26dfe0189da2b9914e",
        effective_membership_sha256=None,
    )
    report = check_world_authority(
        world_graph=_d_b_graph(),
        adoptions=_Adoptions(receipt),
        sources=_Sources(83, 83),
        contributions=_Rows(ELDYRWILD_D_B_CONTRIBUTIONS),
        identity_decisions=_Rows(13),
        project=_project,
        schema_revision=ELDYRWILD_SCHEMA_REVISION,
    )
    assert report.status == STATUS_READY
    assert report.current_head == ELDYRWILD_D_B
    assert report.receipt_schema == "dm_existing_world_adoption_receipt_v3"


def test_exact_d_b_lineage_is_ready() -> None:
    report = check_world_authority(
        world_graph=_d_b_graph(),
        adoptions=_Adoptions(_Receipt()),
        sources=_Sources(83, 83),
        contributions=_Rows(ELDYRWILD_D_B_CONTRIBUTIONS),
        identity_decisions=_Rows(13),
        expected=RecoveryExpectation(),
        project=_project,
        schema_revision="0007_reviewed_world_init",
    )
    assert report.status == STATUS_READY
    assert report.reason is None
    assert report.current_head == ELDYRWILD_D_B
    assert report.parent_revision_id == ELDYRWILD_D_A
    assert report.adopted_revision_id == ELDYRWILD_D_A
    assert report.schema_revision == ELDYRWILD_SCHEMA_REVISION
    assert report.projection is not None
    assert report.projection.revision_id == ELDYRWILD_D_B


def test_restore_refuses_wrong_dump_digest(tmp_path) -> None:
    import subprocess
    import sys
    from pathlib import Path

    dump = tmp_path / "fake.dump"
    dump.write_bytes(b"not-the-accepted-eldyrwild-dump")
    script = (
        Path(__file__).resolve().parents[2] / "scripts" / "eldyrwild_world_authority_recovery.py"
    )
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--database-url",
            "postgresql://dungeonmind@127.0.0.1:1/unused",
            "restore",
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
