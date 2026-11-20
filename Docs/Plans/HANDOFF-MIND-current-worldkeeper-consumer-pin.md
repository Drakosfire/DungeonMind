# V10 — current WorldKeeper CI consumer pin

Status: ACTIVE. Owner MIND under the operator's full-lane design, implementation,
review and merge authority. Serial predecessor Core245 accepted at
`7b79fc4d1b5d5a39a3a59800fc2c0759b200221f` (review5988191850, exacte50c,
CI44684331642 all3successful), then WK17 accepted at
`348c0dbf5156e7e7d5d951de90b9086501fc834f` (review5988177840, exactb1aa,
98 installed-wheel tests/Ruff/Pyright pass on locked Core4ccd). This assignment
is pinned before consumer configuration changes. Reuse the clean existing task
Core checkout on `codex/v10-current-worldkeeper-consumer`, base7b79; no new worktree.
Buddy's SQL qualification completed before releasing this migration-script root.

## Outcome, scope and dependency order

Core CI must prove native source admission and actual WK publication using the
accepted current WK ref, rather than its old49a862 checkout. Update both the
workflow checkout ref and the verifier's exact expected pin together. Preserve
all witness assertions, source-path attestations, commands, extras and migration
setup. This is one coherent consumer-qualification slice, not transaction work.

Exact four-path lease:
1. This pinned handoff.
2. `.github/workflows/ci.yml`: WorldKeeper checkout SHA only.
3. `scripts/verify_native_source_evidence_consumer.py`: EXPECTED_KEEPER SHA only.
4. `Docs/Handoffs/HANDOFF-v8-joint-acceptance-checkpoint.md`: settle Core245/WK17,
   record Buddy4222 exact qualification with explicit preservation diagnostic
   limits and merge-pending status, replace completed next-action wording.

Open Core158's shared index/roadmap lease excludes these paths; do not absorb it.
No package dependency, Core/WK runtime algorithm, stored/wire contract, migration,
source/admission semantics, test selection or publication/recovery assertion change.
The CI source overlay is intentional and must remain distinct from Buddy's
installed-package proof. No duplicate local SQL run for a pin-only change.

Serial delivery: this accepted consumer/checkpoint slice precedes Buddy4222 merge.
Buddy preserves Core90a5 and consumes the exact accepted WK348 merge. That adoption
has separate installed-wheel evidence; it is not proved by this CI source overlay.
Actual historical recovery and callable classic writer retirement follow under
separate bounded contracts. Neither import isolation nor hiding exports completes
V10, deployment/rollback or V11.

## Proof and disposition

Independent Hubble readiness PASS. Validate exact matching full SHA literals,
Python syntax, one-four-path cumulative scope, unchanged runtime/test/dependency
inputs, relative links, and byte-identical accepted V8/serving section. Run/inspect
all exact-head automatic CI checks and preserve the final integration witness:
WK348 checkout and actual WK/Core source origins, native admission/publication,
exact replay, stale-parent refusal and immutable child verification. Independent
exact-head source/evidence review and expected-head merge required.

Buddy4222 has exact62b9 installed WK98/native96/auth315 passes, hosted1412 selected
passes plus147 existing filter-pending, build/canonical/parity/cleanup success and
three green short workflows. WK14/Core178 installed files match348/90a5 before
and after qualification; all8 Core SQL fixtures zero-before-drop and absent.
Its preservation376 run is375PASS/1FAIL, not green: one unchanged relationship
adapter test expects classic prepare200; accepted4215 deliberately returns410.
A focused attribution execution with the old installedWKef9/Core90a5 on identical
parent runtime/test blobs reproduces the same failure. This is not separately
checked-out parent execution or a retrieval baseline rerun. Independent disposition
must be explicit; an owning retirement-test repair remains required before final
cutover, outside the three-path dependency slice. Do not silently rewrite its
assertions here. Initial failed importlib collection attempt remains unqualified.

No new full-discovered run: dependency-only slice without UI changes; retained
102 UI failures/two report-only collection extras remain explicitly non-green.
No frozen retrieval baseline rerun, ingestion, provider, serving or live World work.

## Resources and continuity

MIND retains task checkouts, environments, package audits, diagnostics and logs
under verified Projects UUID48fa5d10-fe99-4557-9fc9-d8a2a4b41ac8 for the active
full goal. Existing accepted environments stay untouched. No new worktree,
manual deletion or reclaimed bytes. Cleanup follow-up requires approved scoped
inventory plus active process/mount, dirty/unique-data and unique-commit checks.
