# HANDOFF — Assertion-scoped World Graph v4 (handback)

**Created:** 2026-08-07  
**Status:** COMPLETE — implementation handback (Cycle 1 REQUEST CHANGES addressed)  
**Repository:** `Drakosfire/DungeonMind`  
**Flow:** WORLD / KERNEL  
**Branch:** `world/assertion-scoped-graph-v4`  
**Base SHA:** `8095321ed011b8a38640615a90cbc9efaf385e8c` (DungeonMind `main` / merge of #23)  
**PR:** [#24](https://github.com/Drakosfire/DungeonMind/pull/24)  
**Reviewed head (Cycle 1):** `0be1cfe07f48d406a5e5aea9399692802af19df7`  
**Fix head (Cycle 1 corrections):** `fc0339b094359d81b34951ab13e913c1aa6057ea`

**Review accounting:** `review cycles: 1` (Cycle 1: REQUEST CHANGES — 1 P1 + 1 P2; fixes in this update)

### Cycle 1 corrections

| Finding | Fix |
|---------|-----|
| **P1** Opaque `fictional_time_ref: str` parallel to FT authority | Replaced with `FictionalTimeAnchorRefV1` (`dm_fictional_time_anchor_ref_v1`: `bundle_id` + `campaign_id` + `anchor_id`) in `contracts/fictional_time.py`. Opaque strings fail closed. Campaign compatibility: `campaign_scope` null or equals `ref.campaign_id`. No FT query logic added. |
| **P2** Empty `evidence_ref_ids` contract-valid but reader-invalid | `KnowledgeAssertionMetadataV1.evidence_ref_ids` now `Field(min_length=1)`; direct contract test without reader. Reader keeps resolvability checks. |

---

## §1 Dispatch gate (satisfied)

| Anchor | State |
|--------|--------|
| Buddy PR #522 | MERGED into Buddy `main` as `d30f94f1…` |
| Approved #522 head | `9d1f8349…` is ancestor of Buddy `main` (unchanged) |
| DungeonMind `main` at start | `8095321…` — no intervening graph-schema PR |
| Competing `dm_union_graph_v4` claim | none |

---

## §2 Contract inventory (new public)

| Symbol | Schema / role |
|--------|----------------|
| `TemporalScopeKind` | `unknown` / `world_timeless` / `fictional_time_ref` |
| `TemporalScopeRefV1` | `dm_temporal_scope_ref_v1` |
| `FictionalTimeAnchorRefV1` | `dm_fictional_time_anchor_ref_v1` — exact `bundle_id` + `campaign_id` + `anchor_id` into FT claim-bundle authority |
| `EpistemicKindV2` | asserted/inferred/speculative/**fact**/**source_derived_candidate** (no remapping) |
| `KnowledgeAssertionMetadataV1` | `dm_knowledge_assertion_metadata_v1` (`evidence_ref_ids` nonempty at contract) |
| `GRAPH_SCHEMA_V4` | `dm_union_graph_v4` |
| `UnionGraphV4SnapshotReader` | exact schema dispatch |
| `UnionGraphV4Payload` (+ object/alias/summary/property/relationship records) | strict payload models |

Historical `EpistemicKind` (`asserted|inferred|speculative`) unchanged.

---

## §3 Representative v4 shape

See `tests/unit/test_union_graph_v4.py` fixtures and `tests/integration/test_postgres_graph_v4.py`.

Conceptual:

```json
{
  "world_id": "world:…",
  "semantic_profile": { "schema_version": "dm_semantic_profile_ref_v1", "…": "…" },
  "objects": [
    {
      "object_id": "obj:person-quill",
      "kind": "test:person",
      "label": "Quill",
      "assertion_metadata": {
        "schema_version": "dm_knowledge_assertion_metadata_v1",
        "assertion_id": "asrt:quill-exists",
        "campaign_scope": null,
        "visibility": "gm",
        "epistemic_kind": "fact",
        "canon_state": "canonical",
        "evidence_ref_ids": ["ev:…"],
        "session_refs": ["session-23"],
        "temporal_scope": { "schema_version": "dm_temporal_scope_ref_v1", "kind": "unknown" }
      },
      "aliases": [{ "value": "…", "assertion_metadata": { "…" : "…" } }],
      "summary": null,
      "properties": [{ "property_term": "test:role", "value": "scribe", "assertion_metadata": { "…" : "…" } }]
    }
  ],
  "relationships": [
    {
      "relationship_id": "rel:…",
      "source_object_id": "obj:…",
      "target_object_id": "obj:…",
      "predicate": "test:located_in",
      "assertion_metadata": { "…" : "…" }
    }
  ],
  "evidence_refs": [ { "schema_version": "dm_evidence_ref_v1", "…" : "…" } ]
}
```

---

## §4 Compatibility

| Schema | Result |
|--------|--------|
| v1 | unchanged — rejects `semantic_profile` / v4 schema / v4-only keys |
| v2 | unchanged — assertion-scoped alias/summary privacy retained |
| v3 | unchanged — profile pin + namespace admission retained |
| v4 | additive — uses `objects` (not `nodes`) so silent cross-parse fails |

Evidence: unit suites `test_union_graph_v4`, `test_semantic_profile_graph`, `test_graph_snapshot_reader`, `test_import_boundaries` green on this head.

---

## §5 Assertion semantics

| Unit | Carries `KnowledgeAssertionMetadataV1` | Independently scoped |
|------|----------------------------------------|----------------------|
| object existence | yes | yes |
| alias | yes | yes |
| summary | yes | yes |
| property | yes | yes |
| relationship | yes | yes |

`assertion_id` globally unique across all families in one revision.

---

## §6 Temporal statement

```text
session_refs are not fictional time
temporal unknown is not timeless
no fictional-time derivation or query logic was added
fictional_time_ref is FictionalTimeAnchorRefV1 (bundle_id + campaign_id + anchor_id)
opaque ftime strings are rejected
campaign_scope must be null or equal fictional_time_ref.campaign_id
```

---

## §7 Dependency proof

```text
DungeonMind kernel imports no dungeonmind_dnd
DungeonMind imports no DungeonMindBuddy
```

Enforced by `tests/unit/test_import_boundaries.py`.

---

## §8 PostgreSQL

`tests/integration/test_postgres_graph_v4.py` — publish v4 → exact get_revision → canonical payload equality + re-parse under `UnionGraphV4SnapshotReader`.

Executed green in implementation environment against `compose.postgres.yml` (agent reported 12 integration graph tests including v4). Re-run locally:

```bash
uv sync --locked --extra postgres --extra api
docker compose -f compose.postgres.yml up -d
export DUNGEONMIND_DATABASE_URL=postgresql://dungeonmind:dungeonmind-dev@localhost:54329/dungeonmind
uv run alembic upgrade head
uv run pytest -m integration tests/integration/test_postgres_graph_v4.py tests/integration/test_postgres_graph.py -q
```

---

## §9 Expected Buddy #522 ledger delta (after Buddy re-pin)

Structurally representable after this PR (adapter proof still pending):

- CAMPAIGN_SCOPE
- EPISTEMIC_STATE (`fact` / `source_derived_candidate`)
- ATTRIBUTE_ASSERTION (generic property assertions; D&D `role` meaning still profile-gap)
- session_ids → `session_refs` (true fictional-time still unresolved)
- alias assertion + evidence grain

Still red:

```text
WORLD_OBJECT_KIND
RELATIONSHIP_PREDICATE
D&D property vocabulary
source/evidence provenance v2
source-domain mappings
authority_state migration
contribution/reconstruction history
existing-world adoption seam
PostgreSQL Eldyrwild adoption
whole real Eldyrwild target construction
product projection / dark cutover
```

Overall remains:

```text
WHOLE_GRAPH_ADOPTION_NOT_READY
CUTOVER_NOT_READY
```

---

## §10 Nonclaims

```text
No real Eldyrwild migration was performed.
DungeonMind is not yet whole-graph product authority.
D&D whole-world vocabulary is still incomplete.
Source/evidence migration is still incomplete.
Contribution history adoption policy is still unresolved.
Existing-world bootstrap/adoption seam is still missing.
PostgreSQL adoption of Eldyrwild was not executed.
Dark cutover has not run.
canon_state is recorded on v4 assertions but not yet used as a read filter (ADR-0014 deferral).
```

---

## §11 Files

| Path | Change |
|------|--------|
| `src/dungeonmind/contracts/fictional_time.py` | ADD `FictionalTimeAnchorRefV1` |
| `src/dungeonmind/contracts/knowledge_assertion.py` | CREATE (+ Cycle 1: typed FT ref + nonempty evidence) |
| `src/dungeonmind/application/graph_snapshot_v4.py` | CREATE |
| `src/dungeonmind/application/graph_snapshot.py` | V4 dispatch + view extensions |
| `src/dungeonmind/application/graph_scope.py` | assertion-grain admission |
| `src/dungeonmind/contracts/__init__.py` | exports |
| `Docs/Decisions/ADR-0014-assertion-scoped-world-graph-v4.md` | CREATE (+ Cycle 1 amendments) |
| `Docs/Architecture/ARCHITECTURE.md` | schema-status note |
| `tests/unit/test_union_graph_v4.py` | CREATE (+ Cycle 1 contract tests) |
| `tests/integration/test_postgres_graph_v4.py` | CREATE |
| `tests/fixtures/semantic_profiles/test-kernel-v1.json` | CREATE |

---

## §12 Named successor

Preferred next generic slice:

```text
KERNEL: preserve whole-world source and evidence provenance v2
```

Then D&D whole-world vocabulary v2, then existing-world bootstrap adoption (with genesis/history policy).
