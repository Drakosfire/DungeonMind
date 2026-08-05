# HANDOFF — FT1a revision-pinned fictional-time query

**Status:** ACTIVE  
**Implementation base:** `56d7263950a406d2fff88fc8d1bf77a85ab72abf`  
**Branch:** `timeline/ft1a-revision-pinned-fictional-time-query`

## 0. Mission

Deliver FT1a: durable fictional-time **claim contracts**, a **revision-pinned query evaluator**, and conformance proofs that binding, abstention, and deterministic proofs hold on the Hempholm/Lysandra two-case graph derived from FT0 pins.

Shadow authority only. No graph writes, no migrations, no new providers, no `temporal_scope` coupling.

## 1. Scope allowlist

**Create:** `contracts/fictional_time.py`, `application/fictional_time.py`, fixtures, conformance tests, this handoff.

**Modify:** `contracts/__init__.py`, `application/__init__.py`, `domain/errors.py` (`FictionalTimeIntegrityError` only).

**Out of scope:** `contribution.temporal_scope`, graph/review materialization, DnD packages, service/infrastructure/agents, FT0 fixture, characterization tests, README/ADR/pyproject.

## 2. Line ceilings

| Path | Max nonblank lines |
|------|-------------------|
| `contracts/fictional_time.py` | 300 |
| `application/fictional_time.py` | 325 |
| `test_fictional_time_query.py` | 525 |
| each FT1 fixture | 250 |

## 3. Architecture

```
StoredGraphRevision + FictionalTimeClaimBundle + FictionalTimeQuery
        │                      │                         │
        └──────── evaluate_fictional_time_query ─────────┘
                              │
                    FictionalTimeQueryResult
```

Evaluator reload-validates inputs, recomputes payload digest, verifies bundle↔revision binding, parses snapshot via injected `GraphSnapshotReader`, verifies anchor objects and evidence JSON equality, then evaluates query semantics.

## 4. Patterns

- `DungeonMindModel` / `extra="forbid"`
- Reuse `EvidenceRef`, `StoredGraphRevision`, `canonical_sha256`, `compute_revision_id`
- `FictionalTimeIntegrityError` with sanitized `details` (machine ids only)
- Tests use `UnionGraphV1SnapshotReader` only

## 5. Nano-commits

1. `feat(timeline): add fictional-time claim contracts`
2. `feat(timeline): add revision-pinned query evaluator`
3. `test(timeline): prove binding abstention and deterministic proofs`

## 6. Contracts (`dm_fictional_time_*_v1`)

### 6.1 Schemas

- `dm_fictional_time_claim_bundle_v1`
- `dm_fictional_time_query_v1`
- `dm_fictional_time_query_result_v1`

### 6.2 Enums

`FictionalTimeAuthorityMode` (shadow), `FictionalTimeQueryKind` (strict_before | state_at_boundary | absolute_fictional_time), `FictionalTimeBoundaryPosition`, `FictionalTimeResultStatus`, `FictionalTimeUnresolvedReason`.

### 6.3 Anchor

`anchor_id`, `label`, `related_object_ids` (nonempty unique). **No** absolute time field.

### 6.4 Claims

- **StrictBefore:** `claim_id`, `before_anchor_id`, `after_anchor_id`, `evidence_ref_ids` (nonempty unique).
- **StateBoundary:** `claim_id`, `state_id`, `boundary_anchor_id`, `before_value`, `after_value`, side-specific evidence lists (nonempty unique); `before_value != after_value`.

### 6.5 Bundle

Binds `world_id`, `campaign_id`, `authority_mode=shadow`, `graph_schema`, `graph_revision_id`, `graph_payload_sha256` (64 lowercase hex), anchors (nonempty), claims, `evidence_refs` (nonempty).

Reject: duplicate ids, dangling refs, unused evidence, self-edges, duplicate ordered pairs, directed cycles, unchanged boundaries, duplicate `(state_id, boundary_anchor_id)`, non-shadow authority, empty total claims, blank strings.

