"""Deterministic, synthetic World-like and Rules-like graph workloads."""

from __future__ import annotations

from typing import Any

from benchmarks.world_graph_reads import generate_payload

GENERATOR_VERSION = "vnext-scale-fixtures-1"
SEED = 20260928
WORLD_ID = "world:bench"


def make_payload(
    *, shape: str, size: int, seed: int = SEED
) -> tuple[dict[str, Any], dict[str, Any]]:
    if shape not in {"world_like", "rules_like"}:
        raise ValueError(f"unknown workload shape: {shape}")
    payload, base = generate_payload(object_count=size, seed=seed)
    if shape == "world_like":
        params = {**base, "shape": shape, "size": size, "seed": seed}
        return payload, params

    # Rules-like is deliberately only a stress shape: small records, dense evidence,
    # and repeated dependency-style edges. It retains the real V6 contract and
    # DungeonMind's World semantics; it does not claim Rules-domain semantics.
    evidence = payload["evidence_refs"]
    evidence_ids = {row["evidence_ref_id"] for row in evidence}
    for obj in payload["objects"]:
        own = obj["assertion_metadata"]["evidence_ref_ids"]
        for alias in obj["aliases"]:
            alias["assertion_metadata"]["evidence_ref_ids"] = list(own)
        for prop in obj["properties"]:
            prop["assertion_metadata"]["evidence_ref_ids"] = list(own)
    for index, rel in enumerate(payload["relationships"]):
        # Reuse stable source rows while raising edge evidence density.
        rel["assertion_metadata"]["evidence_ref_ids"] = [
            f"ev:r:{index:06d}",
            f"ev:o:{index % size:06d}",
        ]
        if f"ev:o:{index % size:06d}" not in evidence_ids:
            raise AssertionError("fixture evidence identity drift")
    params = {
        **base,
        "shape": shape,
        "size": size,
        "seed": seed,
        "rules_like_relationship_evidence_refs_per_edge": 2,
        "rules_like_note": "stress shape only; no Rules-domain semantics asserted",
    }
    return payload, params
