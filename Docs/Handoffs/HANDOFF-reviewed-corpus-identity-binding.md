# Reviewed corpus identity binding — bounded Core contract slice

**Status:** CONTRACT PREFLIGHT ONLY — runtime confirmation and publication remain false.
**Base:** DungeonMind `f7f2a1f61e00ba56885e20d4f95c0a5fd2e843a8`.

## Decision

A fresh ingest may propose a reviewed binding from an authoritative, typed hub identity key to an **existing** canonical graph node. The binding names the world/campaign, exact hub artifact/current revision/body digest, exact identity assertion ID and digest, assertion's typed key and asserted target, canonical target ID/kind, and expected graph head. No display label, alias or fuzzy match is an identity key. The older `ReviewedIdentityPublicationPreconditionsV1` does not carry this exact hub assertion or typed key; extending it in place would blur an accepted wire contract. This additive contract lives in `contracts/corpus_identity_binding.py`.

The pure `validate_reviewed_corpus_identity_binding` preflight checks scope, source revision/body, graph head and target, unique exact hub assertion membership, and collisions with accepted bindings. Its `CorpusIdentityAuthoritySnapshotV1` is **not caller input**. A later confirmation owner must resolve it from the authoritative corpus and graph stores under a concurrency fence and rerun validation immediately before atomic mutation. Passing a fabricated snapshot proves nothing. No repository port, source admission, graph write, migration or live corpus access is leased here.

## Synthetic falsifiers

Unit tests cover stale scope/artifact/revision/body/head, wrong target kind or ID, missing/ambiguous assertion, competing key/target mapping, hub target mismatch, and rejected label/alias fields. They prove only the contract and pure preflight; they do not prove transactional confirmation or zero mutation at a persistence boundary.

## Next owner gate

Before runtime use, specify the hub's canonical identity-assertion serialization/digest, a trusted corpus read of the exact revision and assertion, graph target existence/kind read, accepted-binding index and locking/uniqueness rules, review authority, and an atomic confirmation/receipt path. Recheck all observations in that path; do not admit source or publish graph truth from this contract alone. PR #109's operator-attested source-span runtime is a separate source/read authority and is not modified here.
