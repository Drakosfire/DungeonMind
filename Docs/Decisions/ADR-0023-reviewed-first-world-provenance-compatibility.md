# ADR-0023 — Reviewed first-world genesis provenance compatibility

**Status:** Proposed  
**Date:** 2026-08-26  
**Deciders:** implementing agent, per CUTOVER reviewed-init-v1 genesis provenance dispatch after Buddy PR #653  
**Supersedes:** none  
**Related:** ADR-0015, ADR-0019, ADR-0021

The handoff asked for ADR-0023. ADR-0022 is already taken by
`ADR-0022-independent-library-and-agent-harness-boundary.md`. This is the
next free number.

## Question

How does DungeonMind admit historically mis-stamped #645 first-world `OTHER`
evidence onto native projection and replay without rewriting immutable `D_0`,
broadening ordinary provenance admission, or depending on Buddy-side semantic
rewrites?

## Context

DungeonMindBuddy #645 publishes a real zero-parent first revision `D_0`. The
authoritative `SourceArtifact` is worldbuilding, but contribution evidence was
stamped `SourceDomain.OTHER`. Native projection then rejects those facts as
`evidence_source_domain_mismatch`.

Rejected repairs included mutating immutable `D_0`, rewriting `evidence_refs`
before projection, trusting any artifact over a disagreeing domain, and making
Buddy the sole compatibility layer. Ordinary reviewed-init `OTHER` stamps, and
family commands whose live artifact is not worldbuilding, must keep failing
closed.

Replay identity was exact `command_sha256` only. A later corrected retry that
stamps the artifact domain therefore conflicted with the historical receipt
even though it is the same #645 initialization.

## Decision

1. **Named producer family only.** Compatibility applies only when
   `source_plan_schema == "dmb_first_world_graph_plan_v1"`,
   `initialization_id` matches `^dmb:first-world:[0-9a-f]{64}$`, and
   `actor == "live_control:graph_review_confirm"`. Projection additionally
   requires `D_0.parent_revision_id is None`. Eligible evidence additionally
   requires a live worldbuilding/`worldbuilding` artifact. These strings are
   copied into DungeonMind; Buddy is not imported.

2. **Compatibility is request context above `graph_scope`.**
   `WorldGraphProjectionService` requires
   `ReviewedWorldInitializationRepository`. Absence of a receipt is
   `get_for_world → None`, not absence of the repository. When a receipt
   exists, the service loads and verifies the exact immutable `D_0`, then
   builds `GenesisEvidenceCompatibility` only for the named family. Broken
   `D_0` correspondence is `PersistenceIntegrityError`.

3. **`graph_scope` stays a pure consumer.** Optional
   `genesis_compatibility` is content-bound: the entire canonical D0
   evidence record, not just the id. For provenance domain comparison only,
   the OTHER stamp is treated as the known placeholder (the live artifact
   domain is compared to itself). Parsed snapshots, stored payloads, and
   cache entries are not rewritten. Same id with any changed field on a
   descendant, and new OTHER ids on descendants, receive no exception.

4. **One shared replay identity at all four seams.**
   `ReviewedWorldInitializationReplayIdentity` carries the current command
   digest plus an optional historical OTHER-normalized digest. The historical
   digest is computed only for a family command whose eligible v1
   `EvidenceRef.source_domain` values reverse-normalize from worldbuilding
   back to OTHER and differ from current. It is never persisted. First insert
   stores the current hash. A receipt matches when initialization id matches
   and the stored hash equals current, or equals the historical digest and the
   receipt is also family. Application preflight, lost-response recovery,
   PostgreSQL under-lock replay, and in-memory under-lock replay all use this
   identity.

5. **Existing semantics remain the default.** Without valid #645
   compatibility, session-recap vs worldbuilding mismatch still rejects,
   non-family reviewed-init OTHER still rejects, family plus non-worldbuilding
   still rejects, adopted-world/Eldyrwild behavior is unchanged, and PLAYER
   remains fail-closed.

## Consequences

- Buddy still produces OTHER on new first-world commands until a successor
  producer PR. This decision does not update Buddy's DungeonMind pin or
  unpark #651.
- Raw `get_revision(...D_0...)` continues to expose historical OTHER.
- This is not a generic provenance waiver and does not add source-mutation
  or graph-rewrite APIs.
