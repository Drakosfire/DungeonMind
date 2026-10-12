# HANDOFF — v6 evidence producer-key preservation

**Created:** 2026-10-12  
**Status:** ACTIVE  
**Repository / branch:** DungeonMind / `codex/v6-evidence-producer-key`  
**Base:** `13143455b304d748c249bd7bd628134c421bf6d9`  
**Mission:** Preserve an admitted source's producer classification when v1 contribution evidence is materialized into a v6 graph.

## Outcome and evidence

An admitted SourceArtifactV2 with a producer key distinct from its generic SourceDomain can be used by a confirmed GraphContributionV2, published atomically, and found through authorized World search, object/evidence lookup, and source-anchor revalidation. The source pair remains byte-identical.

The motivating private regression is an approved disposable rehearsal: packet SHA-256 `2c59fcb48812a007696a44bbb71d38c9dee717c02fac78b499911e5e79dcac3d`, review intent `5ea9632156fb4e8f052a53dd854d999b6cc1f5b2bf20660c86c3109852bf4946`. Publication succeeded, but the source artifact producer key and lifted evidence producer key differed. Authorized projection returned `evidence_source_domain_mismatch`. Repository tests must use synthetic source bodies and identities; private corpus content stays outside Git.

## Authority and contract

Read `Docs/Architecture/AUTHORITY.md`, `Docs/Architecture/ARCHITECTURE.md`, `CONTRIBUTING.md`, source/evidence contracts, finalized v2 review contracts, and current v6 materialization/publication code. Current checked-in code and immutable durable records outrank chat reconstruction.

`GraphContributionAssertionV2.evidence_refs` uses `EvidenceRef` (`dm_evidence_ref_v1`). That contract carries only generic `source_domain`, not a producer `source_domain_key`. `EvidenceRefV2` and SourceArtifactV2 separate these fields. The lift must obtain the producer key from a coherent source snapshot; it cannot reconstruct it from the enum, locator, client payload, source body, or ID. No wire-contract mutation is required: extend the application repository port to supply that existing typed snapshot and keep durable command/receipt schemas unchanged.

## Scope and lease

Changed-path budget: nine paths, with a recorded rebrief if another path becomes necessary:

- this handoff;
- `src/dungeonmind/application/repositories.py`;
- `src/dungeonmind/application/review_publication.py`;
- `src/dungeonmind/application/review_materialization_v6.py`;
- `src/dungeonmind/infrastructure/memory/repositories.py`;
- `src/dungeonmind/infrastructure/postgres/review_publication.py`;
- `tests/conformance/test_review_materialization_v6.py`;
- `tests/integration/test_postgres_review_publication_v6.py`;
- `tests/integration/test_review_publication_source_producer_key.py`.

Only materialization of v2 reviews into `dm_union_graph_v6`, source-snapshot port wiring, publication integrity checks, and focused regressions are in scope. Native vNext writes, domain vocabularies, Buddy extraction/DTOs, storage optimization, wire schema changes, migrations, historical graph rewrites, and source relabeling are excluded. No retained database mutation is authorized. Existing private clone receipts are evidence, not production state to repair.

## Invariants and implementation

1. SourceArtifactV2 producer classification supplies the lifted producer key; the evidence's generic SourceDomain remains separate and must agree with the source's generic domain.
2. Source-backed materialization rejects missing source authority, wrong World, incompatible source generation, generic-domain mismatch, and missing/misbound named revision before mutation. Pure historical materializer calls and explicitly source-free in-memory test compositions retain their existing behavior; production PostgreSQL publication always resolves source authority.
3. Only accepted assertions' source identities are requested, once in a bounded snapshot. Source bodies are never fetched by the Core.
4. Publication adapters revalidate introduced evidence against current source records under the owning writer fence. A source change between preparation and commit fails closed with zero revision/head/event/receipt mutation. Old parent evidence and exact durable replay are preserved.
5. Graph revisions and SourcePairs remain immutable. Read-side producer-key equality, schema, scope, visibility and lifecycle gates remain unchanged. No special producer-key names occur in Core logic.

## Acceptance and handback

Run focused materialization, review/publication, and source tests plus Ruff and static checks. Prove producer key distinct from generic domain, unchanged SourcePair and v1 input, negative authority/domain/revision cases, writer-boundary forged-key rejection and source-drift rejection with zero mutation. PostgreSQL must prove source admission → finalized review → atomic publication → World search/get-object/get-evidence → exact admitted source opening, plus replay and existing failure hooks.

Rehearse the repaired implementation only on a separately named disposable database if needed; pin the exact packet, code head, clone name and source/head anchors before writes. Keep all private bodies out of reports and PRs.

Open a focused PR for independent review. Record head/base, checks, synthetic PostgreSQL proof and private clone evidence. The Core repair does not authorize retained migration/publication, does not resolve the 37 held candidate items, and does not reproduce the isolated historical 66 accepted proposals. Stop and rebrief if fixing the defect requires changing source classification, weakening read admission, altering a durable schema, or expanding the lease.
