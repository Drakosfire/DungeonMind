# DungeonMind — Independent Library Roadmap

**Status:** current forward roadmap  
**Updated:** 2026-08-24  
**Current library head at sync:** `519b2c96fc42d22f3113cc9ca0d48bc70b6780e5`  
**First real consumer proof:** DungeonMindBuddy #631 merged at `ffc39ab394ea55b00dc8b2a0fd41be0448635600`

This roadmap is intentionally forward-looking. The founding A/B PR ladder and detailed cutover chronology remain available in Git history, ADRs, reports, and merged PRs; they are no longer the canonical way to understand what DungeonMind should become next.

## North star

DungeonMind should be a small, trustworthy, extensible library for durable world knowledge.

A good end state is:

```text
client product
  ├─ UI / documents / work context
  ├─ agent harness (optional)
  └─ other product tools
          │
          ▼
     DungeonMind API
          │
          ├─ exact revisions
          ├─ scoped/admissible graph reads
          ├─ evidence + anchors
          └─ governed publication
          │
          ▼
       durable stores
```

DungeonMind should not grow product or harness responsibilities merely because its first consumer is agentic.

## What is already achieved

### Foundation — DONE

- versioned contracts and repository ports;
- in-memory and PostgreSQL adapters;
- immutable World Graph revisions and explicit head CAS;
- source/evidence provenance;
- derived semantic-index model;
- semantic-profile identity boundary plus D&D profile package;
- governed contribution review/materialization/publication;
- exact replay/recovery semantics.

### Real-world authority adoption — DONE

Eldyrwild was adopted into DungeonMind/PostgreSQL as a living authority. The original adopted state remains historically sealed; the single accepted V4 source-classification repair preserves M0 and records sanctioned M1 rather than rewriting history.

A post-adoption child revision was published through the normal governed path, proving DungeonMind owns living graph authority rather than only imported snapshots.

### Native current-client read contract — DONE

R.1/R.2 expose transport-neutral native projection/retrieval services.

DungeonMindBuddy R.3 proved the current-client contract against the real adopted world:

- exact head and historical revision reads;
- campaign and cross-campaign scope;
- GM and PLAYER;
- object lookup;
- deterministic search/referent resolution;
- depth-1/depth-2 neighborhood;
- evidence;
- source-anchor emit/revalidate;
- explicit fail-closed behavior.

The final supported-contract witness recorded 0 unresolved blocking semantic differences and 0 supported-operation errors. Historical Buddy-kernel differences are no longer the acceptance oracle.

## Current lane

### R.3a — Native World Graph read optimization — THIS PR

**Owner:** DungeonMind  
**Goal:** make the accepted native read seam fast enough for direct production consumption without changing its meaning.

This PR implements the named order: one `WorldGraphReadContext`, coherent
`SourceProvenanceSnapshot`, per-context evidence memo, and service-local
parsed-revision reuse. Public R.1/R.2 contracts are unchanged. There is no
scoped cross-request cache and no search/anchor index.

Live Eldyrwild campaign-GM projection (same V4 identity as the R.3 direct
witness): **20,739 ms → 89 ms warm (233×)**. Every R.2a synthetic digest at
100 / 1k / 5k / 10k still matches. Durable record:
[`Docs/Benchmarks/BASELINE-world-graph-reads-r3a.md`](../Benchmarks/BASELINE-world-graph-reads-r3a.md).
Handoff:
[`Docs/Handoffs/HANDOFF-cutover-direct-read-optimization.md`](../Handoffs/HANDOFF-cutover-direct-read-optimization.md).

Safety constraint (still binding):

> A scoped/admissible projection may not be cached across requests by graph revision/scope alone. Source/provenance state participates in admission and may change while the graph revision remains fixed.

R.3a regression oracle:

```text
R.3 supported-contract direct result == R.3a optimized direct result
```

Disposition: `R3A_OPTIMIZED`, `SWITCH_NOT_READY`. R.3a does not flip a
DungeonMindBuddy rollout flag and does not delete Buddy code. The next
proof is a small Buddy pin + rerun of the merged R.3 witness.

## Next library lanes

### L.1 — Architecture fitness and simplification — READY after R.3a characterization

Purpose: determine what complexity the independent library has actually earned.

For each subsystem record:

- named consumer;
- library ownership rationale;
- correctness value;
- runtime/conceptual/maintenance cost;
- extension evidence.

Classify:

