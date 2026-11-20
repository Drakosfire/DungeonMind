# Verification-cache test import-generation isolation

Status: COMPLETE, CorePR241 accepted/merged, TEST ONLY.
Owner: MIND; root owns review/merge.
Merge:ecaaa2da0da1db028e260985cf8abc20ef6dfa9c.
Accepted code:671a361c98330df407f99fafeba0f24dd894b78e.
Review:5986075059. CI44651370225 all3terminalSUCCESS.
Initial stack parent:Core240 code36c5f1f0538716413ddd4b90000af0ccf41997b7,
accepted merge757cc986a55aaba7013e27724e42ef50f814804c (identical tree).

## Accepted outcome and exact boundary

Only this owning handoff and tests/unit/test_postgres_revision_verification_cache.py
changed. Collection-time global k captured the original base adapter, while a
function-local native import after legitimate optional-module cleanup captured a
new generation. The Mock observed the old generation and incorrectly saw0!=1.
Move only native import_module assignment beside k, AFTER pytest.importorskip
('psycopg'). Both adapter references now share one collection generation.

All29 assertion ASTs,2uncached/1cached expectations, injection/wrap targets/private
functions and the rest of the test AST are unchanged. No production/runtime/cache
policy changes, import-boundary test edits, module restoration, skips or waivers.
Original root audit established no overlap with239's16,240's4 or classic/process
PR paths. No other work merged/closed/superseded by this test-only repair.

## Proof and honest execution identities

Scoped scratch/v10-core/cache-verification-import-isolation/final-671a361.json
binds source/command/XML/log/AST proofs. Unchanged parent-equivalent test bytes at
handoff-onlydd24615 reproduce ordered pairRED1pass1fail0!=1. After the one import
move, same pair2pass, full cache module26pass, full unit/conformance3207pass0errors/
failures/skips, fullRuffPASS and Pyright0errors0warnings. Those broad runs occurred
before final commit/integration with verified identical code/test inputs, not a
new integrated-head full execution. Final committed671a ordered pair2passed.

Parent240 merged while child full run was live; no head/source edit occurred until
terminal. Accepted parent main757cc was then integrated normally and the child PR
opened against main. Exact240 code/merge trees equal. CI44651370225 all3success
and root/Hubble accepted review are separate final-head delivery proof.
Original Core2393279/1 and exactbase red receipts remain retained as failures;
239 must integrate accepted quality repairs and rerun its own current full suite.

## Settled ownership and continuation

Original2-path lease released after merge. Root explicitly authorizes this
handoff-only seal within239 reanchor, no additional code/test ownership. Merge
order240->241 is complete;239 now integrates acceptedecaaa. No environment sync,
newenv/worktree/mirror, DB/provider/live/serving/baseline work by this repair.
MIND retains unique red/green/static evidence and protected commits for active
full goal; no cleanup/deletion. Follow-up needs explicit scope and process/mount/
dirty/unique-data checks. Full native manual/UI/retirement/deployment/V11 remains.
