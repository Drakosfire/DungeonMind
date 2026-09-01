# Report — 2026-08-31 K0.2 golden semantic witness

**Status:** deterministic World-authority semantic oracle for K2.5 inheritance; no runtime behavior change  
**Artifact:** [`K0-golden-semantic-witness-v1.json`](K0-golden-semantic-witness-v1.json)  
**Schema:** `dm_k0_semantic_witness_v1`  
**Predecessor:** PR #48 / [`REPORT-2026-08-30-k0-current-consumer-public-surface.md`](REPORT-2026-08-30-k0-current-consumer-public-surface.md) / [`K0-surface-inventory.json`](K0-surface-inventory.json)  
**Formal review cycles:** 2 (implementation self-check; review `5072176246` CHANGES REQUIRED → all items addressed); steward PASS review ID pending PR #49 re-review

This witness freezes meaning, not wall-clock cost. Observation-only fields never participate in golden equality. K0.2 does **not** authorize demolition, performance claims, or Buddy pin movement.

## 1. Exact implementation base and inputs

```text
dungeonmind_landed_base_sha       = e5fb104708f979b0ebb481ee925db4beb22e2bfe
dungeonmind_base_tree_sha         = 3b52a81a6c113ac6bfb4d1b0fa7fa78246aa31f1
k0_inventory_schema               = dm_k0_surface_inventory_v1
k0_inventory_digest               = sha256:1154b0fb9ce4d0845782aaaff0d9ad901920633bb940d2e0514925a274214358
fixture_digest                    = sha256:2471a03792fa9f65591368ad06ad7947548dd0a15f28f1ba99e39a05f3bd0a57
normalization_policy_digest       = sha256:573ca3b9c77c5ece7a81f39bef6e0ea7934f8926e66849f86e7e623337d10adc
witness_schema                    = dm_k0_semantic_witness_v1
aggregate_semantic_sha256         = sha256:928d459288e208cf37f11ca63fac426c5f338d2f531292ebefa8118071fdd9fa
canonical_adapter                 = memory
```

Anchor bookkeeping: GitHub reports the landed PR #49 base as merge commit `e5fb104…`; its first parent `3b52a81…` has an identical tree and is the revision the diff gates pin. Both are recorded in witness `inputs` and fail-closed validated.

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

Small governed v6 world (`world:test`) reused from proven retrieval-service payload helpers, published as two revisions:

- an **ancestor revision** (tavern/gate/keep only) pinned by `read.exact_historical_revision`;
- a **head revision** adding the GM-only secret, the campaign-B object, and the broken-provenance object.

Fixture contents:

- GM-visible keep / secret / campaign-scoped objects and relationships;
- PLAYER-admissible subset that must never leak `obj:alpha-secret`, `Hidden Cache`, or `Traitor's Keep`;
- broken provenance object for fail-closed evidence;
- seeded source artifacts/revisions for anchor emit/revalidate and binding integrity.

Write/governance cases use existing Gatewatch publication conformance seeds, reviewed-first-world initialization fixtures, and the checked-in Eldyrwild sealed adoption bundle (`tests/fixtures/dungeonmind_dnd/eldyrwild_existing_world_adoption_bundle_v2.json`). No live Eldyrwild access; no fabricated Eldyrwild-like substitute.

## 3. Operation coverage matrix

| Operation ID | Family | Status | Semantic digest prefix |
|---|---|---|---|
| `failure.missing_head` | failure | error | `75bdddfd80c8…` |
| `failure.missing_object` | failure | miss | `57e6e4f76b63…` |
| `failure.missing_revision` | failure | error | `f4e98df46911…` |
| `failure.provenance_invalid_fail_closed` | failure | ok | `36d9a828e4c6…` |
| `read.deterministic_search` | read | ok | `e2ec94946495…` |
| `read.evidence` | read | ok | `89789fb623db…` |
| `read.exact_historical_revision` | read | ok | `fb9e7997b807…` |
| `read.exact_object` | read | ok | `093697b0faf7…` |
| `read.head_projection` | read | ok | `0dadd9970565…` |
| `read.neighborhood.depth_1` | read | ok | `b5d0f44513d2…` |
| `read.neighborhood.depth_2` | read | ok | `a8bb294d2e4e…` |
| `read.source_anchor.emit` | read | ok | `ac204f647d1c…` |
| `read.source_anchor.revalidate` | read | ok | `29c99822c579…` |
| `scope.cross_campaign` | scope | ok | `09a5d9bdbb2e…` |
| `scope.gm_campaign` | scope | ok | `0dadd9970565…` |
| `scope.player_campaign` | scope | ok | `db077617e03c…` |
| `scope.world_owned` | scope | ok | `ca281d6ddbe2…` |
| `write.correction_or_retraction` | write | ok | `7688bb4c3109…` |
| `write.exact_parent_publication` | write | ok | `f067f63ea120…` |
| `write.exact_replay_idempotency` | write | ok | `863db0f9ff27…` |
| `write.outcome_unknown_recovery` | write | error | `da3689a68e6e…` |
| `write.reviewed_first_world_initialization` | write | ok | `911c749b2cc6…` |
| `write.source_evidence_binding_integrity` | write | ok | `663a9336f665…` |
| `write.stale_parent_rejection` | write | error | `0549a839ba5f…` |