- essential complexity;
- productive abstraction;
- unproven abstraction;
- accidental complexity;
- historical residue.

Highest-priority scrutiny:

- founding-era MindTurn orchestration;
- retrieval-session/thread ownership;
- context assembly and budgeting;
- claim ledger / answer validation;
- `agents/` adapter machinery;
- semantic-document/embedding machinery relative to current consumers;
- duplicate generations of contracts/services retained only because of the founding sequence.

Allowed outcomes include deletion, collapse, migration to a client, or explicit retention.

The purpose is not to make the codebase small by taste. It is to make complexity answerable to evidence.

### L.2 — Independent client ergonomics proof — READY after stable optimized read seam

Build the smallest non-Buddy consumer that can naturally:

```text
select world
→ read head
→ search
→ get object
→ neighborhood
→ evidence
→ anchor revalidation
```

Prefer a tiny CLI/example/library consumer over another product.

Measure:

- DungeonMind concepts the client must understand;
- configuration needed;
- imports/dependencies required;
- whether internal contracts leak;
- whether an exact operation can be expressed without product-specific knowledge.

Success means DungeonMind feels like a library, not "Buddy extracted into another repo."

### L.3 — Public library contract consolidation — READY after L.1/L.2 evidence

Use the architecture-fitness and second-client evidence to decide what is intentionally public and stable.

Potential work:

- tighten exported application entry points;
- document stable error vocabulary;
- make optional transports clearly subordinate to application services;
- deprecate or quarantine founding/demo APIs that are not part of the long-term library;
- reduce duplicate contract generations only where historical revision support allows it.

Do not perform broad API cleanup before the evidence identifies which surfaces matter.

### L.4 — Extensibility proof through semantic profiles — DEFERRED until concrete pressure

The generic/profile split is structurally clean and has a synthetic non-D&D canary, but real multi-system value is not yet proven.

When a concrete second profile/use case appears, measure:

- generic-kernel files changed;
- generic contracts changed;
- profile-only files changed;
- migrations required;
- retrieval/publication behavior changed.

A successful profile extension should mostly remain profile-side.

Do not build cross-profile taxonomy/reasoning before a real consumer requires it.

### L.5 — Retrieval/index maturation — EVIDENCE-GATED

R.2a showed lexical search and anchor derivation have graph-size-dependent secondary cost. R.3a removed repeated projection/provenance work; live Eldyrwild projection is no longer dominated by per-evidence source round-trips. Synthetic search still pays graph-size lexical work on top of projection.

Only if remeasurement shows a remaining product problem should DungeonMind add:

- search indexes;
- anchor-supporter indexes;
- incremental parsing/materialization;
- broader cache layers.

Every new index is derived state, never knowledge authority.

### L.6 — Packaging and operational maturity — READY when library surface settles

Possible work:

- clean package/extras story;
- release/versioning policy for public contracts;
- compatibility/deprecation policy;
- migration/runbook hardening;
- production observability/SLO decisions based on measured use;
- deployment guidance while preserving operator ownership of infrastructure lifecycle.

This lane is not an excuse to add a platform service before embedded/library use proves insufficient.

## External integration milestones — tracked, but not library roadmap owners

DungeonMindBuddy still has external cutover work after this R.3a PR:

```text
pin optimized DungeonMind
→ reuse long-lived native read services
→ rerun R.3 semantic/performance witness
→ record SWITCH_READY or SWITCH_NOT_READY
→ only then explicitly enable native direct reads
→ retire hydrated Buddy read bridge
→ delete legacy Buddy graph runtime
```

Those are important proof points for DungeonMind, but the implementation belongs to DungeonMindBuddy. DungeonMind should not absorb Buddy rollout flags, UI behavior, product source opening, or agent harness logic to make that integration easier.

## Explicit non-goals

Until evidence changes the decision, DungeonMind does not roadmap:

- an agent harness;
- Hermes/Pi/model-provider integration;
- product prompt/context orchestration;
- UI surfaces;
- product-local document state;
- generic source-body storage/opening;
- distributed cache infrastructure;
- semantic/vector search as authority;
- generic multi-game interpretation;
- compatibility with retired Buddy-kernel semantics;
- a second graph per campaign.

## Optimization principle

Optimization means reducing total system cost while preserving valuable capability.

DungeonMind optimization therefore includes:

- runtime cost;
- memory and database cost;
- conceptual cost;
- maintenance cost;
- client integration cost;
- boundary leakage.

Prefer measured simplification over speculative flexibility.
