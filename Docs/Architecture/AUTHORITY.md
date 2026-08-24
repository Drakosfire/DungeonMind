# DungeonMind — Authority and Source Precedence

**Status:** current post-R.3 library authority  
**Updated:** 2026-08-23

## 1. Precedence

When sources disagree, use this order:

1. **Current checked-in DungeonMind contracts, code, accepted ADRs, and architecture docs.**
2. **Durable published DungeonMind state** for a specific world: immutable graph revisions, explicit head, source/evidence records, contribution/review/publication records, and adoption receipts.
3. **Current-client acceptance evidence** for capabilities claimed by the library, when pinned to exact commits/revisions and consistent with 1–2.
4. Historical founding/cutover reports and external architecture documents as evidence of intent or prior behavior.
5. Chat/history is never authority; if it contains a newly accepted decision, the checked-in docs must be updated in the same change set.

Current accepted ADRs include ADR-0001 through ADR-0021 as applicable plus **ADR-0022**, which establishes DungeonMind as an independent knowledge library and places the agent harness outside the library boundary.

## 2. World Graph authority

For a world served by DungeonMind:

- the immutable published graph revision is authority for the exact graph payload at that revision;
- the explicit world head is authority for which published revision is current;
- timestamps and row order never select graph truth;
- exact historical pins remain historical truth even after head movement;
- rollback is an explicit head operation, not history mutation.

For Eldyrwild, the existing-world adoption and post-adoption publication proved this model against a real external consumer.

## 3. Source and evidence authority

Source/evidence validity is not frozen merely because a graph revision is immutable.

The checked-in schema semantics plus current durable source state determine whether an evidence chain is admissible for a read. Relevant source state includes artifact existence, world/campaign classification, visibility, lifecycle, source domain, source-revision existence, and source-revision/artifact binding.

Therefore:

> Graph revision identity alone is not sufficient authority for a cached scoped/admissible projection.

A cross-request authorized projection cache requires coherent source/provenance state identity or an equivalent invalidation proof.

Out-of-scope material is filtered silently. Scope-unknown or broken provenance fails closed under the public diagnostic rules defined by the current graph schema/application services.

## 4. Existing-world adoption authority

The Eldyrwild adoption history remains governed by ADR-0019 and ADR-0021.

- V3 `membership_sha256` is historical M0 from the exact sealed adoption bundle.
- V4 `effective_membership_sha256` is sanctioned M1 after the single accepted source-classification repair.
- V4 membership manifest selects the exact adopted members.
- The repair record is the only authority for the accepted classification changes.
- Later descendants are normal living-world history, not retroactive adopted membership.

No future optimization may rewrite this history to make reads easier.

## 5. Client authority boundary

DungeonMindBuddy is the first real external consumer of the library, not its semantic authority.

The accepted R.3 consumer contract establishes the capabilities a current client can rely on: revision-aware projection, object/search/neighborhood/evidence/anchor reads, campaign/world/cross-campaign scope, and GM/PLAYER admissibility.

Where historical Buddy-kernel behavior differs from accepted DungeonMind semantics, the accepted DungeonMind contract wins unless a current named client requirement proves a defect.

Client adapters may:

- map wire shapes;
- map explicit scope/admissibility vocabulary;
- perform deterministic presentation transformations;
- open product-local source content only after DungeonMind admits/revalidates the anchor and the product verifies the expected digest.

Client adapters may not:

- reconstruct a foreign graph to recover excluded rows;
- replay contributions to redefine graph truth;
- broaden scope/admissibility;
- infer current revision from client-local files;
- restore retired semantics solely for compatibility.

## 6. Agent-harness authority boundary

Per ADR-0022, DungeonMind does not own agent orchestration.

The client/harness owns model selection, prompts, product context, tool loop, retries, approvals, conversation state, and which product tools an agent receives.

DungeonMind remains authoritative only for the validity and authorization of **DungeonMind operations themselves**. A library method may reject an invalid or unauthorized read/write; it does not decide the complete tool policy of a product agent.

Existing MindTurn/agent/context modules are subject to architecture-fitness review and are not evidence that the library permanently owns harness behavior.

## 7. Semantic-profile authority

DungeonMind owns semantic-profile identity: refs, descriptor contracts, digests, registry ports, and qualified-term admission.

A profile package owns its domain meaning. `dungeonmind_dnd` is authoritative for its checked-in D&D descriptors/vocabularies and pure profile-side adapters; it holds no authority over generic kernel contracts.

Profile paths/config are locators, never durable semantic identity. Graphs pin profile identity and digest.

## 8. Write authority

Only governed durable operations produce graph truth.

Candidate extraction/planning is not authority. Finalized review is governance input, not graph truth. Publication against an exact expected parent produces one immutable child revision and advances the explicit head atomically.

Publication receipts/recovery records prove the correspondence between reviewed input and published revision; current-head equality is not required to prove a historical publication occurred.

No agent, UI, prompt, or current-head inference has silent durable write authority.

## 9. Historical sources

DungeonMindBuddy architecture/cutover documents remain valuable evidence for the semantics and migration pressures that founded this library, but they no longer outrank the current independent-library architecture.

RulesIngestion/retrieval research remains benchmark-methodology input, not DungeonMind runtime authority.

Founding reports and the original PR ladder are historical evidence. The current forward plan is `Docs/Roadmaps/ROADMAP.md`.
