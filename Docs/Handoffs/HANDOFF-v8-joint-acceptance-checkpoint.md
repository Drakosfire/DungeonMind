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

## Elderwyld PostgreSQL candidate evidence

Core main was `fe01182432e2cbca9864fa9965b7be8db726045c`. Buddy #3303
merged at `d9e56d6858632ee952e03eb5665f3cf8c397c484`, with Core pinned
to `b1fadd145a90565ae5938837e5bd67b6dc6e004b`. The runs used the Buddy
PR head `b7c2870de35c4ee5e092b60f84652d7f698d784e`.

- The shared complete-object endpoint returned stable semantic fingerprints
  and two source bindings at the Elderwyld snapshot head and parent. Five
  in-process HTTP calls per revision had medians of 1,650.49 ms and
  1,598.02 ms, respectively, using read-only PostgreSQL and a fixture
  managed-world binding. Anonymous calls returned 401.
- Elderwyld's classic head is an empty reset. A separate synthetic fixture
  with equal graph cardinality exercised both complete-object branches
  against disposable PostgreSQL. Twelve alternating requests per branch
  yielded medians of 17.10 ms classic and 20.28 ms native. The selected
  location facts and directed relationship matched. The ledgers retained
  their respective existence and classification/name assertions.
- The paired persisted campaign recap citation returned a 38-byte classic
  paragraph and the exact 40-byte native span including CRLF. Both paths
  withheld source text for a foreign campaign.

V8 remains open. The paired timing covers one synthetic selected-object
workload. The retained native listing and classic full projection have
different result contracts and timing boundaries. The Core operation
comparisons and canonical joint artifact remain prerequisites for V9.

## Fresh-native Elderwyld replay at the serving head

V8 remains open. Buddy #3370 merged at
`02b613c68727e9be852cd86065b0476ea8ba5a7a` with Core
`ab330d49864738ae54157fcaf2c95071ff072180`. The restored Elderwyld
head `rev:2320336c2bf9b6d3f5cf514f8e2dc9b6` reconciled 288 revisions
to one root, with one matching receipt and publish event per revision.

The authenticated candidate managed projection returned 3,008 nodes at
the head and 3,007 at parent `rev:643a89642dcd9ab74a63056fb0fa1e1c`,
with 2,651 relationships at both pins. The head response digest matched
across standalone HTTP and in-process HTTP. One retained citation opened
the same 1,276 bytes at both pins. Anonymous requests returned 401.
A separate authenticated scope check rejected stale binding and unrelated
campaign requests with 409 and withheld source content.

The serving build returned `revision_not_bridged` for managed projection
at the live native head. Both managed projection and shared complete-object
returned 404, then 200, then 404 when their candidate dispatch flags were
toggled off, on, and off against the isolated restore. A deployment
rollback rehearsal remains required. The restored classic head is empty,
so use matched synthetic workloads for comparative timing.

Buddy #3370 restored related-object search matching. A paired 10k
PostgreSQL fixture returned the same two mapped hits in order for one
exact-label query.

## Shared neighborhood and governed publication evidence

Core #184 merged at `45d04fb6691cb084b1d50feb1ddb7ab18f15a95d`.
Buddy #3409 merged at `7ab97e95680b17a042f7b90c5d45b31c1221ce53` and
pins that Core commit. The shared native World neighborhood route is opt-in.

The isolated paired PostgreSQL check on Buddy's reviewed head `4a3282f0d`
and the locked Core install returned the same three labels, two edges, one
shared-evidence anchor, and byte-identical UTF-8 source excerpt. The fixture
had no standalone attributes. A mounted native regression separately proves
standalone term-reference attributes under Buddy's native semantic profile.

The first observed two-hop request took 514 ms classic and 2,093 ms native.
Four repeats took 514–529 ms classic and 348–360 ms native. The profile
attributes the first native request primarily to loading and parsing the
immutable revision. Retain both observations for joint acceptance.

Separate 10k write diagnostics recorded 577 ms for classic finalized review
(two added nodes) and 3,059 ms for native parent load through governed
publication (one added entity). Both replayed exactly. Their parent assertion
shapes and accepted deltas differ. A matched write comparison and full
projection attribution and provenance remain open, as does disposition of
the first-request latency gap. V8 joint acceptance and V9 cutover are pending.
