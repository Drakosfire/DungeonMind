# ADR-0027 — atomic prospective evidence-bearing aliases

Status: accepted design for bounded implementation, runtime acceptance pending.
Authority: HANDOFF-MIND-prospective-evidence-aliases.md in Docs/Plans.

The current prospective contribution can allocate entities and assertions, but
ordinary identity decisions cannot target a create result. Its alias_add path also
does not preserve evidence. Predicting an allocated ID or replacing aliases with
name facts would violate the current identity boundary.

Add an explicit versioned alias wrapper and publication entry point. Alias IDs
remain caller-owned operation identities, entity IDs remain Kernel-allocated.
Accepted aliases target only accepted entity creates within the wrapped
contribution, carry explicit standing and parent-bound evidence, and commit in the
same generic publication transaction. The complete final child is validated and
sealed; the complete wrapper and all dispositions are request-hash inputs.

Retain existing contracts/receipts unchanged. Reuse generic read admission and
source withdrawal; parent evidence membership is not current source authorization.
No new source creation, product semantics, alias search, provider or deployment
behavior is introduced. Consumer adoption and native first-World publication are
separate acceptance gates.
