# ADR-0021 — Existing-world adoption source-classification repair

**Status:** Accepted  
**Date:** 2026-08-23  
**Deciders:** implementing agent, per CUTOVER R.2b dispatch after Buddy PR #629 Review Cycle 3  
**Supersedes:** none  
**Related:** ADR-0002, ADR-0015, ADR-0019

The handoff asked for ADR-0016. That number is already taken by
`ADR-0016-eldyrwild-whole-world-object-kinds-v2.md`. This is the next free
number.

## Question

How does DungeonMind record a legitimate, steward-supervised correction to
already-adopted `SourceArtifactV2` classification fields without rewriting V3
history, re-adopting the world, or adding a generic source mutation API?

## Context

Existing-world adoption (ADR-0019) publishes one terminal receipt per world.
V3 later added `membership_sha256` as a checkpoint over the exact sealed
bundle's four adopted history families. That digest is historical: it is
derived from the sealed bundle, never minted from current database rows.

During Buddy R.3 experimentation, out-of-band scripts mutated adopted
classification fields (`visibility` None→GM; two session-less worldbuilding
`campaign_id` values campaign-owned→None) and rewrote the V3 membership
checkpoint to match the mutated rows. Those Buddy `--apply` paths are now
hard-disabled. Containment is not a DungeonMind repair.

Rewriting V3 again would choose which side of the invariant to break.
Re-adoption would falsify chronology on a living world. A generic
`SourceRepository.update_artifact` would become an unbounded mutation API.

## Decision

1. **V3 remains historical.** `membership_sha256` (M0) is the sealed
   original adopted-member digest. Repair must restore it when a corrupted
   V3 checkpoint was rewritten from current rows. V3 is never a serving
   license to treat current rows as what was adopted.
2. **V4 is explicit repair authority.** One
   `dm_existing_world_adoption_receipt_v4` retains every prior adoption fact
   and adds:
   - `membership_sha256` = M0 from the exact sealed bundle
   - `effective_membership_sha256` = M1 from the sanctioned adopted-member
     state after the recorded corrections
   - `membership_manifest` = exact sealed adopted-member IDs
   - `source_classification_repair` = one repair record with observed
     pre-repair digest, exact correction fingerprints, and a content-bound
     `repair_id`
3. **Allowed transitions are closed.** Only `visibility` None→GM and
   `campaign_id` campaign-owned→None for explicitly named session-less
   `source_domain=worldbuilding` artifacts. Every other source field, and
   every revision/contribution/identity record, must equal the sealed
   original. Named artifacts may already be original or exact target.
4. **One atomic adoption-aggregate operation.**
   `ExistingWorldAdoptionRepository.repair_source_classification` is the
   only writer. It uses the same writer-excluding boundary as V3 promotion.
   Artifact updates are a typed in-transaction replacement of the full
   target `SourceArtifactV2`, not a public source lifecycle API.
5. **Correspondence distinguishes M0 from M1.** Identity-matched sealed
   bytes still prove bundle-derived M0. Current-state integrity hashes the
   manifest-selected rows against M1. Later descendants outside the
   manifest must not break the V4 checkpoint.
6. **Recovery is exact V4 identity.** An uncertain mutation attempt may
   return success only when the durable receipt is V4 and the repair
   identity matches. An unchanged V3 is not success.
7. **Dry-run is a no-write preflight.** The same proofs run under the
   writer-excluding boundary and return the would-be V4 receipt with zero
   writes.

## Consequences

- Live Eldyrwild apply is a later operator action after this PR merges. It
  is not this decision's implementation.
- Buddy R.3 / PR #629 stays paused until it can pin a landed R.2b and teach
  hydration to serve V4 `effective_membership_sha256`.
- This is not a general history-repair framework and does not reclassify
  remaining R.3 semantic witness differences.
