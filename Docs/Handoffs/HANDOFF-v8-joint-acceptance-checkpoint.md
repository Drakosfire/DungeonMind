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

WorldKeeper [PR17](https://github.com/Drakosfire/WorldKeeper/pull/17) is qualified
but not merged: head `b1aa09b609e203b18fc0277282dc2932daeab58b`,
review5988177840. Its pinned five-path lease removes the eager classic adapter
from the native integration root and retains the identical historical class
under explicit `.compat` and its original direct module. Cold imports block the
WK classic module before any WK import. Exact installed-wheel98 tests pass with
zero skips; Ruff/Pyright pass,14 wheel source files match, and WK/Core origins
are isolated site-packages on unchanged locked Core4ccd. It does not prove
Core's own eager-import independence or Buddy adoption on Core90a5. This
checkpoint settles4215 before another roadmap merge; it does not relabel WK17
as merged or deployed.

Serial continuation:

- Accept WK import isolation, then explicitly repin/qualify Buddy while retaining
  Core90a5. Move Buddy's shared presentation carriers/helpers out of classic read
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

Implemented one-file continuity settlement awaiting independent exact-head review under the operator's full-lane authority.
MIND reuses the clean task Core checkout on
`codex/v10-classic-retirement-checkpoint`, base
`e83ab2664f6c953f4a8726ff053b24703440452a`. This lease was pinned at `957c386` before
updating the current checkpoint. Exact write lease: this file only.

Outcome: settle accepted Buddy4215 merge
`c19f4d90dc5628399009cdd12831d01bc5dd2c83`, tested3cdd, review5988124380;
record qualified but not yet merged WK17 headb1aa and its serial downstream
adoption; replace the completed classic-manual question with actual remaining
current/public retirement work. Preserve the accepted V8/serving section exactly,
performance/capacity limits and all uncompleted deployment/rollback/V11 gates.
Core244 settled4207 at mergee83; this settlement follows4215 and precedes WK17.

No runtime, dependency, contract, migration, benchmark, serving, provider or live
World changes. Core158's open shared-index lease excludes this file. Validate
one-file cumulative scope, unchanged non-document inputs, preserved accepted
V8/serving section, relative links and diff. No local runtime tests for prose.
Independent exact-head review and expected-head merge close this lease; any
automatic CI is reported separately from local qualification.

MIND retains existing task resources for the active full goal; no new worktree,
manual deletion or reclaimed bytes. Cleanup requires approved scoped inventory,
process/mount/dirty/unique-data and unique-commit checks.
