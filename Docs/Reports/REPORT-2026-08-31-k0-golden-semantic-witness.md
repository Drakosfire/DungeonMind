# Report — 2026-08-31 K0.2 golden semantic witness

**Status:** deterministic World-authority semantic oracle for K2.5 inheritance; no runtime behavior change  
**Artifact:** [`K0-golden-semantic-witness-v1.json`](K0-golden-semantic-witness-v1.json)  
**Schema:** `dm_k0_semantic_witness_v1`  
**Predecessor:** PR #48 / [`REPORT-2026-08-30-k0-current-consumer-public-surface.md`](REPORT-2026-08-30-k0-current-consumer-public-surface.md) / [`K0-surface-inventory.json`](K0-surface-inventory.json)  
**Formal review cycles:** 1 (implementation self-check); steward PASS review ID pending PR review

This witness freezes meaning, not wall-clock cost. Observation-only fields never participate in golden equality. K0.2 does **not** authorize demolition, performance claims, or Buddy pin movement.

## 1. Exact implementation base and inputs

```text
dungeonmind_base_sha              = 3b52a81a6c113ac6bfb4d1b0fa7fa78246aa31f1
k0_inventory_schema               = dm_k0_surface_inventory_v1
k0_inventory_digest               = sha256:1154b0fb9ce4d0845782aaaff0d9ad901920633bb940d2e0514925a274214358
fixture_digest                    = sha256:d5e9ee49b54e07e757cf7d57597506052e93606f2dbfc7644600504daa8a015f
normalization_policy_digest       = sha256:3238b159569ecbb66f1b6298f34a0903bc79a792f04ffecd481abc39bd802fa9
witness_schema                    = dm_k0_semantic_witness_v1
aggregate_semantic_sha256         = sha256:1e43340fc00eac54c0c52378e0e879fd42ff87c6aabcb082b59b47ef12767906
canonical_adapter                 = memory
```

Runtime/schema/dependency gate against the K0.2 base:

```bash
git diff --exit-code 3b52a81a6c113ac6bfb4d1b0fa7fa78246aa31f1 -- \
  src migrations alembic alembic.ini pyproject.toml uv.lock
```

Result: empty (no production diff).

Reproduction:

```bash
uv run python scripts/k0_semantic_witness.py \
  --adapter memory \
  --output Docs/Reports/K0-golden-semantic-witness-v1.json
cmp Docs/Reports/K0-golden-semantic-witness-v1.json \
    /tmp/k0-golden-semantic-witness-v1.json
```

Second generation into `/tmp` is byte-identical (`cmp` OK).

## 2. Synthetic world shape

Small governed v6 world (`world:test`) reused from proven retrieval-service payload helpers:

- GM-visible keep / secret / campaign-scoped objects and relationships;
- PLAYER-admissible subset that must never leak `obj:alpha-secret`, `Hidden Cache`, or `Traitor's Keep`;
- broken provenance object for fail-closed evidence;
- seeded source artifacts/revisions for anchor emit/revalidate and binding integrity.

Write/governance cases use existing Gatewatch publication conformance seeds, reviewed-first-world initialization fixtures, and the checked-in Eldyrwild sealed adoption bundle (`tests/fixtures/dungeonmind_dnd/eldyrwild_existing_world_adoption_bundle_v2.json`). No live Eldyrwild access; no fabricated Eldyrwild-like substitute.

## 3. Operation coverage matrix

| Operation ID | Family | Status | Semantic digest prefix |
|---|---|---|---|
| `failure.missing_head` | failure | error | `4e1dd3be2e3c…` |
| `failure.missing_object` | failure | miss | `8746e23c7d89…` |
| `failure.missing_revision` | failure | error | `422ee55f4e98…` |
| `failure.provenance_invalid_fail_closed` | failure | ok | `317f7a72af70…` |
| `read.deterministic_search` | read | ok | `40327d5274af…` |
| `read.evidence` | read | ok | `a7c1db77f1b1…` |
| `read.exact_historical_revision` | read | ok | `2c4e67cfb51a…` |
| `read.exact_object` | read | ok | `aaa6431ce0db…` |
| `read.head_projection` | read | ok | `2c4e67cfb51a…` |
| `read.neighborhood.depth_1` | read | ok | `a49f20080078…` |
| `read.neighborhood.depth_2` | read | ok | `92e37de7f45c…` |
| `read.source_anchor.emit` | read | ok | `1fdfc5310045…` |
| `read.source_anchor.revalidate` | read | ok | `fae34d0f56a0…` |
| `scope.cross_campaign` | scope | ok | `0583aef7800b…` |
| `scope.gm_campaign` | scope | ok | `2c4e67cfb51a…` |
| `scope.player_campaign` | scope | ok | `04d29f7f3b0c…` |
| `scope.world_owned` | scope | ok | `ebd76976d7a2…` |
| `write.correction_or_retraction` | write | ok | `0ba1bf07688b…` |
| `write.exact_parent_publication` | write | ok | `cdae138f067f…` |
| `write.exact_replay_idempotency` | write | ok | `0b6f05e863db…` |
| `write.outcome_unknown_recovery` | write | error | `a5ab3ace96fd…` |
| `write.reviewed_first_world_initialization` | write | ok | `c86d08d911c7…` |
| `write.source_evidence_binding_integrity` | write | ok | `48409ca17ffe…` |
| `write.stale_parent_rejection` | write | error | `bf26c62b306f…` |

All 24 required operation IDs are present exactly once. Aggregate digest is over sorted operations only.

## 4. Write / governance semantics frozen

