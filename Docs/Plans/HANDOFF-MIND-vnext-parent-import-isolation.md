# vNext parent-package import isolation

Status: COMPLETE — accepted implementation; merge pending. Owner MIND under explicit full-lane design, implementation,
review and merge authorization. Serial Core successor to PR #247 at
`d206e56a9aa34ae6eb6cc7ac61980a7ac8919c4d`; branch
`codex/v10-native-import-isolation`, existing task Core checkout. Pin this brief
before runtime edits. This is an import prerequisite, not classic public-API
retirement or completed vNext deployment.

## Outcome and invariant

Importing current vNext contracts/application services or the native PostgreSQL
adapter must not eagerly load classic WorldGraph projection/retrieval/snapshot,
publication or adoption runtimes through parent facades. Resolve the existing
public facade aliases lazily, with the same objects, exported inventory, explicit
from-import/star-import behavior and public identity when requested. No current
or historical callable semantics, durable/wire schema, canonical digest, receipt,
policy, source authorization or storage behavior changes.

Preserve static typing with TYPE_CHECKING imports. Unknown attributes still raise
AttributeError; dir exposes advertised aliases without resolving every one.
Historical compatibility readers continue through application.compatibility,
which already owns decoders and terminal publication reading. Do not duplicate
that namespace or migrate retained receipts to vNext current authority.

PostgresRepositoryBundle remains an explicitly requested legacy aggregate. Its
construction may load old adapters; importing only PostgresDatabase or
PostgresNativeSourceEvidenceRepository may not. If moved to a private module,
preserve its public class module/name, constructor annotations and existing root
factory replacement behavior. No live database/registry/client construction at
module import. Existing default constructors and keyword behavior stay intact.

## Exact eight-path lease

1. This handoff, scope/evidence/limits and continuity.
2. Docs/Plans/HANDOFF-MIND-historical-publication-recovery.md: first-commit
   settlement of accepted Core247 merge/review/CI facts.
3. README.md: bounded current-state correction and import entry-point guidance;
   retain historical R.3 witness, do not claim deployed vNext or rewrite architecture.
4. src/dungeonmind/contracts/__init__.py: lazy alias facade, same existing inventory.
5. src/dungeonmind/application/__init__.py: lazy alias facade, same existing inventory.
6. src/dungeonmind/infrastructure/postgres/__init__.py: lazy aliases and aggregate export.
7. NEW src/dungeonmind/infrastructure/postgres/_bundle.py: existing aggregate
   construction isolated until explicit request; preserve identity/defaults.
8. NEW tests/unit/test_vnext_parent_import_isolation.py: cold import denial,
   native/legacy alias and compatibility behavior at the owning boundary.

No contract implementation/model/schema bundle, application service algorithm,
repository implementation, storage/migration, dependency, Buddy/WK source, benchmark,
CI selector, auth-policy or deployment changes. Rebrief MIND before another path.
MIND owns docs/tests; Hubble may own only the four runtime facade/bundle paths
once dispatched. Aristotle remains an independent read-only reviewer. One PR,
serial delivery. Read-only fixtures are allowed; do not edit their owners.

## Verified dispatch and sequence

Buddy4234 merged at `e4829505224a29ea9b4d3688ac22762588d60b05`; eight classic
Threat POSTs are retired. Current managed HTTP graph reads use vNext. Fresh Plan
and Play select native_graph_query_resolver with policy_bootstrap=None; the driver
uses native_graph_reads.read_selected with APP admission events. The classic broker
and object waves are required by retained original bootstraps. Execution class
PlanWorldGraphExecutionV3 alone does not identify current versus historical
receipt families. Do not rewrite those retained calls as fresh native reads.

Serial plan: (1) this Core import prerequisite, preserving aliases; (2) Buddy
repin/adoption and explicit retained-bootstrap/import quarantine plus disposition
of classic projection/recap/context entry points under later bounded briefs;
(3) remove old current/public Core exports only after consumers are isolated.
No unmerged parent stack. Later slices are design input, not active leases.

Core main re-fetched at d206 and matches Buddy's accepted pin. Eight open Core
PRs158/150/149/148/147/146/145/143 are retained independent lanes, not adopted.
Root facade regions and new private bundle/test are allocated to this import
slice; no legacy publication/correction/decoder implementation region is leased.
Existing task Projects parent UUID48fa5d10-fe99-4557-9fc9-d8a2a4b41ac8 and write
access verified. Reuse v10-core-unit/tools environments; no new worktree required.

## Owning proof and completion

- Cold subprocess/meta-path denial: current vNext contract/application imports
  succeed without classic graph/projection/retrieval/publication/adoption modules.
  With postgres extras, native adapter and database imports satisfy the same fence.
  No database connection, environment config, client or registry side effect.
- Explicit legacy aliases still resolve to original classes/functions/constants;
  identity, from/star import, dir, missing-name and typed aggregate constructor
  behavior remain. Historical decoder/terminal-reader conformance stays intact.
- Whole relevant Core unit/conformance suite, real PostgreSQL integration and
  changed-path Ruff plus required Pyright/CI. Retain all inherited skips/failures
  with exact scope. Build/install wheel and verify cold boundary/source origins
  so PYTHONPATH overlays are not passed off as installed-package proof.
- Independent exact-head cumulative source/evidence review, push/open PR and
  guarded merge complete this bounded slice. Do not rerun frozen retrieval
  baselines, call providers or alter serving data.

