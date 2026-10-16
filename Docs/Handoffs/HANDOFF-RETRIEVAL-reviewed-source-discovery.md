# Reviewed source observation discovery

Status: ACTIVE. PRIME solo implementation; ARCHITECTURE independent review.
Base: DungeonMind origin/main `df755a00e6119f3a3997a5431420d8dfcdee9caf`.
Branch/checkout: `codex/reviewed-source-discovery`, `/tmp/prime-mind-reviewed-source-search`.
Topology: serial Core prerequisite; Buddy consumer requires accepted exact Core pin and separate handoff. Current Core open PR inventory is empty.

## Outcome and invariant

Provide bounded, paged discovery of admitted reviewed source observations for an exact source artifact/revision in one pinned World Graph context. Reuse existing publication ancestry, correction, identity, scope, visibility and evidence admission. Return subject identity, assertion identity, qualified bounded excerpt and exact source-anchor metadata; no source bodies or derived membership. Preserve distinct observations; never choose latest or merge aliases. Grouping by source is provenance, not a relationship.

The API explicitly covers the reviewed-source-observation facet, not all authored properties or all relationships. Entries are discovery-only pointers; existing complete-object and source tools must deliver records before Agent claims them. The consumer derives source identity from the exact saved Build receipt. Cursor binds World/scope/focus/admissibility/Graph revision, source pair and immutable admitted result identity. Pagination reports total count and offset; partial metadata never claims whole-source coverage.

## Exclusive expected writes

- This handoff.
- `src/dungeonmind/application/world_graph_retrieval.py`
- `tests/conformance/test_reviewed_source_discovery.py`

## Verification and holds

Prove exact source/revision matching, historical graph pins, foreign World and visibility exclusion, unresolved/corrected observation omission, distinct identities and observations, bounded deterministic pagination and cross-context cursor rejection. Use actual in-memory publication/review fixtures; verify one coherent read and unchanged object/source APIs. No provider, serving, database/schema, corpus or retained World writes. Inspect cumulative diff and open one PR, then independent review before PRIME merge. Buddy adaptation and ordinary multi-entity acceptance are follow-through; this prerequisite alone does not prove them.
