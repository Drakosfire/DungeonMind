# DungeonMind — Authority and Source Precedence

**Status:** current checked-in authority (B.2f-d)

## 1. Precedence rules

1. **This repository's checked-in state** (code, contracts, ADRs) is the
   current truth for DungeonMind. ADR-0001 (datastore), ADR-0002
   (persistence lifecycle ownership), ADR-0003 (pgvector as derived index),
   ADR-0004 (semantic profile boundary), ADR-0005 (executable D&D profile
   boundary and Threat semantics), and ADR-0006 (pinned profile
   create-or-connect contribution planning), ADR-0007 (finalized contribution
   review adoption), ADR-0009 (review graph materialization), ADR-0010
   (expected-parent CAS publication), and ADR-0011 (durable publication
   identity and recovery), and ADR-0012 (publication service transport) are
   the accepted decision set.
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

## 3.1 D&D vocabulary and candidate authority (PR B.2c)

1. **The checked-in D&D vocabulary catalog** (`src/dungeonmind_dnd/vocabularies/threat-v1.json`)
   is authoritative for B.2c candidate terms: exactly the kinds, predicates,
   and direction it declares. It changes only by a new immutable catalog
   revision (new pin, new digest).
2. **The catalog is not authority over existing graph truth.** It
   constrains what candidates may propose, never what the graph contains.
3. **Evidence and source artifacts remain the authority for claims.**
   Candidate packets are provenance-bearing *proposals*, not canonical
   facts; validation does not canonize them.
4. **DungeonMindBuddy Threat/statblock documents remain consumer
   requirements.** They justify which narrow profile-owned terms exist;
   they never authorize kernel D&D semantics and they are not candidate
   term authority.
5. **Prompts and model output are never semantic authority.** The rendered
   prompt fragment is deterministic catalog-derived guidance; the catalog
   and the deterministic validator are the only candidate-term authority.

## 3.2 Pinned contribution-plan authority (PR B.2d)

1. **The exact immutable base revision** is authority for existing object
   and relationship presence during planning. Current head is not inferred.
2. **The D&D catalog** remains authority for allowed candidate terms.
3. **Candidate evidence** remains authority for proposed claims.
4. **Exact label/alias matching is a proposal mechanism**, not an identity
   decision. Ambiguity and cross-kind collisions block; they never pick a
   winner.
5. **The plan and contribution preview are not canonical.** Only a later
   confirmed durable operation may append identity decisions or
   contributions, or publish a revision.
6. **ADR-0006** records the planning boundary on equal footing with
   ADR-0004/0005 in the authority set.

## 3.3 Finalized contribution-review authority (PR B.2e)

1. The source-plan reference and complete intent digest are authority for what
   was reviewed; the candidate contribution is authority for proposed claim
   bytes and evidence.
2. Assertion verdicts are authority for accepted/rejected review state.
   Identity verdicts are authority for the reviewer's disposition of each
   planned target, but they are not `IdentityDecisionRecord` operations.
3. The `confirm_commit` capability policy and content-bound confirmation
   receipt are authority for whether this one-shot durable review is permitted.
   The policy must be GM-admissible and exact in world, campaign, and revision
   scope; an unpinned policy is never sufficient.
4. The expected parent is authority for review context. B.2e preflights the
   current head but does not publish or perform publication CAS; B.2f must
   recheck the parent atomically.
5. A finalized review is durable governance state, not canonical graph truth.
   The superseded candidate and active reviewed successor are publication
   inputs only. Published graph revisions remain final graph authority.
6. Exact operation replay is idempotent. A changed operation payload and a
   second finalized review for one source plan are conflicts, not replacement
   semantics. No draft, cancellation, retraction, target override, or review
   supersession exists in B.2e.

## 3.4 Finalized-review publication authority (PR B.2f-c)

1. The finalized review is governance authority for the reviewed contribution,
   intent digest, confirmation, operation, and expected parent.
2. The immutable published revision is graph authority for its exact payload,
   parent, schema, operation binding, and creation timestamp.
3. The terminal `FinalizedReviewPublication` record is durable correspondence
   and commit receipt between the review and revision. It is immutable once
   committed and contains no pending, retry, worker, transport, or error
   state.
4. The publication repository owns one atomic unit containing revision insert,
   expected-parent head CAS, normal head event, and publication-record insert.
   It must cross-verify the command against the durable review before mutation.
5. Publication identity is historical. A later descendant or explicit head
   rollback does not invalidate a record, and current-head equality is not
   required for replay or reconstruction. Replay returns the original record
   without rematerialization or graph mutation.
6. Recovery is exact and bounded: a thrown publication call gets one
   `get_for_review` probe; only the exact durable record proves success. The
   exact deterministic predecessor revision may be adopted without head
   mutation. Arbitrary history scans and success inference are forbidden.
7. B.2f-c does not append `IdentityDecisionRecord` rows, mutate review or
   contribution lifecycle, expose transport, or adopt a product surface.

## 3.5 Finalized-review publication transport authority (PR B.2f-d)

1. B.2f-c remains the sole authority for publication materialization, revision
   identity, head CAS, durable publication records, exact replay, and response
   loss recovery.
2. The publication app is a separate service from the read-only Mind Turn host.
   It accepts only `world_id` and `review_id` in the strict
   `dm_finalized_review_publication_request_v1` body.
3. The configured bearer digest authorizes one configured world at the edge. It
   is transport access, not a second semantic confirmation, production user
   identity, or a capability-policy decision inside the kernel.
4. The server owns the one timezone-aware publication timestamp and delegates
   once to `publish_finalized_review`. Fresh, replayed, and recovered success
   return the existing `dm_finalized_review_publication_v1` record.
5. The HTTP layer never reads current head state to infer success, performs
   transport retries, exposes polling/list endpoints, mutates reviews, adds
   pending lifecycle, installs CORS, or creates a browser write surface.
6. Readiness is infrastructure/configuration readiness only. It checks database
   connectivity and required table visibility, not review existence, head
   equality, graph payloads, or publishability.

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
