# DungeonMind — Authority and Source Precedence

**Status:** founding (PR A)

## 1. Precedence rules

1. **This repository's checked-in state** (code, contracts, ADRs) is the
   current truth for DungeonMind. ADR-0001 (datastore), ADR-0002
   (persistence lifecycle ownership), ADR-0003 (pgvector as derived index),
   and ADR-0004 (semantic profile boundary) are the accepted decision set.
2. **GitHub current state beats local or Project Source copies** wherever
   they disagree (applies to sibling repos inspected during founding).
3. **DungeonMindBuddy architecture docs** are authority for the *proven
   semantics* this repo adopts (§2) — but never for implementation mechanics
   (filesystem layout, app wiring), which this repo replaces.
4. **RulesIngestion** is authority for retrieval *benchmark discipline* —
   not for DungeonMind production behavior, and never a runtime dependency.
5. **Chat history is never authority.** If chat and checked-in sources
   disagree, the sources win or the sources get fixed in the same edit batch.

## 2. DungeonMindBuddy authority set (read in this order)

1. `Docs/Design/ARCHITECTURE-campaign-supergraph.md`
2. `Docs/Roadmaps/ROADMAP-campaign-supergraph.md`
3. `Docs/Plans/PR-TRACKER-campaign-supergraph.md`
4. `Docs/Design/STATUS-world-graph-continuity-spine.md`
5. `Docs/Design/CONTRACT-graph-kernel-boundary.md`
6. `Docs/Design/ARCHITECTURE-hermes-campaign-authoring-foundation.md`
7. Current graph-memory models, kernel APIs, projection contracts,
   retrieval-session contracts, tests, accepted dogfood reports.

The decisions adopted from these are listed in `ARCHITECTURE.md` §3 and were
extracted with citations in
`Docs/Reports/RECON-2026-07-29-founding-inventory.md` §A.

## 3. Semantic profile authority (PR B.2b)

1. **ADR-0004** (`Docs/Decisions/ADR-0004-semantic-profile-boundary.md`) is
   the accepted record of the kernel/profile boundary, on equal footing
   with ADR-0001…0003 in the authority set.
2. **DungeonMind architecture and contracts remain authoritative** for
   identity, evidence, revisions, retrieval, and admission — including the
   semantic profile *identity model*: the pinned ref, the descriptor shape,
   the registry config contract, the registry port, and qualified-term
   admission.
3. **`dungeonmind_dnd` is authoritative only for D&D profile semantics** —
   the content of the D&D 5e descriptor (namespaces, revisions, digests).
   It holds no authority over kernel contracts, and no D&D mechanics
   contract may land under `src/dungeonmind`.
4. **DungeonMindBuddy Threat/statblock documents are consumer
   requirements**, not authority. They evidence demand for a D&D profile;
   they never authorize placing D&D mechanics, enums, or taxonomy in the
   kernel.
5. **Profile descriptors are versioned checked-in artifacts**, not chat or
   config authority. A descriptor changes only by a new immutable profile
   revision (new pin, new digest); historical revisions stay loadable for
   as long as graphs pinned to them must remain readable.
6. **Local registry paths are never semantic authority.** A registry config
   locates descriptor files for one deployment; durable identity is the
   pinned `profile_id` + `profile_revision` + `descriptor_sha256`, and
   paths never appear in graph payloads or public responses.

## 4. Known drift found at founding (do not re-import)

Founding recon (same report, §G) documented places where Buddy's
implementation disagrees with its own closed decisions. DungeonMind follows
the *decisions*, not the drift:

- Buddy's durable store payload still carries campaign+focus session-union
  keys at its root; DungeonMind models campaign strictly as scope.
- Buddy evidence models use `extra="allow"`; DungeonMind contracts are
  `extra="forbid"` everywhere.
- Buddy capability taxonomy exists twice (doc-level five categories vs
  runtime `allowed_effects={"read"}`); DungeonMind implements the five
  categories with a fail-closed evaluator.
- Buddy `graph_memory` modules import `apps.*`; DungeonMind forbids any such
  import by test.
- Buddy keeps preview/latest-ingest paths as product debt; DungeonMind has no
  preview authority paths at all.

## 5. Project Source classification (from the founding handoff §2.4)

| Source | Status here |
| --- | --- |
| `CORPUS-ANCHOR.md` | Source-location anchor only |
| `GRAPH-MEMORY-PROJECT-LAYOUT.md` | Reference, subject to current GitHub state |
| `ARCHITECTURE-plan-surface-toolbox.md` | Surface-boundary reference |
| `LLM-graph-construction.md` | Research only |
| `dungeonbuddy_spec_architecture_v0_2.md` | Historical conceptual ancestor |
| `GRAPH-MEMORY-SUPERGRAPH-ARCHITECTURE-ROADMAP.md` | Superseded historical roadmap |
| `PROPOSAL-context-audit-source-reanchor.md` | Proposal, not authority |
| `_bmad-output/project-context.md` | Engineering rules kept; "no API/database/vector" scope superseded |

## 6. The founding charter

The dispatching handoff is preserved verbatim at
`Docs/Handoffs/HANDOFF-found-dungeonmind-repository.md`. Its §15 stop
conditions and §14 non-goals remain binding for every successor slice.
