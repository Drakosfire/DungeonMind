"""In-memory expected-parent CAS for one governed native publication."""

from __future__ import annotations

import json
import re
import subprocess
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest

from dungeonmind.application.vnext.authority import revision_from_command
from dungeonmind.application.vnext.builder import build_parsed_knowledge_revision
from dungeonmind.application.vnext.errors import KnowledgeStaleParentRevisionError
from dungeonmind.application.vnext.materialization import (
    NATIVE_VNEXT_GRAPH_SCHEMA,
    decode_native_graph_payload,
    encode_native_graph_payload,
)
from dungeonmind.application.vnext.publication import publish_governed_materialization
from dungeonmind.application.vnext.records import StoredKnowledgeRevision
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext.domain import DomainContractRef, Entity
from dungeonmind.contracts.vnext.knowledge import (
    MigrationOriginRef,
    PublishKnowledgeRevisionCommand,
)
from dungeonmind.domain.canonical import canonical_json
from dungeonmind.domain.errors import (
    ImmutableRevisionConflictError,
    PersistenceIntegrityError,
    PersistenceUnavailableError,
)
from dungeonmind.infrastructure.memory.vnext_knowledge import InMemoryKnowledgeRevisionRepository
from tests.unit.test_vnext_governed_materialization import (
    _accepted,
    _bob_item,
    _call,
    _contribution,
    _evidence,
    _lab_digests,
    _literal,
    _parent,
)

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 21, 13, 0, tzinfo=UTC)
REPO_ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTATION_BASE = "9f006bf77d72faabee8a3eef359b89a3d537b0c1"
FROZEN_V0_AGGREGATE = "fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea"
SPACE = "space:lab"
V52_SOURCES = (
    "src/dungeonmind/application/vnext/publication.py",
    "src/dungeonmind/application/vnext/revision_ids.py",
    "src/dungeonmind/application/vnext/authority.py",
    "src/dungeonmind/application/vnext/errors.py",
    "src/dungeonmind/application/vnext/records.py",
    "src/dungeonmind/application/vnext/ports.py",
    "src/dungeonmind/infrastructure/memory/vnext_knowledge.py",
)
BANNED_VOCABULARY = re.compile(
    r"\b(world_id|GM|PLAYER|campaign_id|ContributionReview|"
    r"FinalizedReviewPublication|review_materialization)\b"
)


def _origin() -> MigrationOriginRef:
    return MigrationOriginRef(
        source_system="legacy",
        source_root_id="root:1",
        source_revision_id="rev:legacy",
        source_payload_sha256="11" * 32,
        migration_manifest_sha256="22" * 32,
    )


def _refs() -> tuple[DomainContractRef, SemanticProfileRef]:
    contract_digest, profile_digest = _lab_digests()
    return (
        DomainContractRef(
            domain_id="lab.domain",
            domain_revision="1",
            descriptor_sha256=contract_digest,
        ),
        SemanticProfileRef(
            profile_id="lab.profile",
            profile_revision="1",
            descriptor_sha256=profile_digest,
        ),
    )


def _alice_payload() -> dict:
    evidence = _evidence()
    assertion = _literal("asrt:alice-title", "ent:alice", "Alice")
    return encode_native_graph_payload(
        entities={"ent:alice": Entity(entity_id="ent:alice")},
        assertions={assertion.assertion_id: assertion},
        aliases={},
        evidence={evidence.evidence_ref_id: evidence},
    )


def genesis_command(
    *,
    payload: dict | None = None,
    created_at: datetime = NOW,
    origin: MigrationOriginRef | None = None,
    operation_ids: list[str] | None = None,
    parent_revision_id: str | None = None,
    expected_parent_revision_id: str | None = None,
) -> PublishKnowledgeRevisionCommand:
    contract, profile = _refs()
    return PublishKnowledgeRevisionCommand(
        space_id=SPACE,
        parent_revision_id=parent_revision_id,
        expected_parent_revision_id=expected_parent_revision_id,
        operation_ids=operation_ids or ["op:genesis"],
        graph_schema=NATIVE_VNEXT_GRAPH_SCHEMA,
        graph_payload=payload or _alice_payload(),
        domain_contract_ref=contract,
        semantic_profile_ref=profile,
        migration_origin_ref=origin,
        created_at=created_at,
    )


def _parsed_parent(repo: InMemoryKnowledgeRevisionRepository):
    stored = repo.get_revision(SPACE, repo.get_head(SPACE).head_revision_id)  # type: ignore[union-attr]
    assert stored is not None
    return build_parsed_knowledge_revision(
        revision=stored.revision,
        decoded_content=decode_native_graph_payload(stored.graph_payload),
    )


def _materialize_bob(repo: InMemoryKnowledgeRevisionRepository):
    parent = _parsed_parent(repo)
    contribution = _contribution(parent, [_bob_item()])
    dispositions = _accepted("i1")
    return (
        contribution,
        dispositions,
        _call(
            parent=parent,
            contribution=contribution,
            dispositions=dispositions,
        ),
    )


