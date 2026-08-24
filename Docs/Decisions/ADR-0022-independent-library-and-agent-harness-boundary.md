# ADR-0022 — Independent library and agent-harness boundary

**Status:** Accepted  
**Date:** 2026-08-23  
**Deciders:** steward/product owner during post-R.3 architecture sync  
**Supersedes:** the founding assumption that DungeonMind owns end-to-end agent orchestration/context budgeting  
**Related:** ADR-0002, ADR-0004, ADR-0019, ADR-0021

## Question

After the first real product cutover, what does DungeonMind own as an independent library, and where does the agent harness belong?

## Context

DungeonMind was founded before it had a real external production consumer. Its founding architecture therefore bundled several concerns under a broad "context and knowledge runtime" thesis: graph authority, evidence/retrieval, context assembly, retrieval sessions, capability policy, answer validation, and agent orchestration.

The DungeonMindBuddy cutover now provides better evidence.

DungeonMind has proven an independent value boundary around durable graph authority, exact revisions, source/evidence provenance, scope/admissibility, retrieval, anchors, and governed publication. DungeonMindBuddy can consume those semantics through a thin adapter while keeping product presentation behavior outside the library.

DungeonMindBuddy also owns the product state needed for agentic work: current surface/document, selected text, work context, conversation state, available product tools, model/harness choice, prompt/tool loop, retries, approvals, and interruption/resume.

Keeping those harness concerns inside DungeonMind would couple the knowledge library to one product's agent architecture and make harness experimentation harder.

## Decision

1. **DungeonMind is an independent governed world-knowledge library.** Its durable responsibilities are graph/source/evidence authority, exact revisions, scope/admissibility, retrieval, semantic-profile identity/admission, and governed publication.
2. **The agent harness is entirely client-owned.** For the current product, DungeonMindBuddy owns model/provider selection, prompt construction, tool registration/loop, conversation/work state, retries, approvals, context budgeting across product tools, and harness implementation (Hermes/Pi/custom/future).
3. **DungeonMind is a tool/service used by an agent, not the owner of the agent.** An agent may call projection/search/neighborhood/evidence/anchor and governed-write APIs without DungeonMind knowing which harness, model, UI gesture, or conversation produced the call.
4. **DungeonMind may enforce authorization for DungeonMind operations.** Exact revision, world/scope/admissibility, write capability, confirmation, and expected-parent requirements remain library authority. This does not make DungeonMind the authority for the complete product-agent tool set.
5. **Product context stays outside.** Current document, highlighted text, Plan/Play/Agent surface, product thread, and other product-tool state are not DungeonMind concepts.
6. **Existing MindTurn/agent/context modules are not grandfathered into the long-term public contract.** They remain code until the architecture-fitness lane determines whether each is a useful library capability, an example/compatibility layer, belongs in a client, or should be removed.
7. **No new harness-specific features land in DungeonMind without a new ADR demonstrating why the responsibility belongs in the independent library rather than the client.**

## Consequences

- DungeonMindBuddy can experiment with Hermes, Pi, custom loops, local models, or multiple harnesses without changing DungeonMind graph semantics.
- A non-agent client such as a CLI, graph browser, exporter, or batch job should be able to use DungeonMind naturally.
- The Agent Surface magic moment can combine selected document text and product context in Buddy, then call DungeonMind for relevant graph knowledge and governed mutation proposals without teaching DungeonMind about the UI or harness.
- Some founding-era DungeonMind modules may become simplification/deletion candidates. That is intentional follow-up evidence work, not an immediate code-removal mandate from this ADR.
- Capability terminology must be read carefully: DungeonMind can authorize its own operations; client agent-tool policy remains client-owned.

## Falsification / revisit conditions

Revisit this decision only if a concrete second client demonstrates that a currently client-owned harness concern must be centralized to preserve knowledge correctness or cross-client interoperability.

Convenience alone is not sufficient. The evidence must show that the concern is intrinsic to governed world knowledge rather than to how a product chooses to reason or act over that knowledge.
