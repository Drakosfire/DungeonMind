"""Regenerate tests/fixtures/curated_world_v1.json deterministically.

The fixture is a tiny synthetic world (no corpus prose, no PII, no real
campaign data) that proves the substrate end-to-end: revision publish → exact
read with intact hash → semantic search with scope/visibility filters.

Run: uv run python scripts/build_curated_fixture.py
"""

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "curated_world_v1.json"

WORLD_ID = "world:demo-atlas"
GRAPH_SCHEMA = "dm_union_graph_v1"

GRAPH_PAYLOAD = {
    "world_id": WORLD_ID,
    "nodes": [
        {
            "object_id": "obj:city-vael",
            "kind": "location",
            "label": "Vael",
            "aliases": ["Vael City"],
        },
        {
            "object_id": "obj:npc-mere-astor",
            "kind": "npc",
            "label": "Mere Astor",
            "aliases": ["Astor"],
        },
        {
            "object_id": "obj:item-sun-ledger",
            "kind": "artifact",
            "label": "The Sun Ledger",
        },
    ],
    "relationships": [
        {
            "subject_object_id": "obj:npc-mere-astor",
            "predicate": "resides_in",
            "object_object_id": "obj:city-vael",
        },
        {
            "subject_object_id": "obj:npc-mere-astor",
            "predicate": "safeguards",
            "object_object_id": "obj:item-sun-ledger",
        },
    ],
}

SEMANTIC_DOCUMENTS = [
    {
        "semantic_document_id": "sdoc:obj-city-vael",
        "graph_object_id": "obj:city-vael",
        "document_kind": "graph_object",
        "campaign_scope": None,
        "visibility": "gm",
        "content": "Vael: a terraced harbor city ruled by its tide-courts and lantern ward.",
        "embedding": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    },
    {
        "semantic_document_id": "sdoc:obj-npc-mere-astor",
        "graph_object_id": "obj:npc-mere-astor",
        "document_kind": "graph_object",
        "campaign_scope": None,
        "visibility": "gm",
        "content": "Mere Astor: the Sun Ledger's keeper, a soft-spoken factor of Vael.",
        "embedding": [0.8, 0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    },
    {
        "semantic_document_id": "sdoc:obj-item-sun-ledger",
        "graph_object_id": "obj:item-sun-ledger",
        "document_kind": "graph_object",
        "campaign_scope": None,
        "visibility": "gm",
        "content": "The Sun Ledger: a brass-bound account of every dawn debt owed in Vael.",
        "embedding": [0.0, 0.05, 0.95, 0.0, 0.0, 0.0, 0.0, 0.0],
    },
    {
        "semantic_document_id": "sdoc:rumor-tide-courts",
        "graph_object_id": "obj:city-vael",
        "document_kind": "graph_object",
        "campaign_scope": "camp:demo",
        "visibility": "player",
        "content": "Street rumor: the tide-courts of Vael vote at dawn and forget by dusk.",
        "embedding": [0.6, 0.1, 0.3, 0.0, 0.0, 0.0, 0.0, 0.0],
    },
]

QUERIES = [
    {
        "name": "ledger_semantic",
        "embedding": [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "expect_dense_first": "sdoc:obj-item-sun-ledger",
    }
]


def main() -> None:
    fixture = {
        "fixture_version": "curated_world_v1",
        "world_id": WORLD_ID,
        "graph_schema": GRAPH_SCHEMA,
        "graph_payload": GRAPH_PAYLOAD,
        "source_artifacts": [
            {
                "source_artifact_id": "src:atlas-notes",
                "source_domain": "worldbuilding",
                "world_id": WORLD_ID,
                "campaign_id": None,
                "session_id": None,
                "visibility": "gm",
            }
        ],
        "semantic_documents": SEMANTIC_DOCUMENTS,
        "queries": QUERIES,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
