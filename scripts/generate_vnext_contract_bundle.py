#!/usr/bin/env python3
"""Generate/check the deterministic DungeonMind vNext JSON Schema bundle."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from dungeonmind.contracts import vnext
from dungeonmind.contracts.vnext.common import canonical_json, sha256

PUBLIC_TYPES = [
    vnext.DomainContractRef,
    vnext.DomainContractDescriptor,
    vnext.SemanticProfileDescriptorV2,
    vnext.Entity,
    vnext.Assertion,
    vnext.IdentityAlias,
    vnext.IdentityDecisionV3,
    vnext.SourceArtifactV3,
    vnext.SourceRevisionV2,
    vnext.EvidenceRefV3,
    vnext.KnowledgeRevision,
    vnext.KnowledgeHead,
    vnext.PublishKnowledgeRevisionCommand,
    vnext.KnowledgeContribution,
    vnext.ContributionDisposition,
    vnext.ProjectionRequest,
    vnext.ProjectionSnapshot,
]


def make_bundle() -> dict[str, Any]:
    contracts = []
    for model in sorted(PUBLIC_TYPES, key=lambda item: item.__name__):
        schema = model.model_json_schema(by_alias=True, ref_template="#/$defs/{model}")
        schema_bytes = canonical_json(schema)
        contracts.append(
            {
                "public_name": model.__name__,
                "schema_version": schema.get("properties", {})
                .get("schema_version", {})
                .get("const"),
                "canonical_json_schema": schema,
                "schema_sha256": sha256(schema_bytes),
            }
        )
    bundle = {
        "bundle_schema": "dm_vnext_contract_bundle_v1",
        "contract_family": "dungeonmind-vnext",
        "contract_revision": "v1",
        "contracts": contracts,
    }
    bundle["aggregate_sha256"] = sha256(canonical_json(bundle))
    return bundle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()
    if bool(args.output) == bool(args.check):
        parser.error("provide exactly one of --output or --check")
    payload = canonical_json(make_bundle()) + b"\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(payload)
        return 0
    if not args.check.exists() or args.check.read_bytes() != payload:
        print(f"schema bundle is stale: {args.check}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