def test_governed_materialization_publishes_exact_revision() -> None:
    repo = InMemoryKnowledgeRevisionRepository()
    origin = _origin()
    genesis = repo.publish_revision(genesis_command(origin=origin))
    contribution, dispositions, materialization = _materialize_bob(repo)
    before_contribution = contribution.model_dump(mode="json")
    before_dispositions = [item.model_dump(mode="json") for item in dispositions]

    published = publish_governed_materialization(materialization, repository=repo)

    assert published.graph_payload_sha256 == materialization.graph_payload_sha256
    assert published.revision.graph_payload_sha256 == materialization.graph_payload_sha256
    assert published.revision.domain_contract_ref == materialization.command.domain_contract_ref
    assert published.revision.semantic_profile_ref == materialization.command.semantic_profile_ref
    assert published.revision.migration_origin_ref == origin
    assert published.revision.status == "published"
    head = repo.get_head(SPACE)
    assert head is not None
    assert head.head_revision_id == published.revision.revision_id
    events = repo.head_events(SPACE)
    assert len(events) == 2
    assert events[-1].event_kind == "publish"
    assert events[-1].previous_revision_id == genesis.revision.revision_id
    assert events[-1].target_revision_id == published.revision.revision_id
    mutated = published.graph_payload
    mutated["entities"] = []
    stored = repo.get_revision(SPACE, published.revision.revision_id)
    assert stored is not None
    assert stored.graph_payload["entities"]
    assert contribution.model_dump(mode="json") == before_contribution
    assert [item.model_dump(mode="json") for item in dispositions] == before_dispositions


def test_stale_expected_parent_mutates_nothing() -> None:
    repo = InMemoryKnowledgeRevisionRepository()
    genesis = repo.publish_revision(genesis_command())
    stale = genesis_command(
        parent_revision_id="rev:missing",
        expected_parent_revision_id="rev:missing",
        operation_ids=["op:stale"],
        payload={"entities": [], "assertions": [], "aliases": [], "evidence": []},
    )
    attempted = revision_from_command(stale).revision_id
    with pytest.raises(KnowledgeStaleParentRevisionError) as raised:
        repo.publish_revision(stale)
    assert raised.value.details == {
        "space_id": SPACE,
        "expected_parent_revision_id": "rev:missing",
        "actual_head_revision_id": genesis.revision.revision_id,
    }
    assert "world_id" not in raised.value.details
    assert repo.get_head(SPACE).head_revision_id == genesis.revision.revision_id  # type: ignore[union-attr]
    assert repo.get_revision(SPACE, attempted) is None
    assert len(repo.head_events(SPACE)) == 1


def test_genesis_and_absent_head_rules() -> None:
    repo = InMemoryKnowledgeRevisionRepository()
    missing = genesis_command(
        parent_revision_id="rev:absent",
        expected_parent_revision_id="rev:absent",
        operation_ids=["op:absent"],
    )
    with pytest.raises(KnowledgeStaleParentRevisionError) as absent:
        repo.publish_revision(missing)
    assert absent.value.actual_head_revision_id is None
    assert repo.get_head(SPACE) is None
    assert repo.head_events(SPACE) == ()

    genesis = repo.publish_revision(genesis_command())
    again = genesis_command(
        operation_ids=["op:second-genesis"],
        payload={"entities": [], "assertions": [], "aliases": [], "evidence": []},
    )
    with pytest.raises(KnowledgeStaleParentRevisionError) as existing:
        repo.publish_revision(again)
    assert existing.value.expected_parent_revision_id is None
    assert existing.value.actual_head_revision_id == genesis.revision.revision_id
    assert repo.get_revision(SPACE, revision_from_command(again).revision_id) is None
    assert len(repo.head_events(SPACE)) == 1


