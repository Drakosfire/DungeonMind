# Complete entity batch: lint and optional-counter typing

Status: ACTIVE IMPLEMENTATION, bounded static repair.
Owner: MIND; root explicitly released the Core checkout after Core239 qualification
and independent review. Full-lane implementation/PR authority; root owns review
and merge. No ARCH/PRIME gate.
Pinned base: b6539db99fe5c961123bf7615c9d67cd4e40676b.
Branch: codex/v10-complete-entity-batch-lint-types.

## Outcome, authority and serial delivery

Restore static correctness of accepted complete-entity batching while preserving
runtime/admission/default/counter behavior. This is independent of Core239's atomic
source publication capability. Merge this repair first, then root reanchors239 and
qualifies its exact integrated source. Do not absorb this repair into239's19-path
lease. Core239 remote ee3eb3f945cc7c91902ec983d15402070f79ac7c is protected; no source
publication, repository, schema, dependency, profile, migration or protocol edits.

README.md, AGENTS.md and Docs/Architecture/AUTHORITY.md govern. Re-fetched main is
exactb653. Fresh public open-PR listing and complete paginated changed-file lists
for143,145-150,158,239 show no intersection with these4paths. PR158 process/Steward
scope remains untouched, as do all classic stacks and239. No old PR absorption.

## Exact4-path lease / review map

1. Docs/Plans/HANDOFF-MIND-complete-entity-batch-lint-types.md (new owning handoff)
2. src/dungeonmind/application/vnext/entity_reads.py
3. src/dungeonmind/application/vnext/read_context.py
4. tests/unit/test_vnext_entity_reads.py

- entity_reads: line-wrap found_ids and provenance subset guard. Annotate nested
  project(artifact_ids: Sequence[str], revision_ids: Sequence[str])
  -> KnowledgeProvenanceSnapshot using existing imports. Preserve union, order,
  duplicates, projections, callback boundaries, missing sets and counters.
- read_context: retain initial getattr(..., None) and non-None guard. Inside the
  guard use cast(_SnapshotCallCounter, self.source_reader).snapshot_call_count
  minus the observed before value. The private Protocol models optional existing
  instrumentation only. Preserve direct access/AttributeError semantics; no public
  protocol requirement, new counter/default, isinstance restriction, Any cast or
  error suppression.
- owning test: wrap one existing assertion only; preserve its complete membership
  and retracted/not-retracted semantics. No assertion/selection removal or waiver.

Changes are one static repair, not capability growth. No new test path; no mirrored
implementation test for annotations/formatting. Check meaningful existing counted
and ordinary reader behavior through the owning suites. Scope growth returns to
root before editing any other path.

## Verification and inherited qualification record

Existing task Core runtime cache/v10-core-unit (no sync), PYTHONPATH=src, task
TMPDIR; explicit existing Node PATH for owning-interpreter Pyright. Run:
- tests/unit/test_vnext_entity_reads.py
- tests/unit/test_vnext_knowledge_read_context.py
- full Ruff, Pyright with explicit runtime interpreter, git diff --check and
  cumulative4-path/source logic review.
No full suite rerun, database, provider, live, serving or baseline experiment.

Parent Core239 exactee3 full unit/conformance:3279passed1failed; failed cache test
pair reproduces0!=1 on exactbase and candidate. The suite remains FAILED, not green.
Exactbase full Ruff6 and Pyright1 were independently executed in retained16MB mirror
verification/v10-source-publication-base-b653; see parent-base-b653-static.json and
raw logs in scratch/v10-core/governed-native-source-publication. Core239 CI
44646724178: core lintFAILED before types/unit; integrationPASS including actual
WorldKeeper/adapters/service types; benchmark-smokePASS. Hubble5985803881 SOURCEPASS
with qualification HOLD; independent142passed. Parent61951 fullSQL finishedexit0,
ownedDB removed after zero active connections; count pending parent's script.
This repair does not erase/redesign/claim to fix the inherited cache failure.

## Resources, delivery and cleanup

Projects UUID48fa5d10-fe99-4557-9fc9-d8a2a4b41ac8 and actual checkout/scratch parent
writability verified before allocation. Reuse existing task checkout and tools;
no new worktree/mirror/environment, no root cache or global env configuration.
New scoped logs: scratch/v10-core/complete-entity-batch-lint-types, retained by MIND
for active-goal qualification. Prior239 evidence/mirror/cache remain retained and
untouched. No filesystem cleanup authorized; follow-up requires explicit scope and
active-process/mount/dirty/unique-data checks.

After owning/static checks: inspect cumulative diff, commit/push draft PR, freeze
exacthead for parent/Hubble. Root reviews/merges; no merge authority inferred from
this handoff. Full native manual adoption/UI/current-route retirement/deployment/
rollback/V11 objective remains active and separate.

## Static diagnostic checkpoint

Initial owning194passed. Literal no-default getattr triggered RuffB009; use one
local attribute-name string for the same optional lookups (no new counter/fallback).
Sequence annotations exposed that _build_snapshot_from_loaded requires tuple
requests; normalize its two requested-ID arguments with tuple(). Actual internal
callers already supply tuples, so values/order/duplicates remain unchanged. No
protocol widening, error suppression or admission/default changes. Raw Ruff1 and
types1 failures retained in scoped scratch. Recheck owning/static after correction.

## Root-approved final optional-counter typing rebrief

Root explicitly approves a private _SnapshotCallCounter Protocol with int counter
and typed cast under the unchanged getattr(..., None) non-None guard. Use that
instead of the intermediate local attribute-name solution (which passed Ruff2/
types2/owning2 but is not final). Keep direct attribute access/error semantics;
no Any cast, runtime isinstance, ignore, exported helper or KnowledgeSourceReader
requirement. Sequence callback retains tuple normalization at immutable builder
boundary; actual tuple callers retain identity/order/work. Update AST proof to
normalize only the private structural typing and typed cast, not broader behavior.

## Final scoped verification checkpoint

Final private Protocol/cast source: owning3 XML194passed0failed0errors0skips;
Ruff3 full repository PASS; types3 owning-interpreter Pyright0errors0warnings;
git diff --check PASS. scope-equivalence.json confirms exact4path scope, private
Protocol/cast/annotations/tuple-boundary normalization only, and unchanged test AST.
The intermediate initial diagnostic failures remain retained, not overwritten.
No full unit/conformance/SQL rerun or baseline experiment; previous3279/1 remains
an explicitly failed full suite with exactbase-reproduced cache failure.
Protected239 remote still exactee3; this repair is not silently included there.
Source inputs are frozen for independent review after commit/push/draft creation;
root owns merge and subsequent239 reanchor/qualification.
