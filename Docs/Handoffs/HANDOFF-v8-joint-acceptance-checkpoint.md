# V8 acceptance and current V10 execution checkpoint

Status: **V8 ACCEPTED; V9.B native serving accepted; V10 IN PROGRESS; V11 OPEN.**
Owner: MIND, Elderwyld optimization/cutover lane under the operator's explicit
implementation, review and merge authority. This is current continuity for this
bounded lane; the full vNext goal remains active.

## Current code anchor and next slice

Core239 is accepted at `90a5aed43ca2a7f1c7539f7d57fe23d54a22d483`, reviewed
`4d58f2d67507d98c8a4aa80a58aa1a12d52d88c1`, review5986257814 and
CI44653743056 all three jobs successful. Its
[owning handoff](../Plans/HANDOFF-MIND-governed-native-source-publication.md)
records the atomic source-authorized publication contract and accepted evidence.

Buddy [PR4188](https://github.com/Drakosfire/DungeonMindBuddy/pull/4188) merged
`13ea571faffd9bdc3e909ade910be623f66e25db`, reviewed
`61c3dd9d7c540d259e0fb2890b555d8ed67d0ae1`, review5986476147. It consumes exact
Core90a5/WKef9 and proves both SUPPORT modes, canonical-name-equal aliases and the
complete closed kind/predicate mapping. Candidate874/Coreee3 runs remain earlier
diagnostics, not accepted-pin execution.

Buddy [PR4192](https://github.com/Drakosfire/DungeonMindBuddy/pull/4192) merged
`807e1771e8e3addc83ad5df42d4c7f56f1ad603f`, reviewed and tested
`5233d9c605e7344511e9a021a02f12180fea5c8d`, final independent review5986967724.
The native manual context/prepare/confirm backend is accepted: scoped APP Page and
run/artifact metadata before content; exact persisted source/index commitments;
all13 kinds/45 mappings; names, primary aliases, role and descriptions; atomic
SUPPORT/facts/aliases; current owner/binding fences and immutable original-packet
recovery before mutable eligibility. Empty active Worlds are supported; profile
adoption stays explicit. Mounted manual UI migration is accepted separately below.

Exact5233 qualification: owning96, authorization315 and native preservation376
passed with zero failures/errors/skips; hosted frontend1412, production build,
collection parity, canonical validation and verifier cleanup passed. All four short
CI checks succeeded. Eight owning SQL databases were dropped at zero connections
and confirmed absent;177 installed Core files matched the accepted pin. New files
were lint-clean under Buddy's lock-pinned Ruff0.15.7; eleven inherited shared F811
warnings remained, with no new diagnostics. Final main's disjoint history warmup
was inspected for coupling; these are tested-head results, not execution of the
subsequent merge tree, live deployment or full-release acceptance.

Buddy [PR4207](https://github.com/Drakosfire/DungeonMindBuddy/pull/4207) merged
`e3e9304e7e7397a0e6950c285e56d399cc4e6cd3`, exact reviewed/tested head
`45b87cd015ed7dfab9fa2fc2ec9f278c158939c8`, final independent acceptance
review5987678478. The mounted manual UI now uses native context/prepare/confirm,
explicit source admission/profile adoption, all13 kinds/45 relationships, exact
UTF8 witnesses and original signed-packet recovery. World coordination and
monotonic dispatch claims protect concurrent retries; ambiguous prior outcomes
cannot become safe-to-archive merely because a later attempt refuses. Retained
same-name endpoints stay distinguishable, and refused identity refreshes remove
stale choices. Classic saved packets retain their original protocol.

Exact45b qualification: all290 owning UI assertions passed; hosted1412 selected
passed with147 existing filter-pending cases, build/parity/canonical validation/
cleanup passed. Full discovered8331 passed/102 failed/2 pending: all102 failure
identities are retained from the accepted base, with no new failure/pending case.
Collection parity remains red from the same two baseline report-only extras;
there are no collection omissions. The21 replaced dispatcher assertions have an
explicit independently approved migration disposition;116 assertions were added.
The full diagnostic is not aggregate green or release qualification. Backend
owning96 and auth315 passed without failures/errors/skips. Eight qualifying SQL
DBs were dropped after zero connections and verified absent;177 Core Python files
matched accepted90a5/WKef9. Both applicable short CI workflows succeeded.

The merged4207 tree differs from tested45b only in the independently inspected
Backlog change. These are exact tested-head results and source equivalence, not
execution of the later merge tree or a new live deployment. Detailed evidence is
retained under the task's `scratch/v9-buddy/v10-native-manual-ui`, including
`root-final-qualification-45b87cd015.json` and `merge-acceptance-4207.json`.

Buddy [PR4215](https://github.com/Drakosfire/DungeonMindBuddy/pull/4215) merged
`c19f4d90dc5628399009cdd12831d01bc5dd2c83`, exact reviewed/tested head
`3cdd67cbcb324f81d992c799fce17e5bf00b5895`, final independent review5988124380.
Classic manual prepare now returns typed410 after existing ownership checks;
both local/hosted confirmation branches are recovery-only. The explicit legacy
published-Recap branch retains local object/relationship drafts and inspection,
with truthful local-only presentation and no fresh publisher. Managed native
Recap is unchanged; native Worldbuilding is not a Recap adapter.

Exact3cdd qualification:31 retirement tests passed with one explicitly optional
historical PostgreSQL witness skipped;96 native and315 auth tests passed without
failures/errors/skips. All114 owning UI cases passed in the full discovered run:
8334 passed/102 retained failures/2 pending, zero new failures/pending and no
omissions. The same two report-only collection extras leave parity red. One old
publisher assertion was retitled with explicit retirement disposition; four
assertions were added, including that replacement and an upstream selector case.
Hosted1412 selected passed with147 existing filter-pending; build, canonical
validation, parity and cleanup passed. The full discovered diagnostic remains
red, not aggregate release qualification. Eight SQL fixtures were dropped after
zero connections and verified absent;177 Core files match90a5/WKef9. Short
classification CI44681089141 passed. Initial diagnostics and the lock-refused
hosted attempt are retained as unqualified; the successful retry is distinct.
Actual later-main changes throughcd54 were independently inspected for coupling;
no execution of the subsequent merged tree or new serving deployment is claimed.
Evidence: task `scratch/v9-buddy/v10-classic-manual-recovery-only`.

Existing classic recovery still resolves mutable source/span/binding/admission
before receipt lookup; hosted ownership also reads mutable metadata. Recovery-only
prevents fresh publication but does not establish source-independent immutable
recovery. Preserve original packets and fail closed; stronger recovery needs a
separate exact read-only boundary before retiring its writer dependencies.

Next primary question: **Can current native consumers be separated from classic
imports, then remaining classic reads/writers be retired or explicitly historical
without losing exact saved selectors, receipt recovery or source provenance?**

WorldKeeper [PR17](https://github.com/Drakosfire/WorldKeeper/pull/17) merged
`348c0dbf5156e7e7d5d951de90b9086501fc834f`, reviewed/tested head
`b1aa09b609e203b18fc0277282dc2932daeab58b`, review5988177840. Its five-path lease
removes the eager classic adapter from the native integration root and retains
its identical historical class under explicit `.compat` and its original module.
Cold imports block WK's classic module before any WK import. Exact installed-wheel
98 tests, Ruff and Pyright pass on unchanged locked Core4ccd;14 wheel source files
match and installed origins are isolated. Merge package/test inputs are identical
to that tested head. This does not retire Core's own eager classic imports.

Core245 settled4215 at merge `7b79fc4d1b5d5a39a3a59800fc2c0759b200221f`,
exacte50c/review5988191850; CI44684331642 all three jobs successful. The current
[consumer-pin handoff](../Plans/HANDOFF-MIND-current-worldkeeper-consumer-pin.md)
updates Core CI's old49a862 WK checkout and verifier constant together to348.
Its intentional exact-source-overlay witness remains separate from Buddy's
installed-package qualification. No Core library runtime or dependency changes.

Buddy [PR4222](https://github.com/Drakosfire/DungeonMindBuddy/pull/4222) remains
merge-pending at exact `62b9f40752a9ae6dd1a89251756819be4b66a0d0`, base9f479.
Its three-path adoption preserves Core90a5 and all unrelated lock metadata:
only the exact WK reference changes. Installed WK98/native-manual96/auth315 pass
without errors/skips. Hosted1412 selected passes,147 existing filter-pending;
build/canonical/parity/cleanup and three short CI workflows pass. WK14/Core178
package files match348/90a5 before/after SQL; eight Core fixtures are absent after
zero-connection cleanup. Accepted earlier environments remain untouched.

Preservation is375PASS/1FAIL/0skip out of376, explicitly red. One unchanged
relationship adapter test expects classic prepare200, while accepted4215 returns
410 classic_manual_prepare_retired. A focused oldWKef9/Core90a5 execution on
identical parent runtime/test blobs reproduces that failure; this is not a separate
parent checkout or a retrieval baseline rerun. Record independent disposition in
its PR before accepting the dependency slice. An owning retirement-test repair
remains required before final cutover; do not delete the assertion or silently
broaden this pin slice. Current relationship UI already uses native-prepare/
native-confirm; its review-request carrier remains product-local presentation.
The initial WK importlib collection attempt is retained as unqualified; the
standard-mode retry supplies the98 passing installed-package cases. Later main287
editor-snapshot changes were independently inspected without concrete coupling;
no later merge execution or deployment is claimed. Evidence is retained in task
`scratch/v10-wk-native-consumer-buddy`.

Serial continuation:

- Finish Core consumer-pin and Buddy adoption acceptance while retaining Core90a5;
  repair the stale classic retirement test separately. Move Buddy's shared presentation carriers/helpers out of classic read
  imports without changing DTO bytes or saved pins.
- Disposition direct classic projection and recap-context-v2 separately. Native
  managed projection is not an equivalent protocol for saved historical reads.
- Establish exact historical receipt recovery with zero-write absent/corrupt
  refusal, migrate actual consumers, then retire Core's reachable fresh classic
  publishing host and library entrypoints. Quarantine legacy operator policy
  without rewriting immutable stored attestations.
- Retire actual old current/public Core/consumer surfaces, not just export lists;
  qualify installed packages and downstream pins. Then compatible primary/fallback
  rollout, later-write-safe rollback/restart/restore and V11 serving acceptance.

These are bounded dependent slices, not authorization for a single broad rewrite.
Full current/public retirement remains unproved; source inventory is not complete
external-consumer evidence. Repository merges alone do not satisfy deployment.

## Accepted V8 and serving evidence

The named V8 measured composition remains Core
`4b6516e2c0dfd81acaa4410b9b9bb9da18894c90` (#228) and Buddy
`0a746752da32324256d83b018e884aa7cb8ad692` (#4029). Core229 accepted V8 at
`f770098ad27b772e6351f2827a2b7bd6628705e8`. Preserve these as measurement anchors,
not claims that current main or serving processes load that composition.

Read the [canonical acceptance artifact](dm_vnext_contract_acceptance_v1.json),
[V8 decision](V8-joint-evidence-review.md),
[portable evidence](../Reports/V8-optimized-evidence-v1.json), and
[V8 acceptance contract](../Plans/HANDOFF-MIND-v8-optimized-acceptance.md).
Scope is [fresh-native Elderwyld](HANDOFF-v7-elderwyld-fresh-native-scope.md),
accepted Core174 and its47-session published-source cohort. No legacy bridge is
required for this World. Historical design names do not rename the rollout.

V9.A Buddy4041 qualified the integrated consumer. V9.B Buddy4079 merged
`e36abef5d75d543b7e8c656d611b93723757b362`, reviewed
`5b422140079b357e064176732b20918a85ba14d5`, review5971846921. Its actual5202 proof
covers84 matching read cases, exact citations, retained authority, loaded-source
attestations and same-version process rollback/restart; frontend1411 selected
passes/build/canonical/cleanup were recorded. The recorded serving mirrors were
Buddy4f4ed526/Core4b6516e. This is the last named proof, not a fresh process
attestation. Reverify actual UI/primary/fallback code, imports, assets, configuration,
schemas, binding and head before rollout. The Buddy serving runbook owns its
operational details and bounded recovery limitations.

## Proof obligations that remain open

- V10 is incomplete. The [historical-codec quarantine](../Plans/HANDOFF-MIND-v10-historical-codec-quarantine.md)
  is a bounded completed step, not full retirement. Replace actual fresh classic
  current-authority callers and reachable legacy fresh publishing surfaces. The
  mounted Worldbuilding manual UI is accepted; remaining public classic endpoints,
  Core exports/leaf APIs and actual Buddy/WorldKeeper consumers still require
  retirement or an explicit compatibility boundary. Preserve justified original
  receipt/source-page recovery and exact historical selectors.
- Profile4 declaration and the explicit1/2/3->4 API are accepted code capabilities,
  not an automatic World transition. Both serving primary and compatible fallback
  must support the selected descriptor and latest persistence before live adoption.
  Core0023 migration compatibility, later-write preservation, restart/recovery,
  backup/restore and rollback require qualification of the actual chosen pair.
- V11 must measure deployed cold/warm, eviction, new-revision and historical-return
  behavior with exact workload, loaded pins, scope/head, authorization, ordered
  results and citation identity. Record latency, work and memory. Bind the roadmap's
  improvement comparison to a named V8 artifact, separating the original2.12s paired
  native reference from optimized acceptance measurements and accounting for work
  already accepted. The V11 handoff must state how its measurements satisfy that
  requirement and publish the successor optimization handoff before completion tokens.
- The554.24ms historical-return sample remains above the approximately540ms frozen
  reference. Accepted V8 fresh-worker first requests were484.92/488.99/492.57ms,
  warm77.80–84.04ms. Three workers establish no p95 or universal no-regression.
  Observe and disposition this tail in V11; never conceal it with a median.
- Practical full-input ladder accounting is accepted through100/1k/10k. Both50k
  encodings failed primary JSONB insertion before artifact generation;100k was
  consequently unattempted. This is explicit capacity debt, not50k read timing,
  proven RSS exhaustion, universal capacity or Rules-like parity. Carry it into
  V11/successor work; do not invent a storage prerequisite or redesign without a
  demonstrated required workload and owning measured assignment.

Full V10 completion, compatible current deployment/rollback, V11 acceptance and
`VNEXT_ROADMAP_COMPLETE` remain false. The frozen classic reference is retained;
no rerun is authorized by this checkpoint. The new writer's derived-read-artifact
regression proves removed-work preservation, not deployed timing improvement.

## Safe parallel work and resources

Other product/hosted/combat lanes may continue within their own assignments. Core158
retains its shared roadmap/standing-role index files; this dedicated checkpoint
provides current technical continuity without absorbing that lease. Current code,
accepted architecture and pinned acceptance evidence outrank stale phase summaries.

MIND retains `/home/drakosfire/Projects/.codex/v7-elderwyld-scope` checkouts, caches,
source-bound reports, candidate environments and the exact-base verification mirror
for the active goal. The eight qualifying Core SQL fixture DBs were removed only after zero active
connections; logical DB sizes are not reclaimed filesystem bytes. Four older
interrupted-run fixture candidates remain retained at zero connections, with
partial outputs and their interrupted verifier workspace excluded from accepted
evidence. Attribute/check these before any approved scoped disposal. No manual
filesystem cleanup occurred. Cleanup follow-up requires explicit scope/authorization
and process/mount/connection, dirty-worktree, unique-data and unique-commit checks.

## Bounded checkpoint maintenance lease

This update belongs to the four-path
[current WK consumer assignment](../Plans/HANDOFF-MIND-current-worldkeeper-consumer-pin.md),
pinned at `fa49b0f` before implementation on
`codex/v10-current-worldkeeper-consumer`, base7b79. It settles WK17 after its merge
and before another roadmap merge. Core245's prior one-file assignment is closed.
Preserve accepted V8/serving evidence and all full-goal limitations. Independent
exact-head review and actual CI consumer witness are required before acceptance.
No new worktree, manual cleanup or reclaimed bytes; existing MIND-owned resources
remain retained with approved-scope process/mount/dirty/unique-data cleanup follow-up.
