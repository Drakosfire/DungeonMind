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

## Buddy complete-object candidate and serving evidence

Buddy #3224 merged at `ffb666db75c388c5d3d2943eeeec616937136626` and
retains the Core package pin above. At that merge, 18 mounted inspection
tests and 29 preservation tests passed. The synthetic mounted complete-object
route returned response SHA-256
`ce456fb84f3938741c3242793b9a2974bb5f02b7295ad7f0a61d7177af4d234d`
across 21 reads, with a 4.01 ms median over the 20 warm reads.

The signed-in Graph surface on port 5202 displayed Elderwyld at
`rev:9a457bfed6bc517af83a7a719644970c`. It loaded 3,005 objects and
reported 3,828 omitted assertions with zero unexamined. The serving API
environment's installed Core distribution reported
`855f23bd8b20c3b91c27d0d065c3a3cfb0fef917`. Its OpenAPI schema lacked
the candidate complete-object endpoint.

The capped classic scale diagnostic terminated with exit 137 during
100,000-item World-like setup. It emitted no timing report. Buddy owns the
remaining proof for Elderwyld's authorized complete-object results, historical
pins, exact citations and timings on the candidate route. Use independent
expectations for Elderwyld and matched fixtures for classic/native timing
comparisons. Core owns the final joint artifact after that route evidence
and all required fixture semantics are verified.
