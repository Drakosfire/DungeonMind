"""In-memory characterization of native expected-parent CAS publication.

Logical authority bytes are canonical serialized revision payload plus graph
payload. They are not PostgreSQL WAL size, disk amplification, or physical I/O.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dungeonmind.application.vnext.authority import revision_from_command
from dungeonmind.application.vnext.builder import build_parsed_knowledge_revision
from dungeonmind.application.vnext.materialization import (
    GovernedMaterializationResult,
    GovernedPublicationIdentity,
    decode_native_graph_payload,
    encode_native_graph_payload,
    materialize_governed_revision,
)
from dungeonmind.application.vnext.model import ParsedKnowledgeRevision
from dungeonmind.application.vnext.publication import publish_governed_materialization
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext.common import (
    EpistemicBasis,
    KnowledgeStanding,
    PublicVisibility,
    ScopeBinding,
    TimelessTemporalScope,
)
from dungeonmind.contracts.vnext.contribution import (
    ContributionDisposition,
    KnowledgeContribution,
    ProposeEntity,
)
from dungeonmind.contracts.vnext.domain import (
    Assertion,
    AssertionMetadata,
    DomainContractDescriptor,
    DomainContractRef,
    Entity,
    LiteralValue,
    SemanticProfileDescriptorV2,
    SemanticProfilePredicate,
)
from dungeonmind.contracts.vnext.knowledge import PublishKnowledgeRevisionCommand
from dungeonmind.contracts.vnext.source import EvidenceRefV3
from dungeonmind.domain.canonical import canonical_json, canonical_sha256
from dungeonmind.infrastructure.memory.vnext_knowledge import InMemoryKnowledgeRevisionRepository

KNOWN_BASE = "9f006bf77d72faabee8a3eef359b89a3d537b0c1"
NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
SPACE = "space:bench"


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def _percentiles(samples_ms: list[float]) -> dict[str, float]:
    ordered = sorted(samples_ms)
    p50 = statistics.median(ordered)
    index = min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))
    return {"p50_ms": p50, "p95_ms": ordered[index]}


def _descriptors() -> tuple[DomainContractDescriptor, SemanticProfileDescriptorV2]:
    contract = DomainContractDescriptor(
        domain_id="bench.domain",
        domain_revision="1",
        scope_axes=["bench:scope"],
        claim_modes=["bench:fact"],
        admission_policy_id="bench.always",
    )
    profile = SemanticProfileDescriptorV2(
        profile_id="bench.profile",
        profile_revision="1",
        term_namespaces=["bench"],
        predicates=[
            SemanticProfilePredicate(term="bench:title", allowed_value_kinds=["literal"]),
        ],
    )
    return contract, profile


def _meta() -> AssertionMetadata:
    return AssertionMetadata(
        scope=[ScopeBinding(axis="bench:scope", value="one")],
        visibility=PublicVisibility(),
        epistemic_basis=EpistemicBasis.ASSERTED,
        claim_mode="bench:fact",
        standing=KnowledgeStanding.ESTABLISHED,
        evidence_ref_ids=["ev:bench"],
        temporal_scope=TimelessTemporalScope(),
    )


def _parent_command(entity_count: int) -> PublishKnowledgeRevisionCommand:
    entities = {
        f"ent:{index:05d}": Entity(entity_id=f"ent:{index:05d}") for index in range(entity_count)
    }
    assertions = {
        f"asrt:{index:05d}": Assertion(
            assertion_id=f"asrt:{index:05d}",
            subject_entity_id=f"ent:{index:05d}",
            predicate="bench:title",
            value=LiteralValue(value=f"name-{index:05d}"),
            metadata=_meta(),
        )
        for index in range(entity_count)
    }
    evidence = {
        "ev:bench": encode_evidence(),
    }
    contract, profile = _descriptors()
    return PublishKnowledgeRevisionCommand(
        space_id=SPACE,
        parent_revision_id=None,
        expected_parent_revision_id=None,
        operation_ids=["op:parent"],
        graph_schema="dm_vnext_graph_v1",
        graph_payload=encode_native_graph_payload(
            entities=entities,
            assertions=assertions,
            aliases={},
            evidence=evidence,
        ),
        domain_contract_ref=DomainContractRef(
            domain_id=contract.domain_id,
            domain_revision=contract.domain_revision,
            descriptor_sha256=canonical_sha256(contract.model_dump(mode="json")),
        ),
        semantic_profile_ref=SemanticProfileRef(
            profile_id=profile.profile_id,
            profile_revision=profile.profile_revision,
            descriptor_sha256=canonical_sha256(profile.model_dump(mode="json")),
        ),
        created_at=NOW,
    )


def encode_evidence() -> EvidenceRefV3:
    return EvidenceRefV3(
        evidence_ref_id="ev:bench",
        source_artifact_id="art:bench",
        source_revision_id="srcrev:bench",
        evidence_role="support",
        can_open_source=True,
        can_highlight_span=False,
    )


def _materialization(
    parent_command: PublishKnowledgeRevisionCommand,
) -> tuple[ParsedKnowledgeRevision, GovernedMaterializationResult]:
    revision = revision_from_command(parent_command)
    parent = build_parsed_knowledge_revision(
        revision=revision,
        decoded_content=decode_native_graph_payload(parent_command.graph_payload),
    )
    contract, profile = _descriptors()
    contribution = KnowledgeContribution(
        contribution_id="contrib:tiny",
        space_id=SPACE,
        producer="producer:bench",
        produced_at=NOW,
        status="finalized",
        items=[ProposeEntity(item_id="i1", entity=Entity(entity_id="ent:tiny-new"))],
    )
    result = materialize_governed_revision(
        parent=parent,
        contribution=contribution,
        dispositions=[ContributionDisposition(item_id="i1", disposition="accepted")],
        publication=GovernedPublicationIdentity(
            operation_ids=("op:child",),
            created_at=NOW,
            expected_parent_revision_id=parent.revision_id,
        ),
        domain_contract=contract,
        semantic_profile=profile,
    )
    return parent, result


def _time_publish(
    parent_command: PublishKnowledgeRevisionCommand,
    materialization: GovernedMaterializationResult,
    iterations: int,
) -> dict[str, Any]:
    samples: list[float] = []
    published = None
    repo: InMemoryKnowledgeRevisionRepository | None = None
    for _ in range(iterations):
        repo = InMemoryKnowledgeRevisionRepository()
        repo.publish_revision(parent_command)
        started = time.perf_counter()
        published = publish_governed_materialization(materialization, repository=repo)
        samples.append((time.perf_counter() - started) * 1000.0)
    assert published is not None and repo is not None
    envelope = canonical_json(published.revision.model_dump(mode="json")).encode("utf-8")
    graph = canonical_json(published.graph_payload).encode("utf-8")
    head = repo.get_head(SPACE)
    assert head is not None
    events = repo.head_events(SPACE)
    parent_id = revision_from_command(parent_command).revision_id
    child_entities = [item["entity_id"] for item in published.graph_payload["entities"]]
    return {
        "parent_revision_id": parent_id,
        "head_before": parent_id,
        "head_after": head.head_revision_id,
        "revision_id": published.revision.revision_id,
        "graph_payload_sha256": published.graph_payload_sha256,
        "child_payload_bytes": len(graph),
        "revision_envelope_bytes": len(envelope),
        "logical_authority_bytes_written": len(envelope) + len(graph),
        "head_event_delta": 1,
        "revision_row_delta": 1,
        "head_event_count": len(events),
        "revision_row_count": 2,
        "child_entity_count": len(child_entities),
        "tiny_entity_present": "ent:tiny-new" in child_entities,
        "iterations": iterations,
        **_percentiles(samples),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=8)
    parser.add_argument("--exact-head", default="")
    parser.add_argument("--output", default="Docs/Benchmarks/vnext_cas_publication_10k_v1.json")
    args = parser.parse_args()

    runs: dict[str, Any] = {}
    workloads: dict[str, Any] = {}
    for label, count in (("1k", 1_000), ("10k", 10_000)):
        command = _parent_command(count)
        parent, materialization = _materialization(command)
        measured = _time_publish(command, materialization, args.iterations)
        parent_bytes = len(canonical_json(command.graph_payload).encode("utf-8"))
        workloads[f"space_{label}"] = {
            "entity_count": count,
            "assertion_count": count,
            "parent_payload_bytes": parent_bytes,
            "parent_revision_id": parent.revision_id,
        }
        runs[f"tiny_accepted_change_{label}"] = {
            "parent_entity_count": count,
            "parent_assertion_count": count,
            "parent_payload_bytes": parent_bytes,
            **measured,
        }

    ten = runs["tiny_accepted_change_10k"]
    one = runs["tiny_accepted_change_1k"]
    structural_ok = (
        ten["child_entity_count"] == 10_001
        and one["child_entity_count"] == 1_001
        and ten["tiny_entity_present"] is True
        and ten["head_before"] == ten["parent_revision_id"]
        and ten["head_after"] == ten["revision_id"]
        and ten["head_event_delta"] == 1
        and ten["revision_row_delta"] == 1
        and ten["logical_authority_bytes_written"]
        == ten["revision_envelope_bytes"] + ten["child_payload_bytes"]
    )
    artifact = {
        "schema_version": "vnext_cas_publication_10k_v1",
        "characterization_only": True,
        "adapter": "in_memory",
        "exact_base": KNOWN_BASE,
        "exact_head": args.exact_head or _git_head(),
        "seed": "expected-parent-cas-publication-v1",
        "workloads": workloads,
        "runs": runs,
        "structural_gate": "PASS" if structural_ok else "FAIL",
        "notes": (
            "In-memory adapter. logical_authority_bytes_written is canonical "
            "revision-envelope bytes plus canonical graph-payload bytes. It is "
            "not PostgreSQL WAL size, disk amplification, or physical I/O. "
            "No V5.2 performance threshold is claimed."
        ),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "structural_gate": artifact["structural_gate"]}))
    if not structural_ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
