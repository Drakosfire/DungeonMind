# CORE — pinned object read views

ACTIVE PRIME implementation lease from origin/main
617635c5da2eb66d3302998ca243f1111216a297 on codex/pinned-object-views.
Authority: OverMind #53 merge 5ffb18d2ce5c662f1c1b4c7b9e17ac3e7f2f181a,
Docs/Plans/HANDOFF-MIND-pinned-object-views.md. Independent Bugbot approved
that cross-owner contract. One capability: bounded and complete object views from
one captured exact-pinned read context, with existing selection and diagnostics.

Exclusive writes: src/dungeonmind/application/world_graph_retrieval.py;
tests/unit/test_world_graph_retrieval_service.py; focused existing retrieval
conformance tests if needed; Docs/Contracts/CONTRACT-pinned-object-views.md;
this handoff and predecessor HANDOFF-CORE-first-world-typed-source-spans.md.
No database/schema changes, consumer edits, source-body reads, service-wide cache,
compatibility fallback or live runtime changes. Buddy adoption is a separate PR
pinned to the exact Core merge. Preserve independently useful existing methods.

Reuse PRIME's existing first-world-spans checkout. No process cwd references were
found; its own inactive .venv editable reference is retained, and Buddy's test
venv has no editable reference to this checkout. Reuse Buddy Python with explicit
Core PYTHONPATH for in-memory tests; no new environment. Scratch/evidence stays
under /home/drakosfire/Projects/.codex/prime-first-world-spans/scratch/object-read-views.
PRIME owns cleanup after consumer adoption; retain unrelated checkouts and data.

Prove exact per-view parity, one projection/fresh next call, pre-IO validation,
mutation/head stability, scopes/misses/exclusions/visibility, reviewed provenance,
error propagation and truthful diagnostics. Independent exact-head Bugbot before
PRIME merge. No API8000/UI5202 or retained APP/native database changes here.
