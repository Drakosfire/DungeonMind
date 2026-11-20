# O1 Core native revision turnover

The combined candidate met both 50% Core latency targets on the governed,
synthetic 10,000-entity PostgreSQL fixture. The accepted control was the source
tree from V11 Core `046791d09f7c0f7d3b348578763f9c87c7f1ecf1`.
Five fresh workers per variant ran in alternating order with an isolated
pgvector database and the direct verified-row reader.

| Measure | Accepted V11 | Combined candidate |
| --- | ---: | ---: |
| First child neighborhood, median (range) | 182 ms (168–222) | 25 ms (24–26) |
| Return after parsed eviction, median (range) | 173 ms (165–227) | 76 ms (74–97) |
| Governed prospective publication, median | 2,227 ms | 2,154 ms |
| Warm child neighborhood, median | 25 ms | 24 ms |
| End RSS, median | 161 MiB | 192 MiB |
| Peak RSS, median | 249 MiB | 253 MiB |

The read timer opens before the PostgreSQL-backed native context and closes
after the authorized neighborhood result returns. Publication is timed from
prospective materialization through the returned durable receipt. The
historical sample follows a child read and exercises one-entry parsed
eviction. The control uses one verification proof. The candidate uses two
proofs with the same 64 MB byte budget and opts into immutable record
retention. These are Core fixture timings. The V11 HTTP and live Elderwyld
measurements remain their own evidence.

The candidate eliminates one complete source reconstruction on publication
and another on historical return. The committed child reuses the parse that
artifact generation already validated, after rechecking the current primary
row. The returning parent reuses its exact primary maps and rebuilds the
parsed indexes and semantic digest. Fresh source views govern citation access.
PostgreSQL tests cover rollback, primary-row drift, cold-parser parity, exact
citation text and source withdrawal.

At 15,000 entities and a 7.56 MB source payload, one worker per policy
completed 12 alternating parent and child pin rounds with matching result
digests. The median parent return was 242 ms without record retention and
73 ms with retention. Peak RSS was approximately 343 MiB in each worker and
end RSS was 236 MiB and 227 MiB, respectively. This stress pair characterizes
one fixture below the 8 MB retention limit.

## Reproduce

Use the candidate checkout as the working directory and set
`DUNGEONMIND_DATABASE_URL` to an isolated PostgreSQL database with pgvector.
The integration fixture migrates and truncates its test tables. Set
`V11_CORE_CHECKOUT` to a checkout at the accepted Core commit and use the
same Python environment for both commands. Run each variant in a fresh
process, alternating which runs first.

```bash
witness=tests/integration/test_postgres_vnext_revision_turnover.py
PYTHONPATH="$V11_CORE_CHECKOUT/src" DUNGEONMIND_BENCH_ACCEPTED_V11=1 \
  python -m pytest -p no:cacheprovider -qs \
  "$witness::test_native_context_rebuild_on_child_and_parent_return[False-1-10000]"
PYTHONPATH=src python -m pytest -p no:cacheprovider -qs \
  "$witness::test_native_context_rebuild_on_child_and_parent_return[True-2-10000]"
```

Each worker prints its imported Core path, read stages, reconstruction
counts, proof content bytes and process memory. The next cost to investigate
is structural and digest reconstruction on a historical return after the
retained immutable records have also been displaced.
