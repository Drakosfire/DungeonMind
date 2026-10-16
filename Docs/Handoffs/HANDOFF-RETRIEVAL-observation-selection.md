# Exact reviewed source observation selection

Status: ACTIVE; PRIME solo implementation, ARCHITECTURE independent review.
Base: DungeonMind origin/main `b64e10b71c25814fadde8a2a76bba8f700d3d7d0`.
Branch/checkout: `codex/reviewed-observation-selection`, `/tmp/prime-mind-reviewed-source-search`.
Topology: serial Core prerequisite; no current open Core PRs. Separate Buddy consumer after accepted exact pin.
Authority: active Mirathorn lifecycle goal and ARCHITECTURE advice following the Council deadline failure.

## Contract

Read 1–8 distinct exact reviewed observation assertion IDs from one source artifact/revision and one pinned World/scope/admissibility/Graph context. Establish that context once and reuse reviewed-publication ancestry, corrections, subject admission and evidence validation. Return full qualified observations, their subject identities, and only their complete anchor closure. Never infer membership, choose latest, read source bodies, or promote authored properties into this facet.

Unavailable IDs fail the selection atomically with caller-supplied missing IDs and no observations/anchors/subjects. Explicit aggregate canonical payload byte budget (default/ceiling 262144 bytes) produces a distinct empty overflow result, never truncated descriptions or missing required anchors. Invalid requests reject before reads. Integrity failures retain existing failure behavior. Preserve historical source access and cross-campaign scope distinctions.

Buddy consumer will expose a Build-only observation selection using model-supplied IDs and host-derived frozen source identity. Its generic validated Graph event may suffice, but worker allowlists, paging, trace, replay and final-envelope admission require owning tests before adoption. No Agent/answer acceptance is claimed by this prerequisite.

## Exclusive expected writes

- This handoff.
- `Docs/Handoffs/HANDOFF-RETRIEVAL-reviewed-source-discovery.md` (settle merged predecessor only).
- `src/dungeonmind/application/world_graph_retrieval.py`.
- `tests/conformance/test_reviewed_observation_selection.py`.

## Evidence and gates

Actual published review fixtures: multiple subjects, disjoint references, exact source revision, duplicates/foreign IDs, campaign/visibility exclusions, withdrawn/current versus historical observations, aggregate overflow and complete anchors. Assert one coherent context, no unrelated object/property/relationship support, unchanged stored state and deterministic output. Focused current retrieval regressions, Ruff and cumulative diff check; publish one PR and independent review before merge. No provider, corpus export, serving, schema or retained database writes.