All 24 required operation IDs are present exactly once. Aggregate digest is over sorted operations only. `read.exact_historical_revision` pins the non-head ancestor (3 admitted objects) and differs from `read.head_projection` (4 admitted objects); both neighborhood reads run as PLAYER and record `player_traversal_fail_closed` against the GM-only seed neighbor.

## 4. Write / governance semantics frozen

| Case | Mechanism frozen at base |
|---|---|
| Reviewed first-world init | `initialize_reviewed_world` receipt + published revision identity |
| Exact-parent publication | Gatewatch finalized-review publish |
| Exact replay | Second publish returns same published revision |
| Stale parent | `StaleParentRevisionError` after competing writer (head rolled back afterward) |
| Outcome-unknown recovery | `FinalizedReviewPublicationOutcomeUnknownError` via post-publish + failed recovery probe, then durable recovery: re-publish replays the durable record without rematerialization |
| Correction / retraction | Eldyrwild source-classification repair (`ExistingWorldAdoptionReceiptV4`) after intentional membership corruption via an adapter-private seam (memory + PostgreSQL implementations) |
| Source/evidence binding | Object admitted by the governed reviewed-init publication retains evidence refs / anchors resolved against governed sources |

All write/governance operations execute against the active adapter's repositories — in-memory for the canonical golden, PostgreSQL under the parity lane.

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
| ADR-0023 `OTHER`-stamped D0 / `GenesisEvidenceCompatibility` | #645-family init → projection admits via compatibility; raw D0 stays `OTHER`; corrected command replays to same receipt; non-family `OTHER` fail-closed | `93d5fc82e47d…` |

No historical schema was rewritten into a newer schema before parsing. Profiles required for historical payloads (dnd5e v1–v3 + `test.kernel`) are loaded into the witness reader registry. The historical case set is fail-closed: the validator requires each `case_id` above exactly once.

## 6. Normalization exclusions

Policy id: `k0_semantic_normalization_v1`.

- **SEMANTIC:** identity, scope/admissibility, revision/object/evidence/binding fields, dispositions, fail-closed markers.
- **OBSERVATION_ONLY (dropped):** exact-match allowlist (`projected_at`, `created_at`, `updated_at`, duration/elapsed, traces, cache hits, etc.). Undeclared `_at`-suffixed keys are **retained** by normalization and **flagged** by the forbidden-field guard.
- **List order is preserved** — contractual ranking/order drift participates in equality; unordered id sets are sorted at the extraction site instead.
- **FORBIDDEN:** absolute paths, DSNs, wall-clock equality keys, process/trace ids.

Unit proof: mutating observation-only fields does not change digest; mutating semantic fields (including list reordering) does. Validator rejects missing/duplicate operation IDs, missing/duplicate historical case IDs, forbidden nondeterministic fields, and any tampering with declared base SHAs, K0 inventory digest, fixture digest, or normalization-policy digest.

## 7. In-memory vs PostgreSQL parity

Focused lane: `tests/integration/test_k0_semantic_witness_postgres.py`.

- Disposable Postgres via compose port `54329`.
- Same scenario runner; **all** required operations — read, write, and governance — execute against PostgreSQL repositories, including the adapter-private Eldyrwild corruption seam and the durable outcome-unknown recovery replay.
- Aggregate digest over all adapter-neutral operations equals the checked-in golden.

Result: PostgreSQL witness **green**; aggregate digest matches `sha256:928d459288e208cf37f11ca63fac426c5f338d2f531292ebefa8118071fdd9fa`.

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
| 2 | Steward review `5072176246` (CHANGES REQUIRED) | All 8 findings + anchor bookkeeping addressed: ancestor-pinned historical read; PLAYER neighborhood fail-closed proof; full PostgreSQL write/governance parity; ADR-0023 `OTHER`-stamped D0 case; durable outcome-unknown recovery; governed binding-integrity path; order-preserving exact-match normalization; fail-closed validator over declared inputs + historical case set |

Steward PASS review identifier: **pending** after PR update.
