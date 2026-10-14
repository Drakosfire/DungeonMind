# Core: keep resolved subjects in bounded search

Status: ACTIVE. Owner: PRIME; solo implementation.
Base: `d81ed4e126c55ef8df57804c9ab7128b7499c7a1`.
Branch: `codex/resolved-subject-search-priority`; non-serving isolated lane.

## Outcome

Search prioritizes unambiguously resolved, admitted mentions over incidental lexical matches. Existing explicit seeds retain first priority. Mention selection remains bounded; excess resolved subjects report object truncation. Existing omitted/ambiguous alias filtering remains authoritative. No schema, admission, provider, publication or serving change.

Live private evidence: the question about Pippa owing a favor resolves her canonical ID but excludes it from bounded results. Name-only or explicit-seed search returns her. Core already owns scoped mention resolution; do not add another resolver in Buddy.

## Write ownership

- `src/dungeonmind/application/world_graph_retrieval.py`
- `tests/unit/test_world_graph_retrieval_service.py`
- this handoff

Remote main and open PRs checked; no open Core PRs returned. Existing local kernel work is untouched. One capability only. Verify through the real projection/retrieval service, including lexical competition, explicit seed precedence, mention overflow, ambiguity and scope. Preserve beginning/end refs for experiments. Inspect cumulative diff, tests and lint; push and open PR. PRIME-authored independent review required before merge. No other agents activated under the solo instruction.

Rollout after accepted review: pin the accepted Core dependency in a separate Buddy-owned deployment, then rerun captured question/source probes and a real Harness answer. Unit tests alone do not establish connected user acceptance.

Benchmark evidence is retained privately at `pippa-admitted-source-audit` in the existing World-context experiment: six source-backed questions on both APIs, plus changed name-only/seed probes and exact scoped resolver output. No corpus enters this PR. Migration requires no schema/data changes. Rollback restores the prior Core pin; preserve source roots and database authority during either rollout.

Topology: serial. No unmerged behavioral parent. PRIME owns post-merge re-anchor and release of the shared retrieval reader lease to the next reviewed-worldbuilding observation handoff.

Mutable predecessor sync: none; this changes bounded search prioritization, without activating or settling another runtime or publication lane. The consuming Buddy pin/rollout handoff will record this exact accepted Core merge and its adoption evidence.
