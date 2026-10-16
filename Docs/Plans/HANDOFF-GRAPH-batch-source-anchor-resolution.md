# Batch source-anchor resolution

ACTIVE. PRIME solo implementation; ARCHITECTURE independent review/advice.
Base `dd20b9734eeba5e17704c6e091bc0e61411e7964`, branch
`codex/batch-source-anchor-resolution`, isolated non-serving checkout
`/tmp/prime-mind-reviewed-source-search`. Serial topology: one Core PR;
Buddy consumer follows only after this exact contract is accepted.
Remote main and open Core PRs rechecked before activation; no open Core leases.

## Outcome and boundary

Resolve a bounded ordered set of distinct anchor IDs against one explicitly
pinned authorized projection. Establish the context and derive admitted anchors
once. Return a resolution for every requested ID, preserving order and explicit
misses. Context/integrity/unavailable failures raise; never substitute latest,
reuse serialized pins as authority, or return a misleading successful prefix.

Factor the existing single-anchor method through the same admission helper,
preserving its behavior and telemetry. Batch metadata is not source content,
proof of body availability, an opened passage, or a citation receipt. No schema,
repository queries, visibility rules, mutable cache, or publication changes.

The next Buddy contract will use these validated resolutions with existing
immutable-source body joins and actual-read receipts; it is outside this PR.
ARCHITECTURE recommended this boundary after a retained read-only diagnostic:
116 independent anchor reads took 134 seconds; all passages matched the exact
source. This is motivation, not a promised speedup or product acceptance.

## Exclusive write set

- This handoff
- `src/dungeonmind/application/world_graph_retrieval.py`
- `src/dungeonmind/application/world_graph_observability.py`
- `src/dungeonmind/application/__init__.py`
- `tests/unit/test_batch_source_anchor_resolution.py`

No serving ports, retained databases, corpus, provider requests, or runtime
configuration changes. Synthetic memory fixtures only for implementation tests.

## Verification and delivery

Prove canonical single/batch equivalence, exactly one context establishment and
anchor derivation, ordered found/miss results, strict input bounds/duplicates,
explicit pin requirement, foreign scope/admissibility/campaign/focus/revision
rejection, historical-versus-current correctness, and failure propagation with
one terminal batch observation. Preserve source/locator identity semantics.
Inspect cumulative diff; test, lint/typecheck affected contracts; commit/push/open
the assigned PR and send exact head promptly for independent review. No merge
until review passes. Preserve implementation beginning/end refs and failures for
local-model task evaluation. Settle superseded handoff facts in the next consumer.

## Author verification

The new batch boundary plus existing retrieval and read-observability suites pass
162 tests. Ruff and full Pyright pass (zero errors/warnings); cumulative diff
inspection/check pass. Initial pytest collection accidentally imported the installed
older package; reran with this checkout's `PYTHONPATH=src`. Initial lint found export
ordering and long test lines; corrected before the passing checks. A temporary
runtime `.venv` symlink used for type discovery is removed after checking.
No provider call, retained write, source read benchmark, runtime change, or claim
of improved end-to-end performance is part of this implementation evidence.