| Case | Mechanism frozen at base |
|---|---|
| Reviewed first-world init | `initialize_reviewed_world` receipt + published revision identity |
| Exact-parent publication | Gatewatch finalized-review publish |
| Exact replay | Second publish returns same published revision |
| Stale parent | `StaleParentRevisionError` after competing writer |
| Outcome-unknown recovery | `FinalizedReviewPublicationOutcomeUnknownError` via post-publish + failed recovery probe |
| Correction / retraction | Eldyrwild source-classification repair (`ExistingWorldAdoptionReceiptV4`) after intentional membership corruption |
| Source/evidence binding | Admitted object retains evidence refs / anchors at head |

## 5. Historical compatibility evidence

| Stored schema / obligation | Reader path | Digest prefix |
|---|---|---|
| `dm_union_graph_v1` | `VersionedUnionGraphSnapshotReader.parse v1` | `b378bae1ffe0…` |
| `dm_union_graph_v2` | `VersionedUnionGraphSnapshotReader.parse v2` | `367fe6682646…` |
| `dm_union_graph_v3` | `VersionedUnionGraphSnapshotReader.parse gatewatch-world-graph-v3.json` | `02cac24e37bf…` |
| `dm_union_graph_v4` | `VersionedUnionGraphSnapshotReader.parse v4` | `4b446069d51b…` |
| `dm_union_graph_v5` | `VersionedUnionGraphSnapshotReader.parse v5` | `5b1ba59395e6…` |
| `dm_union_graph_v6` | `VersionedUnionGraphSnapshotReader.parse synthetic v6 witness payload` | `dee8782531bf…` |
| `dm_existing_world_adoption_bundle_v2` | `adopt_existing_world(eldyrwild_…_bundle_v2.json)` | `a03f67a23d69…` |
| `dm_existing_world_adoption_repair` | `repair_existing_world_adoption_source_classification` | `904c1836b6c6…` |
| `dm_reviewed_world_initialization_v1` | `initialize_reviewed_world + get_for_world` | `c08c346cf8e8…` |

No historical schema was rewritten into a newer schema before parsing. Profiles required for historical payloads (dnd5e v1–v3 + `test.kernel`) are loaded into the witness reader registry.

## 6. Normalization exclusions

Policy id: `k0_semantic_normalization_v1`.

- **SEMANTIC:** identity, scope/admissibility, revision/object/evidence/binding fields, dispositions, fail-closed markers.
- **OBSERVATION_ONLY (dropped):** `projected_at`, `*_at` wall clocks, duration/elapsed, traces, cache hits, etc.
- **FORBIDDEN:** absolute paths, DSNs, wall-clock equality keys, process/trace ids.

Unit proof: mutating observation-only fields does not change digest; mutating semantic fields does. Validator rejects missing/duplicate operation IDs and forbidden nondeterministic fields.

## 7. In-memory vs PostgreSQL parity

Focused lane: `tests/integration/test_k0_semantic_witness_postgres.py`.

- Disposable Postgres via compose port `54329`.
- Same scenario runner; adapter-neutral operation aggregate digest equals checked-in golden.
- Write/governance and Eldyrwild historical repair lanes remain on the in-memory reference adapters so adapter-private corruption seams do not invent a second golden.
- Read/projection/retrieval path for the synthetic world executes against PostgreSQL stores.

Result: focused PostgreSQL witness **green**; aggregate digest matches `sha256:1e43340fc00eac54c0c52378e0e879fd42ff87c6aabcb082b59b47ef12767906`.

## 8. Acceptance gates executed

| Gate | Result |
|---|---|
| A. No runtime/schema/dependency diff vs `3b52a81…` | PASS |
| B. Deterministic golden `cmp` | PASS |
| C. Focused witness + import-boundary unit tests | PASS |
| D. `ruff check .`, `pyright`, `pytest -m "not integration"` | PASS |
| E. Focused PostgreSQL witness parity + full `pytest -m integration` | PASS |
| F. Historical v1–v6 + Eldyrwild adoption/repair + reviewed-init | PASS |
| G. Golden self-check / validator rejects | PASS (unit coverage) |
| H. Known `benchmark-smoke` baseline unchanged | PASS (still red; same constructor defect) |
| I. Formal steward review | PENDING (PR) |

Reconfirmed `benchmark-smoke`:

```text
TypeError: WorldGraphProjectionService.__init__() missing 1 required keyword-only argument:
'reviewed_world_initializations'
```

in `benchmarks/world_graph_reads.py`. Not repaired in K0.2.

## 9. Baseline defects / unknowns not repaired

1. **`benchmark-smoke` constructor drift** — pre-existing; separate corrective slice.
2. **Write/historical lanes are memory-reference under the PostgreSQL parity job** — intentional so the single golden stays adapter-comparable; read-path parity is the PostgreSQL proof surface.

## 10. Inheritance statement

This checked-in witness is the inherited **K2.5 equality oracle** for World authority semantics after later demolition/refactor. Re-run:

```bash
uv run python scripts/k0_semantic_witness.py --adapter memory --output /tmp/witness.json
cmp Docs/Reports/K0-golden-semantic-witness-v1.json /tmp/witness.json
```

K0.2 does **not** prove:

- performance or latency budgets (K0.3);
- demolition eligibility beyond K0.1 dispositions (K1);
- Buddy consumer behavior changes;
- live Eldyrwild database correctness beyond the sealed checked-in bundle.

## 11. Formal review telemetry

| Cycle | Lens | Outcome |
|---|---|---|
| 1 | Coverage / historical authenticity / adapter parity / PLAYER secrecy self-check | Required ops present; v1–v6 parse without rewrite; Eldyrwild sealed bundle used; PLAYER tokens absent; PG aggregate matches golden |

Steward PASS review identifier: **pending** after PR open.
