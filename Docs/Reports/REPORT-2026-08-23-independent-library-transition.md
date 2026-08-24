# Report — DungeonMind after the first real cutover

**Date:** 2026-08-23  
**Purpose:** achievement reflection, architecture-fitness baseline, and forward evidence ledger for DungeonMind as an independent library  
**DungeonMind sync base:** `519b2c96fc42d22f3113cc9ca0d48bc70b6780e5`  
**External consumer proof:** DungeonMindBuddy #631 merge `ffc39ab394ea55b00dc8b2a0fd41be0448635600`

## 1. What changed

DungeonMind began as a deliberate extraction of architecture that had been discovered inside DungeonMindBuddy. At founding, many important properties were still claims: that one World Graph could be independently authoritative, that product surfaces could consume it without owning it, that semantic profiles could keep D&D meaning outside the generic kernel, and that governed publication could survive a real migration.

The Eldyrwild cutover changed the evidence quality.

DungeonMind now has:

- a real adopted world in PostgreSQL;
- immutable historical graph revision identity;
- a living explicit head;
- a governed post-adoption child publication;
- source/evidence provenance as part of read admission;
- an accepted V4 repair mechanism that preserved historical M0 and sanctioned M1 rather than rewriting migration history;
- a native current-client read API exercised by an external product;
- a client contract that prefers DungeonMind semantics over historical Buddy implementation residue.

This is the important achievement:

> DungeonMind is no longer merely "the architecture we want Buddy to move toward." It has become a separate knowledge authority that Buddy can consume.

## 2. What the cutover taught us

### The authority boundary is real

Several R.3 disagreements were resolved by accepting DungeonMind semantics and adapting the client rather than recreating old Buddy behavior.

That is positive evidence. If every difference had required compatibility restoration, DungeonMind would have been an extracted implementation detail rather than an independent library.

### Evidence/provenance is not decoration

The largest semantic disagreement came from DungeonMind's per-evidence-chain fail-closed admission versus Buddy's older coarser behavior. The accepted client contract retained DungeonMind's stricter rule.

This demonstrates that source/evidence state is part of the library's knowledge semantics.

It also explains an important optimization constraint: immutable graph revision identity does not by itself freeze source visibility/lifecycle/revision validity.

### Exact revision identity paid for itself

The cutover exercised current head, historical D_A, and a legacy-A→D_A bridge. Publicly returned DungeonMind revisions are exact and re-pinnable.

Revision identity is therefore essential complexity, not speculative infrastructure.

### Governed repair paid for itself

The V3→V4 source-classification incident could have been "fixed" by rewriting history. DungeonMind instead added a narrow auditable repair aggregate preserving M0 and recording M1.

That is meaningful complexity: it prevented a real integrity failure during migration.

### The generic/profile boundary survived real D&D data

The living Eldyrwild graph uses a D&D semantic profile while generic graph revision, projection, retrieval, provenance, and publication behavior remains in the kernel.

This is evidence for a productive abstraction, though real second-system support remains unproven.

### Native reads are currently too expensive

The real-world R.3 witness measured approximately:

```text
hydrated compatibility projection  1.69 s
direct DungeonMind projection     20.73 s
```

R.2a already showed repeated full projection as the structural cost floor at synthetic scale.

This does not yet prove the architecture is fundamentally overcomplicated. The likely first explanation is repeated parse/provenance/projection work with no coherent reusable read context. R.3a is the experiment that distinguishes an implementation problem from a deeper architectural cost.

## 3. Current architecture hypothesis

The strongest evidence supports this core:

```text
DungeonMind
  durable world/source/evidence identity
  immutable graph revisions + head
  semantic-profile identity/admission
  scope + admissibility
  projection + graph retrieval
  anchors
  governed contribution/review/publication
```

The agent harness belongs outside:

```text
DungeonMindBuddy / client
  product work context
  documents + selected text
  UI surfaces
  model/provider selection
  prompts
  tool loop
  retries / approvals
  conversation state
  context budget across tools
```

See ADR-0022.

## 4. Architecture-fitness ledger

This ledger begins now and should be updated after R.3a, the first non-Buddy client probe, and the first meaningful post-cutover product extension.

