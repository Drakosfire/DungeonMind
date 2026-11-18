# Restore current main validation for the vNext optimization stack

Status — implemented, review and CI pending.

## Outcome and ownership

Restore validation of the accepted main behavior before merging native read
optimizations. This is an independent prerequisite on main
a672791bacd14a55da488b4639d95dfe39de3805. The operator authorized implementation,
review and merge in this lane.

Merge this prerequisite first, then rebase Core #211 onto that merge, then
rebase #212 onto #211's accepted merge. Measure final candidate pins before
V8 acceptance. The cold-read performance gate remains open.

## Bounded repair

Wrap three inherited E501 expressions in classic retrieval and its tests.
Annotate two optional pypdf imports for minimal-installation Pyright.
Both runtime source files and the line-wrapped test retain identical Python
ASTs relative to main.

Permit pypdf and pypdf.errors only in the existing native PDF validator module.
An AST regression requires both imports to remain local to
validate_native_pdf_body. Other application imports retain their existing
layer and third-party restrictions. Minimal core import checks still apply.

Skip the PDF writer exercise when the optional pypdf package is absent;
the dependency-bearing lane continues to exercise pages and encryption.

Update the frozen classic NeighborhoodResult field assertion to include
discovery_relationship_ids, discovery_hops, object_limit_pruned_ids and
object_limit_pruned_count, already accepted on main. The exact field assertion
continues to constrain the full current result shape.

## Verification

The affected import-boundary, native PDF region and read-context suites pass
in the existing dependency-bearing task environment. Whole-repository Ruff,
git diff checks and the three AST-equivalence checks pass. Exact-head CI will
verify the minimal installation and PostgreSQL lanes.

## Retention

Reuse the existing task-owned Core worktree under
/home/drakosfire/Projects/.codex/v7-elderwyld-scope/worktrees/DungeonMind.
Retain it for the optimization stack. Existing environment and retained
scratch are reused. Cleanup follows delivery after active-process,
dirty-worktree and unique-commit checks. No new environment or database
was allocated for this slice.
