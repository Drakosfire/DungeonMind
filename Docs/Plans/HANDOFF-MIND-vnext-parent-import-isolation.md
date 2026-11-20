# vNext parent-package import isolation

Status: ACTIVE. Owner MIND under explicit full-lane design, implementation,
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
