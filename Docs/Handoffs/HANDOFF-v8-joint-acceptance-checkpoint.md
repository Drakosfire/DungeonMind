# V8 joint acceptance checkpoint

V8 remains open. Core #169 merged at `41c74076a27abfcbbf7a8c84ede0f784fd75a3dd`.
Buddy #3203 merged at `73d3968b97f4f1a36c4bf2dc78a6f02c87b7be5d` and
pins that Core revision. Core #170 repaired the CAS benchmark at
`9ad499ccb73ddef8cd5dd740e5203ff4532f5350`.

Use the [V7 fresh-native scope](HANDOFF-v7-elderwyld-fresh-native-scope.md)
as the provenance anchor for Elderwyld. Serving authority has its own V9 gate.

| Evidence | Observed scope |
| --- | --- |
| Native source withdrawal | Core PostgreSQL tests cover rollback, retry, concurrent withdrawal, PDF withholding, pinned source views, and fixed graph history. Buddy's mounted inspection test verifies exact text before withdrawal and no text at the same graph pin afterward. |
| Buddy semantics | 296 native route tests passed on the locked #3203 PR head. They cover inspection, explorer storage, hosted access, governed-write behavior, and historical passages. |
| Core scale | The six native 10k harnesses passed their structural checks at the Core package pin. CAS used the #170 harness change. |
| Mounted inspection timing | At the Buddy merge commit, synthetic in-process warm medians were 7.11 ms for catalog, 6.53 ms for entity detail, and 3.89 ms for exact source. Each route returned a stable response digest across 21 requests. |
| Full native listing | The 10k synthetic fixture returned 3,354 entities and 10,000 admitted assertions at a 628 ms median over five calls against an already parsed revision. |

The remaining V8 work is to finish the capped scale diagnostic, verify
semantic-equivalent comparisons on the intended serving routes, and assemble
`dm_vnext_contract_acceptance_v1` with exact descriptor, fixture, and result
digests. Core owns the benchmark and joint record. Buddy owns route evidence
and its dependency pin. V9 follows only after joint acceptance and an approved
authority switch with rehearsed rollback.
