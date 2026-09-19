"""Structural characterization of vNext generic governed materialization."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dungeonmind.application.vnext.builder import build_parsed_knowledge_revision
from dungeonmind.application.vnext.materialization import (
    GovernedPublicationIdentity,
    materialize_governed_revision,
)
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
from dungeonmind.contracts.vnext.knowledge import KnowledgeRevision
from dungeonmind.contracts.vnext.source import EvidenceRefV3
from dungeonmind.domain.canonical import canonical_json, canonical_sha256

KNOWN_MERGE_BASE = "bc115eb40f1601e5b6c6fda23ff05ee5bf06883d"
NOW = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


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


def _build_parent(entity_count: int) -> dict[str, Any]:
    started = time.perf_counter()
    entities = [Entity(entity_id=f"ent:{index:05d}") for index in range(entity_count)]
    assertions = [
        Assertion(
            assertion_id=f"asrt:{index:05d}",
            subject_entity_id=f"ent:{index:05d}",
            predicate="bench:title",
            value=LiteralValue(value=f"name-{index:05d}"),
            metadata=_meta(),
        )
        for index in range(entity_count)
    ]
    evidence = [
        EvidenceRefV3(
            evidence_ref_id="ev:bench",
            source_artifact_id="art:bench",
            source_revision_id="srcrev:bench",
            evidence_role="support",
            can_open_source=True,
            can_highlight_span=False,
        )
    ]
    contract, profile = _descriptors()
    revision = KnowledgeRevision(
        space_id="space:bench",
        revision_id=f"rev:parent-{entity_count}",
        created_at=NOW,
        operation_ids=["op:parent"],
        graph_schema="dm_vnext_graph_v1",
        graph_payload_sha256="0" * 64,
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
    )
    parsed = build_parsed_knowledge_revision(
        revision=revision,
        entities=entities,
        assertions=assertions,
        evidence=evidence,
    )
    reconstruct_ms = (time.perf_counter() - started) * 1000.0
    return {
        "parsed": parsed,
        "entity_count": len(parsed.entities_by_id),
        "assertion_count": len(parsed.assertions_by_id),
        "reconstruct_ms": reconstruct_ms,
        "semantic_digest": parsed.semantic_digest,
    }


def _percentiles(samples_ms: list[float]) -> dict[str, float]:
    ordered = sorted(samples_ms)
    if not ordered:
        return {"p50_ms": 0.0, "p95_ms": 0.0}
    p50 = statistics.median(ordered)
    idx = min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))
    return {"p50_ms": p50, "p95_ms": ordered[idx]}


def _time_materialize(parent: Any, iterations: int) -> dict[str, Any]:
    contribution = KnowledgeContribution(
        contribution_id="contrib:tiny",
        space_id=parent.space_id,
        producer="producer:bench",
        produced_at=NOW,
        status="finalized",
        items=[ProposeEntity(item_id="i1", entity=Entity(entity_id="ent:tiny-new"))],
    )
    dispositions = [ContributionDisposition(item_id="i1", disposition="accepted")]
    publication = GovernedPublicationIdentity(
        operation_ids=("op:child",),
        created_at=NOW,
        expected_parent_revision_id=parent.revision_id,
    )
    samples: list[float] = []
    validate_samples: list[float] = []
    serialize_samples: list[float] = []
    result = None
    contract, profile = _descriptors()
    for _ in range(iterations):
        started = time.perf_counter()
        result = materialize_governed_revision(
            parent=parent,
            contribution=contribution,
            dispositions=dispositions,
            publication=publication,
            domain_contract=contract,
            semantic_profile=profile,
        )
        samples.append((time.perf_counter() - started) * 1000.0)
        validate_samples.append(result.validate_ms)
        serialize_samples.append(result.serialize_hash_ms)
    assert result is not None
    payload_bytes = len(canonical_json(result.command.graph_payload).encode("utf-8"))
    child_entities = [item["entity_id"] for item in result.command.graph_payload["entities"]]
    validate_pct = _percentiles(validate_samples)
    serialize_pct = _percentiles(serialize_samples)
    return {
        "accepted_item_count": len(result.accepted_item_ids),
        "rejected_item_count": len(result.rejected_item_ids),
        "child_entity_count": len(result.command.graph_payload["entities"]),
        "child_assertion_count": len(result.command.graph_payload["assertions"]),
        "payload_bytes": payload_bytes,
        "bytes_written": 0,
        "graph_payload_sha256": result.graph_payload_sha256,
        "tiny_entity_present": "ent:tiny-new" in child_entities,
        "parent_revision_id": result.command.parent_revision_id,
        "expected_parent_revision_id": result.command.expected_parent_revision_id,
        **_percentiles(samples),
        "validate_p50_ms": validate_pct["p50_ms"],
        "validate_p95_ms": validate_pct["p95_ms"],
        "serialize_hash_p50_ms": serialize_pct["p50_ms"],
        "serialize_hash_p95_ms": serialize_pct["p95_ms"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=24)
    parser.add_argument("--exact-head", default="")
    parser.add_argument(
        "--output",
        default="Docs/Benchmarks/vnext_governed_materialization_10k_v1.json",
    )
    args = parser.parse_args()

    parent_10k = _build_parent(10_000)
    parent_1k = _build_parent(1_000)
    tiny_10k = _time_materialize(parent_10k["parsed"], args.iterations)
    tiny_1k = _time_materialize(parent_1k["parsed"], args.iterations)

    structural_ok = (
        parent_10k["entity_count"] == 10_000
        and tiny_10k["accepted_item_count"] == 1
        and tiny_10k["tiny_entity_present"] is True
        and tiny_10k["bytes_written"] == 0
        and tiny_10k["parent_revision_id"] == tiny_10k["expected_parent_revision_id"]
        and tiny_10k["child_entity_count"] == 10_001
        and tiny_1k["child_entity_count"] == 1_001
    )

    artifact = {
        "schema_version": "vnext_governed_materialization_10k_v1",
        "characterization_only": True,
        "exact_base": KNOWN_MERGE_BASE,
        "exact_head": args.exact_head or _git_head(),
        "seed": "generic-governed-materialization-v1",
        "workloads": {
            "space_10k": {
                "entity_count": parent_10k["entity_count"],
                "assertion_count": parent_10k["assertion_count"],
                "reconstruct_ms": parent_10k["reconstruct_ms"],
                "semantic_digest": parent_10k["semantic_digest"],
            },
            "space_1k": {
                "entity_count": parent_1k["entity_count"],
                "assertion_count": parent_1k["assertion_count"],
                "reconstruct_ms": parent_1k["reconstruct_ms"],
                "semantic_digest": parent_1k["semantic_digest"],
            },
        },
        "runs": {
            "tiny_accepted_change_10k": {
                "parent_entity_count": parent_10k["entity_count"],
                "parent_assertion_count": parent_10k["assertion_count"],
                "parent_reconstruct_ms": parent_10k["reconstruct_ms"],
                **tiny_10k,
            },
            "tiny_accepted_change_1k": {
                "parent_entity_count": parent_1k["entity_count"],
                "parent_assertion_count": parent_1k["assertion_count"],
                "parent_reconstruct_ms": parent_1k["reconstruct_ms"],
                **tiny_1k,
            },
        },
        "structural_gate": "PASS" if structural_ok else "FAIL",
        "notes": (
            "In-memory materialization only. bytes_written is always 0; "
            "publication latency is not measured in V5.1."
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