Still false: aliases are not removed, retained execution and mounted classic read
routes are not fully quarantined, serving authority/rollback/V11 are not accepted.
The full goal stays active after this prerequisite.

## Facade ownership rebrief before runtime edits

Actual patch inspection found older Core148 (`cfce638709f61a46a4eb9cc5aabe2b1504cbc275`)
and Core150 (`368e0c883ec85a4ba71d9940b353677f6d7b38d6`) also propose changes to
infrastructure/postgres/__init__.py. MIND, the operator-authorized owner of this
complete lane, allocates the current-main import facade/aggregate wiring region
to this slice. Their branches remain intact and unmerged here; their proposed
relationship-correction/existence features and constructor changes are not adopted.
Any later adoption requires a fresh rebase and owning review against this boundary.
Other inspected open patches do not overlap these eight paths. This is an explicit
current-file ownership disposition, not reliance on a future Git conflict or an
assertion that the older PRs were merged. No lease path or behavioral scope expands.

## Pre-acceptance verification and reflection repair

Frozen source `a793be35d04f8ae8d287665cfa3a4d88f1a74f9c` passed the
PostgreSQL cohort: 622 passed, one skipped, no failures/errors. Its uniquely
owned verification database was dropped at zero clients and absence verified.
Installed-wheel phases passed eight minimal cold cases, 26 PostgreSQL owning
cases and 172 historical conformance cases; all 362 facade bindings matched
the accepted d206 inventory. These checks did not prove source reflection.
Independent inspection found `inspect.getsource(PostgresRepositoryBundle)`
failed because its class definition had moved out of its public module. The
repair keeps the class definition in the public root and defers only wiring.
Class and constructor source inspection join pickle/signature/type-hint and
root-factory replacement proof in a cold subprocess.

The original full unit attempt is retained as failed: 3,363 passed, three
failed, seven skipped. One subprocess lacked uv on PATH; optional-extra
collection left SQLAlchemy loaded (also reproduced against accepted d206);
the new in-process pickle test encountered an older test's global module purge.
Use the locked default no-extras unit environment, an explicit uv PATH and a
separate nested smoke environment. Isolate the new reflection proof instead of
changing existing import-boundary assertions. Original logs remain evidence;
these findings do not waive the required repaired-head full unit run.

## Accepted source and remaining delivery

Accepted source: `b7255ba0fb3513831e59da432ea3e83b64d88c74`. Independent
COMMENT review [5993193078](https://github.com/Drakosfire/DungeonMind/pull/248#pullrequestreview-5993193078)
accepts this bounded import prerequisite. PR #248 remains merge pending until
the documentation seal is reviewed and its checks pass.

- Exact-source default locked unit run: 3,236 passed, 21 skipped. The 21 include
  ten new PostgreSQL-owning cases skipped without that optional extra; these
  ten pass in the PostgreSQL-installed wheel run. This minimal 3,257-case scope
  is distinct from the earlier 3,373-case extras-rich collection.
- Whole Ruff, Core/PostgreSQL/service Pyright and all 362 facade bindings pass.
  Synthetic 100-object CI smoke passes; no frozen retrieval baseline was rerun.
- Exact-source PostgreSQL: 622 passed, one skipped, no failures/errors.
  The owned verification database was dropped at zero clients and verified
  absent; both recorded process IDs are absent. Source stayed clean/unchanged.
- Built/installed wheel: eight minimal cold cases, 26 PostgreSQL-owning cases
  (including class/constructor source reflection), 172 historical/conformance
  cases, 219 package files and 362 aliases pass. Before/after installed origins
  and file hashes agree; all 21 recorded processes are absent.
- Hosted [CI44740012518](https://github.com/Drakosfire/DungeonMind/actions/runs/44740012518)
  passes core (3,236/21), integration (622/1), synthetic smoke and actual
  WorldKeeper `348c0dbf5156e7e7d5d951de90b9086501fc834f` source-admission witness.
  It executed test-merge `3536b2b8e27e9efabc76c8ccf59efa3922f80f7e`, whose
  tree `cba2f897e385d75198dee4cb7991e684b2c05dc1` equals accepted source.
  This is not direct execution of a later documentation seal or final merge.

Evidence owner MIND: task root
`/home/drakosfire/Projects/.codex/v7-elderwyld-scope`,
`scratch/v10-core-parent-import-isolation/{core-b7255ba0.json,sql-b7255ba0.json,ci-b7255ba0.log,wheel-b7255ba0/}`.
Retain its scratch/cache and distinct repaired-wheel environment for the active
full goal and exact-head audit; do not overwrite the a793 proof environment.
At this checkpoint scratch is 6,688,911 bytes and cache 157,552,276 bytes on
Projects UUID48fa5d10-fe99-4557-9fc9-d8a2a4b41ac8 (before this seal). No manual
filesystem cleanup occurred; reclaimed filesystem bytes are zero. Cleanup follow-up:
inventory active processes/mounts, dirty worktrees and unique commits before
any specifically authorized disposal after these artifacts cease to be needed.

Next serial slice adopts the accepted Core merge in Buddy and isolates native
projection presentation imports; retained-bootstrap and mounted classic-route
disposition remains subsequent work. No serving build or authority changed.
Public aliases, deployment, later-write-safe rollback and V11 remain incomplete.
The complete optimized Elderwyld cutover goal stays active.