def test_same_parent_writers_one_winner() -> None:
    repo = InMemoryKnowledgeRevisionRepository()
    left = genesis_command(operation_ids=["op:1"], payload={"n": 1})
    right = genesis_command(operation_ids=["op:2"], payload={"n": 2})
    left_id = revision_from_command(left).revision_id
    right_id = revision_from_command(right).revision_id
    barrier = threading.Barrier(2)
    winners: list[str] = []
    errors: list[BaseException] = []

    def publish(command: PublishKnowledgeRevisionCommand) -> None:
        try:
            barrier.wait(timeout=5)
            stored = repo.publish_revision(command)
        except BaseException as exc:
            errors.append(exc)
        else:
            winners.append(stored.revision.revision_id)

    threads = [
        threading.Thread(target=publish, args=(left,)),
        threading.Thread(target=publish, args=(right,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    assert all(not thread.is_alive() for thread in threads)
    assert len(winners) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], KnowledgeStaleParentRevisionError)
    head = repo.get_head(SPACE)
    assert head is not None
    assert head.head_revision_id == winners[0]
    loser_id = right_id if winners[0] == left_id else left_id
    assert repo.get_revision(SPACE, winners[0]) is not None
    assert repo.get_revision(SPACE, loser_id) is None
    assert len(repo.head_events(SPACE)) == 1


def test_injected_failure_rolls_back_memory_authority() -> None:
    def boom() -> None:
        raise RuntimeError("injected")

    repo = InMemoryKnowledgeRevisionRepository(after_revision_insert=boom)
    command = genesis_command()
    with pytest.raises(RuntimeError, match="injected"):
        repo.publish_revision(command)
    assert repo.get_head(SPACE) is None
    assert repo.get_revision(SPACE, revision_from_command(command).revision_id) is None
    assert repo.head_events(SPACE) == ()


def test_conflicting_envelope_is_not_overwritten() -> None:
    repo = InMemoryKnowledgeRevisionRepository()
    command = genesis_command()
    expected = revision_from_command(command)
    planted = expected.model_copy(update={"created_at": LATER})
    repo._revisions[(SPACE, expected.revision_id)] = StoredKnowledgeRevision.seal(
        planted, command.graph_payload
    )
    with pytest.raises(ImmutableRevisionConflictError):
        repo.publish_revision(command)
    stored = repo.get_revision(SPACE, expected.revision_id)
    assert stored is not None
    assert stored.revision.created_at == LATER
    assert repo.get_head(SPACE) is None
    assert repo.head_events(SPACE) == ()


def test_corrupt_revision_id_and_payload_hash_fail_closed() -> None:
    repo = InMemoryKnowledgeRevisionRepository()
    command = genesis_command()
    expected = revision_from_command(command)
    bad_id = expected.model_copy(update={"revision_id": "rev:" + "ab" * 16})
    repo._revisions[(SPACE, bad_id.revision_id)] = StoredKnowledgeRevision.seal(
        bad_id, command.graph_payload
    )
    with pytest.raises(PersistenceIntegrityError, match="recomputed native revision id"):
        repo.get_revision(SPACE, bad_id.revision_id)

    repo._revisions[(SPACE, expected.revision_id)] = StoredKnowledgeRevision(
        revision=expected,
        graph_payload_sha256="ab" * 32,
        _payload_json=canonical_json(command.graph_payload),
    )
    with pytest.raises(PersistenceIntegrityError, match="digest drift"):
        repo.get_revision(SPACE, expected.revision_id)


def test_immediate_replay_is_stale() -> None:
    repo = InMemoryKnowledgeRevisionRepository()
    command = genesis_command()
    first = repo.publish_revision(command)
    with pytest.raises(KnowledgeStaleParentRevisionError):
        repo.publish_revision(command)
    assert repo.get_head(SPACE).head_revision_id == first.revision.revision_id  # type: ignore[union-attr]
    assert len(repo.head_events(SPACE)) == 1
    assert repo.get_revision(SPACE, first.revision.revision_id) is not None


def test_repository_failure_does_not_retry_or_probe() -> None:
    parent = _parent()
    contribution = _contribution(parent, [_bob_item()])
    dispositions = _accepted("i1")
    before = contribution.model_dump(mode="json")
    materialization = _call(parent=parent, contribution=contribution, dispositions=dispositions)

    class Probe:
        def __init__(self) -> None:
            self.publish_calls = 0
            self.probes = 0

        def publish_revision(self, command: PublishKnowledgeRevisionCommand):
            del command
            self.publish_calls += 1
            raise PersistenceUnavailableError("down")

        def get_head(self, space_id: str):
            del space_id
            self.probes += 1
            raise AssertionError("head probe")

        def get_revision(self, space_id: str, revision_id: str):
            del space_id, revision_id
            self.probes += 1
            raise AssertionError("revision probe")

        def head_events(self, space_id: str):
            del space_id
            self.probes += 1
            raise AssertionError("event probe")

    probe = Probe()
    with pytest.raises(PersistenceUnavailableError):
        publish_governed_materialization(materialization, repository=probe)
    assert probe.publish_calls == 1
    assert probe.probes == 0
    assert contribution.model_dump(mode="json") == before


def test_v52_source_has_no_legacy_authority_vocabulary() -> None:
    for relative in V52_SOURCES:
        text = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert BANNED_VOCABULARY.search(text) is None, relative


def test_world_publication_and_frozen_contracts_are_unchanged() -> None:
    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            IMPLEMENTATION_BASE,
            "--",
            "src/dungeonmind/contracts/vnext",
            "src/dungeonmind/infrastructure/postgres/graph.py",
            "src/dungeonmind/infrastructure/memory/repositories.py",
            "src/dungeonmind/domain/revision_ids.py",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == ""
    bundle = json.loads(
        (REPO_ROOT / "Docs/Contracts/vnext/dm_vnext_contract_v1.json").read_text(encoding="utf-8")
    )
    assert bundle["aggregate_sha256"] == FROZEN_V0_AGGREGATE


def test_runtime_does_not_claim_v52_acceptance() -> None:
    banned = "V5_2_EXPECTED_PARENT_CAS_PUBLICATION_ACCEPTED"
    for path in (REPO_ROOT / "src").rglob("*.py"):
        assert banned not in path.read_text(encoding="utf-8")
    assert banned not in (REPO_ROOT / "Docs/Roadmaps/ROADMAP.md").read_text(encoding="utf-8")
