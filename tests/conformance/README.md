# Conformance tests

Behavior pinned against DungeonMindBuddy-derived fixtures. DungeonMindBuddy is
the workshop where the graph architecture was proven; these tests ensure the
product implementation preserves the proven semantics as modules are adapted
(see `Docs/Reports/RECON-2026-07-29-founding-inventory.md` §B for the
classification table and `Docs/Roadmaps/ROADMAP.md` for the import plan).

Planned sources (Buddy tests that become conformance fixtures, not copies):

- contribution merge / rebuild equivalence (`test_graph_kernel_contribution_*`)
- identity outcomes + merge/split/unmerge replay (`test_graph_kernel_identity*`)
- head publication / stale-parent (`test_graph_kernel_contribution_merge`)
- projection pinning + admissibility (`test_graph_kernel_world_projection`)
- retrieval session / claim ledger (`test_graph_retrieval_interaction`)
- evidence contract invariants (`test_graph_memory_evidence_contracts`)

Rules:

- fixtures contain synthetic or digest-referenced content only — never corpus
  prose, never player PII;
- mark tests `@pytest.mark.conformance`;
- a conformance failure blocks the adapting PR; it is never "fixed" by
  editing the fixture in the same diff.
