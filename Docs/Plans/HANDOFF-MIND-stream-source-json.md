# Bound mutable source JSON lifetimes during PostgreSQL verification

Status: CLOSED UNMERGED, rejected candidate PR225. Owner: Elderwyld pre-cutover optimization lane.
Authority: operator optimization goal with implementation/review/merge authority.
Base: accepted224 mergef174923bf7962f78d14faeb36a41f77004520676.

Outcome: PostgreSQL reads retrieve graph JSONB text; supported native root arrays
canonicalize one record at a time, discarding mutable row objects immediately.
Preserve canonical bytes, full fingerprint/payload SHA/column/envelope/revision-ID
verification on EVERY read, and the exact StoredKnowledgeRevision representation.
No verification cache/digest-only shortcut or authority change. Opaque/root shapes
fall back to ordinary JSON decoding/canonicalization; nonobject graphs still fail.

Six-path lease: private postgres/_graph_json.py, vnext_knowledge.py read selection/
reconstruction only, unit/test_postgres_graph_json.py,
unit/test_postgres_vnext_revision_reconstruction.py,
integration/test_postgres_vnext_knowledge_publication.py, this handoff.
No migration, store/artifact, source admission, publication write semantics,
Buddy, public contract, cache capacity/lifecycle, GC policy, prewarm or cutover.
Existing dict reconstruction remains compatible for internal direct callers.

Evidence: retained actual socket eviction/history fullGC207–248ms remains after
accepted parsed-map allocation reductions. Synthetic record streaming preserves
bytes on one shape and avoids component GC but has similar wall time; it is not
a performance proof. Whole-text depth scanning added~230ms/12MB and is rejected.
Use bounded per-record depth inspection with ordinary fallback for deep inputs.
The scratch prototype accepted malformed trailing commas/whitespace and MUST NOT
be copied without strict delimiter and JSON-whitespace handling.

Validation: canonical differential matrix incl Unicode/escapes, negative zero,
ints/floats/large numbers, permutations, duplicates, malformed/trailing syntax,
unknown/opaque/nonobject/deep shapes; random deterministic inputs; no whole-graph
loads on the supported fast path; input isolation/concurrency; same all-column,
fingerprint/payload/revision corruption failures for text/dict; actual PostgreSQL
JSONB text roundtrips and complete existing publication tests. Independent
cumulative review and exact CI required. Measure actual candidate full-app HTTP,
matched writes and affected routes before performance/V8 acceptance. Frozen
classic baseline must not be rerun.

Serial compute PR from224, independent of draft storage218. Rebase218 only after
acceptance; pinned local combination may measure beforehand. Reuse existing
Projects checkout/env; scratch/v8-core owner this lane, verified UUID48fa5d10-fe99-
4557-9fc9-d8a2a4b41ac8. Retain unique refs/evidence for dependent integration with
cleanup follow-up after explicit scope/process/mount/dirty/unique-data checks.
No new worktree/env/cache, manual removals or serving mutations. Cutover gated.

Disposition: do not ship. Measured runtime2955bd20daa1cb520462152f99e3f765604e61c6
combined with storage9f48bb7 at5e0d6f2099c495225c1b9fa859753c9b8cd1286c.
Actual full-app HTTP test passed in89.83s, exact responses/citations/freshness and
visible new/historical checks intact. Verification225–234ms, warm253–263ms,
first500–506ms, eviction712–713ms, historical720–731ms; fullGC206–212ms persists.
No end-to-end benefit. Frozen baseline untouched. Fixture dropped owned source DB.

Independent runtime review REJECT: fallback adds a Python serialization frame,
reducing supported depth near the recursion limit (CPython3.11.15, opaque nesting
992 reproducer). The depth80 test misses that boundary. This is unresolved in
candidate runtime; do not treat the branch as merge-ready or accepted.

Initial CI44411006825 core collection failed because the new PGunit module loaded
optional psycopg before skip; corrected in a test-only follow-up.70owningunit and
19owningPG checks passed with PG installed. Lint/PG type checks pass. No final CI
or review is claimed for a discarded candidate. Preserve failed CI/review history.

Retain candidate refs/probe/JSON/log/pytest output, private preflight and PG resource
receipt for negative evidence; owner optimization lane, cleanup after dependent
design work and explicit scope/process/mount/dirty/unique-data checks. Unit PG DB
codex_vnext_stream_a4c3a5faa2 was confirmed idle and dropped. No new worktree/env/
cache, manual filesystem removal or serving change. Next design must be a separate
bounded contract; this rejected parser does not authorize verification-cache work.
