# Reviewed corpus identity binding — bounded Core contract slice

**Status:** CONTRACT PREFLIGHT ONLY — runtime confirmation and publication remain false.
**Base:** DungeonMind `f7f2a1f61e00ba56885e20d4f95c0a5fd2e843a8`.

## Decision

A fresh ingest may propose a reviewed binding from an authoritative, typed hub identity key to an **existing** canonical graph node. The binding names the world and explicit campaign scope (`null` for world-owned), exact hub artifact/current revision/body digest, exact identity assertion ID and digest, assertion's typed key and asserted target, canonical target ID/kind, and expected graph head. No display label, alias or fuzzy match is an identity key. The older `ReviewedIdentityPublicationPreconditionsV1` does not carry this exact hub assertion or typed key; extending it in place would blur an accepted wire contract. This additive contract lives in `contracts/corpus_identity_binding.py`.

Identity uniqueness is **world-wide**, not campaign-local. ADR-0014 states that campaign scope partitions knowledge, not things; a shared canonical node must not split into C1 and C2 identities. ADR-0021 recognizes session-less worldbuilding sources whose campaign association is `null`. Consequently the source scope may be campaign-owned or explicitly world-owned, but existing key/target collisions must be checked across every campaign in the world. The typed key's namespace/type/value must itself be stable across those scopes; a producer that uses campaign-local key values needs a separate namespace/type contract and cannot silently treat them as world identities.

The pure `validate_reviewed_corpus_identity_binding` preflight checks scope, source revision/body, graph head and target, unique exact hub assertion membership, and world-wide collisions with accepted bindings. Its `CorpusIdentityAuthoritySnapshotV1` is **not caller input**. A later confirmation owner must resolve it from the authoritative corpus and graph stores under a concurrency fence and rerun validation immediately before atomic mutation. In particular, `hub_assertions` must be the **complete authoritative identity-assertion enumeration for that exact source revision**, or an exact typed-key lookup whose authority proves uniqueness; `existing_bindings` must be a complete world-wide collision lookup. The model cannot prove either completeness property. A partial/failed/unverifiable lookup is a confirmation failure, never an empty tuple. Passing a fabricated or incomplete snapshot proves nothing. No repository port, source admission, graph write, migration or live corpus access is leased here.

## Synthetic falsifiers

Unit tests cover stale scope/artifact/revision/body/head, wrong target kind or ID, missing/ambiguous assertion, competing key/target mapping including C1/C2 collision, world-owned scope, hub target mismatch, and rejected label/alias fields. They prove only the contract and pure preflight; they do not prove completeness of an authority read, transactional confirmation, or zero mutation at a persistence boundary.

## Next owner gate

Before runtime use, specify the hub's canonical identity-assertion serialization/digest, a trusted **complete** corpus read of the exact revision and assertion (or authority-proven unique typed-key lookup), graph target existence/kind read, world-wide accepted-binding index and locking/uniqueness rules, review authority, and an atomic confirmation/receipt path. Owning-boundary tests must falsify omitted identity assertions, partial/failed key lookup, omitted cross-campaign accepted binding, and stale reads with zero mutation. Recheck all observations in that path; do not admit source or publish graph truth from this contract alone. PR #109's operator-attested source-span runtime is a separate source/read authority and is not modified here.
