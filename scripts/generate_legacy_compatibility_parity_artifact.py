#!/usr/bin/env python3
"""Deterministic generator and validator for legacy v1-v6 compatibility parity artifact."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V1,
    GRAPH_SCHEMA_V2,
    GRAPH_SCHEMA_V3,
    GRAPH_SCHEMA_V4,
    GRAPH_SCHEMA_V5,
    GRAPH_SCHEMA_V6,
    VersionedUnionGraphSnapshotReader,
)
from dungeonmind.application.vnext.legacy_compat import (
    COMPATIBILITY_MANIFEST_SHA256,
    COMPATIBILITY_MAPPING_REVISION,
    build_historical_semantic_witness,
    build_parsed_revision_semantic_witness,
    decode_legacy_graph_revision,
)
from dungeonmind.application.vnext.records import ParsedEntityRefValue
from dungeonmind.contracts.graph import WorldGraphRevision
from dungeonmind.domain.canonical import canonical_sha256

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUTPUT_PATH = Path("Docs/Compatibility/legacy_v1_v6_parity_v1.json")


def _get_v1_workload() -> tuple[str, dict[str, Any], Any]:
    import tests.unit.test_graph_snapshot_reader as tr

    return "canonical_fixture_v1", copy.deepcopy(tr._payload()), None


def _get_v2_workload() -> tuple[str, dict[str, Any], Any]:
    import tests.unit.test_assertion_scoped_graph as tag

    return "canonical_fixture_v2", copy.deepcopy(tag._v2_payload()), None


def _get_v3_workload() -> tuple[str, dict[str, Any], Any]:
    import tests.unit.test_semantic_profile_graph as tsp

    return (
        "canonical_fixture_v3",
        copy.deepcopy(tsp._v3_payload()),
        tsp._narrative_registry(),
    )


def _get_v4_workload() -> tuple[str, dict[str, Any], Any]:
    import tests.unit.test_union_graph_v4 as tu4

    return "canonical_fixture_v4", copy.deepcopy(tu4._v4_payload()), tu4._registry()


def _get_v5_workload() -> tuple[str, dict[str, Any], Any]:
    import tests.unit.test_union_graph_v5 as tu5

    payload = copy.deepcopy(tu5._v5_payload())
    # Ensure payload exercises fictional time anchor ref and relationship assertion metadata
    payload["relationships"].append({
        "relationship_id": "rel:quill-self",
        "source_object_id": "obj:person-quill",
        "target_object_id": "obj:person-quill",
        "predicate": "test:knows",
        "assertion_metadata": {
            "schema_version": "dm_knowledge_assertion_metadata_v1",
            "assertion_id": "asrt:quill-knows",
            "campaign_scope": "camp:fellowship",
            "visibility": "player",
            "epistemic_kind": "asserted",
            "canon_state": "canonical",
            "evidence_ref_ids": ["ev:v5"],
            "session_refs": ["sess:1"],
            "temporal_scope": {
                "schema_version": "dm_temporal_scope_ref_v1",
                "kind": "fictional_time_ref",
                "fictional_time_ref": {
                    "schema_version": "dm_fictional_time_anchor_ref_v1",
                    "bundle_id": "bundle:ft-era1",
                    "campaign_id": "camp:fellowship",
                    "anchor_id": "anchor:year-100",
                },
            },
        },
    })
    return "canonical_fixture_v5", payload, tu5._registry()


def _get_v6_workload() -> tuple[str, dict[str, Any], Any]:
    import tests.unit.test_graph_snapshot_v6 as tu6

    return "canonical_fixture_v6", copy.deepcopy(tu6._v6_payload()), tu6._registry()


def generate_parity_artifact_data() -> dict[str, Any]:
    """Generate the complete legacy v1-v6 compatibility parity record set."""
    schema_workloads = [
        (GRAPH_SCHEMA_V1, _get_v1_workload),
        (GRAPH_SCHEMA_V2, _get_v2_workload),
        (GRAPH_SCHEMA_V3, _get_v3_workload),
        (GRAPH_SCHEMA_V4, _get_v4_workload),
        (GRAPH_SCHEMA_V5, _get_v5_workload),
        (GRAPH_SCHEMA_V6, _get_v6_workload),
    ]

    records: list[dict[str, Any]] = []

    for schema, getter in schema_workloads:
        workload_id, payload, registry = getter()
        world_id = payload.get("world_id", "world:compat-test")
        payload_sha256 = canonical_sha256(payload)

        rev = WorldGraphRevision(
            schema_version="dm_graph_revision_v1",
            world_id=world_id,
            revision_id=f"rev:compat-{schema}",
            parent_revision_id=None,
            created_at=datetime.now(UTC),
            operation_ids=[f"op:init-{schema}"],
            graph_schema=schema,
            graph_payload_sha256=payload_sha256,
            status="published",
        )

        parsed_rev = decode_legacy_graph_revision(
            revision=rev,
            graph_payload=payload,
            profile_registry=registry,
        )

        reader = VersionedUnionGraphSnapshotReader(profile_registry=registry)
        historical_snapshot = reader.parse(
            graph_schema=schema,
            graph_payload=payload,
        )

        hist_witness = build_historical_semantic_witness(historical_snapshot)
        parsed_witness = build_parsed_revision_semantic_witness(parsed_rev)

        hist_sha256 = canonical_sha256(hist_witness)
        parsed_sha256 = canonical_sha256(parsed_witness)

        if hist_sha256 != parsed_sha256:
            raise RuntimeError(
                f"Parity mismatch for schema {schema}: "
                f"historical={hist_sha256} parsed={parsed_sha256}"
            )

        entity_ref_count = sum(
            1 for asrt in parsed_rev.assertions_by_id.values()
            if isinstance(asrt.value, ParsedEntityRefValue)
        )
        alias_assertion_count = sum(
            1 for asrt in parsed_rev.assertions_by_id.values()
            if asrt.predicate == "dungeonmind.compat:alias"
        )

        records.append({
            "graph_schema": schema,
            "workload_identity": workload_id,
            "legacy_payload_sha256": payload_sha256,
            "historical_witness_sha256": hist_sha256,
            "compat_witness_sha256": parsed_sha256,
            "semantic_digest": parsed_rev.semantic_digest,
            "compatibility_key": parsed_rev.compatibility_key,
            "entity_count": len(parsed_rev.entities_by_id),
            "assertion_count": len(parsed_rev.assertions_by_id),
            "entity_ref_assertion_count": entity_ref_count,
            "evidence_count": len(parsed_rev.evidence_by_id),
            "alias_assertion_count": alias_assertion_count,
            "identity_alias_count": len(parsed_rev.aliases_by_id),
            "parity": "PASS",
        })

    records_digest = canonical_sha256(records)

    return {
        "artifact_schema": "dm_legacy_compatibility_parity_artifact_v1",
        "compatibility_mapping_revision": COMPATIBILITY_MAPPING_REVISION,
        "manifest_sha256": COMPATIBILITY_MANIFEST_SHA256,
        "vnext_format_version": "parsed_knowledge_revision_v1",
        "records_count": len(records),
        "records_digest": records_digest,
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate or check legacy v1-v6 compatibility parity artifact."
    )
    parser.add_argument(
        "--check",
        nargs="?",
        const=str(DEFAULT_OUTPUT_PATH),
        metavar="PATH",
        help="Check parity against existing artifact (default: Docs/Compatibility/...)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output path for generated parity artifact",
    )

    args = parser.parse_args()

    data = generate_parity_artifact_data()
    serialized = json.dumps(data, indent=2, sort_keys=True) + "\n"

    if args.check:
        check_path = Path(args.check)
        if not check_path.exists():
            print(f"ERROR: parity artifact not found at {check_path}", file=sys.stderr)
            return 1
        existing_text = check_path.read_text(encoding="utf-8")
        if existing_text != serialized:
            print(
                f"ERROR: parity artifact at {check_path} does not match fresh generation!",
                file=sys.stderr,
            )
            return 1
        print(f"OK: parity artifact at {check_path} is exact and all 6 schemas verify.")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(serialized, encoding="utf-8")
    print(
        f"OK: generated parity artifact at {args.out} "
        f"({data['records_count']} schemas, digest={data['records_digest'][:16]}...)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