| Mechanism | Current evidence | Provisional class | Next evidence |
| --- | --- | --- | --- |
| Immutable graph revisions + explicit head | exercised by adoption, publication, exact pins | ESSENTIAL COMPLEXITY | continue operational use |
| Source/evidence provenance admission | decided real R.3 semantic differences; prevented leakage | ESSENTIAL COMPLEXITY | R.3a source-freshness proof |
| Governed contribution review/publication | published living post-adoption child revision | ESSENTIAL COMPLEXITY | normal future authoring use |
| V4 adoption repair aggregate | resolved a real migration integrity incident without rewriting history | ESSENTIAL, SPECIALIZED | no generalization unless a second incident demands it |
| Semantic-profile boundary | D&D data remains outside generic kernel; synthetic non-D&D canary exists | PRODUCTIVE ABSTRACTION | concrete second profile/use case |
| Native projection/retrieval API | accepted by first real external client | ESSENTIAL / PRODUCTIVE | second-client ergonomics probe |
| Repeated full parse/projection per operation | dominant measured latency | ACCIDENTAL COMPLEXITY candidate | R.3a before/after phases |
| Cross-request scoped projection cache | not implemented; unsafe by graph revision alone | DO NOT ADD WITHOUT EVIDENCE | source-state identity proof if ever needed |
| Search/anchor indexes | secondary costs measured but not yet dominant target | UNPROVEN OPTIMIZATION | remeasure after R.3a |
| MindTurn orchestration | founding/demo usage; not needed for R.3 graph client contract | UNPROVEN LIBRARY OWNERSHIP | architecture-fitness audit + second client |
| Retrieval-session/thread persistence | founding MindTurn continuity; not required by direct graph API | UNPROVEN LIBRARY OWNERSHIP | identify named independent consumers |
| Context assembly / budgeting | useful to an agentic product, but harness boundary now client-owned | LIKELY CLIENT CONCERN | audit before deletion/move |
| Claim ledger / answer validation | no current evidence in the graph cutover | UNKNOWN | inventory consumers/tests |
| `agents/` adapter layer | harness explicitly client-owned | HISTORICAL/EXAMPLE candidate | inventory then retain/quarantine/delete |
| Semantic documents / embedding runs / pgvector retrieval | substantial founding implementation; current real client primarily exercises graph retrieval | UNPROVEN CURRENT VALUE, not presumed waste | identify consumers and benchmark demand |

These classifications are deliberately provisional. The purpose is to collect evidence, not to justify a predetermined simplification.

## 5. Questions R.3a should answer

R.3a is both a performance task and architecture evidence.

Record:

- before/after total latency;
- parse count and parsed-revision cache hit/miss;
- source artifact/revision repository call counts;
- provenance-resolution count;
- scope-projection time;
- retrieval-specific time;
- memory growth;
- number of permanent concepts/ports added.

The important interpretation question is:

> Was direct-read slowness mostly "one missing coherent read context + N+1 provenance", or does efficient serving require a broad caching/materialization subsystem?

The former is strong evidence that the architecture is basically lean but immature. The latter requires another architecture discussion before layering on infrastructure.

## 6. Forward probes

### Probe A — smallest independent client

A tiny CLI/example should use only intentional public seams to read head/search/object/neighborhood/evidence/anchor.

Success criteria: little DungeonMind-specific ceremony and no internal repository/database knowledge leaking into the client.

### Probe B — DungeonBuddy Agent Surface

The product should be able to combine highlighted document text + current work context in Buddy, ask DungeonMind for related objects/neighborhood/evidence, and later submit governed mutation proposals.

DungeonMind should not learn about the editor, right-click interaction, Hermes/Pi, prompts, or conversation thread.

This is a strong boundary test.

### Probe C — profile extension

When a real second profile/domain appears, measure how many generic-kernel files/contracts/migrations must change.

The profile abstraction earns its keep if most work stays profile-side.

## 7. Simplification rule

After R.3a, ask of every major subsystem:

> If this did not exist today, would we build it again to support the consumers and correctness properties we currently have?

If yes, keep it and document why.

If no, ask whether it demonstrably enables an imminent extension. If neither is true, it is a simplification candidate.

The delta between "minimum DungeonMind required by current consumers" and the actual library is not automatically waste. That delta is where extensibility lives. But every item in it must eventually earn its cost.

## 8. Achievement statement

The milestone is larger than moving bytes from files to PostgreSQL.

We have separated **world knowledge authority** from the product that originally grew it.

DungeonMind can now be evaluated on its own merits:

- Is its public seam natural for another consumer?
- Is its correctness machinery worth the concepts it introduces?
- Can it get faster without becoming cache machinery wrapped around a graph?
- Can it support another semantic profile without generic-kernel churn?
- Can founding-era agent/runtime concepts be removed cleanly if they do not belong?

Those are healthier questions than "can Buddy survive the migration?" The migration has provided enough evidence to start asking them.