### 6.6 Query

Kind-specific fields present; other kind fields **absent** (`None`).

### 6.7 Integrity error

`FictionalTimeIntegrityError` reasons: `revision_reload_validation`, `bundle_reload_validation`, `query_reload_validation`, `graph_payload_digest_mismatch`, `revision_binding_mismatch`, `graph_snapshot_validation`, `anchor_object_not_found`, `evidence_binding_mismatch`.

Never leak labels, locators, URIs, prose, or payloads in `details`.

### 6.8 Query result

- **entailed / contradicted:** bool `value`, nonempty `proof_claim_ids`, sorted `evidence_ref_ids`, `reason=null`.
- **unresolved:** `value=null`, empty proof/evidence, non-null `reason`.
- Always copy binding fields from verified bundle; `authority_mode=shadow`.

## 7. Query semantics

### 7.1 strict_before

Same anchor → `same_anchor_irreflexive`. Unknown anchor → `unknown_anchor`. Path A→B → entailed/true; B→A → contradicted/false; else `no_ordering_path`. Proof = shortest positive-length path; tie-break claim-id lex order. Evidence = sorted union of path claim evidence. Irreflexive: start==goal yields no path.

### 7.2 state_at_boundary

Unknown anchor → `unknown_anchor`. No `(state_id, boundary_anchor_id)` → `no_matching_state_boundary`. Else entailed with side value/evidence; proof = `[claim_id]`.

### 7.3 absolute_fictional_time

Unknown anchor → `unknown_anchor`. Known anchor without explicit absolute → `no_explicit_absolute_anchor` (never invent from metadata/locators).

## 8. Handback stub

**TODO (future FT1b+):** wire bundle ingestion, promotion from shadow, graph publication of fictional-time claims, planner/retrieval surfacing. This handoff completes contracts + evaluator + conformance only.

## 9. Verification

```bash
uv run pytest -q tests/conformance/test_fictional_time_query.py
uv run ruff check src/dungeonmind/contracts/fictional_time.py \
  src/dungeonmind/application/fictional_time.py \
  tests/conformance/test_fictional_time_query.py
```

Conformance E1–E14: schemas, bundle matrix, binding errors, gold queries, edge cases, determinism, sanitization, import boundaries, line ceilings.

---

## Appendix A — Gold queries (two-case)

| query_id | kind | expected |
|----------|------|----------|
| `query:hempholm-tree-before-beetles` | strict_before | entailed/true; proof `[claim:hempholm-tree-before-revelry, claim:hempholm-revelry-before-beetles]`; evidence sorted hempholm evs |
| `query:hempholm-tree-absolute-time` | absolute_fictional_time | unresolved/`no_explicit_absolute_anchor` |
| `query:lysandra-returned-before-gate` | state_at_boundary immediately_before | entailed/false; proof `[state-boundary:lysandra-returned-at-mireward-gate]`; evidence `[ev:lysandra-not-home-c1-c2]` |
| `query:lysandra-returned-after-gate` | state_at_boundary immediately_after | entailed/true; same proof; evidence `[ev:lysandra-mireward-gate-arrival]` |

## Appendix B — Fixture pins

**Graph revision:** `world:ft1-fictional-time`, `dm_union_graph_v1`, objects `obj:hempholm-tree`, `obj:hempholm-revelry`, `obj:hempholm-root-beetle-attack`, `obj:lysandra-ironveil`, `obj:mireward-gate`. Five `dm_evidence_ref_v1` rows from FT0 IDs. Arrival anchor binds lysandra + mireward-gate.

**Bundle:** `bundle:ft1-two-case-v1`, `campaign:ft1-two-case`, shadow authority, two strict-before claims + one state boundary. No gold answers, no source_manifest.

## Appendix C — FT0 lineage

Evidence source artifacts derive from FT0 pins (`src:hempholm-session-04`, `src:lysandra-mireward-history`, `src:mireward-session-22`). Locators may contain session-like strings for leakage tests; they are **never** occurrence time.
