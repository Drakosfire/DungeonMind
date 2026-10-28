# MIND — publication type-check gates

ACTIVE PRIME prerequisite at 4ccd39a1e433d81569d86c05273ac33ee8f27ef3, branch codex/core-publication-type-gates. Reuses the serial prime-first-world-spans checkout; Core PR143 is waiting on this independent prerequisite. Its allocation module is untouched. No competing Core PR or runtime lease. Preserve the original 24-error audit in the existing scratch/core-type-baseline.json.

## Contract and exclusive write ownership
Repair existing publication/review type annotations and make already required fail-closed invariants explicit. No added acceptance families, coercions, fallback paths, new provenance authority, budget changes or dependency changes. Independent design critique approved narrowing only after exact builtin guards; preserve strict bool/subclass/nonfinite rejection. V4 already executes through shared helpers and memory records; annotate that existing behavior without broadening public V6 dispatch. Keep registry readback after insertion and publication rollback semantics.

Lease: this handoff; application/{publication_admission,review_materialization_v4,review_materialization_v6,review_publication}.py; contracts/{publication_admission,review_publication}.py; infrastructure/memory/repositories.py under src/dungeonmind; tests/unit/test_dnd_world_object_v7.py formatting only. Owning regression tests may be added only for these invariants. No allocator edits. The vocabulary formatting was proved AST/import equivalent to main in scratch/vocabulary-test-original-ast.json.

## Gates
Full locked Python3.12 Ruff/Pyright, owning strict JSON/publication/V4/materialization/repository/rollback tests and full non-integration suite. Inspect exact cumulative diff; independent Bugbot exact-head review; CI; PRIME merge. Then re-anchor PR143 on the merged prerequisite and repeat review/CI. Preserve all sources, revisions and runtime state. No runtime delivery until separately reviewed Buddy adoption.
