# MIND — indexed authorized alias-search read

COMPLETE — MIND_AUTHORIZED_ALIAS_SEARCH_ACCEPTED. Core PR232 merged
99e9eed4d1727adf5f754e386d3f4768f779021d. Reviewed implementation
bae427092b8d6f22a7f29a71c013e4f518a8c1cb, basecf197b9939f7b9106c75a8afb9fcf918c8b4aa1c;
independent Cycle1 source/evidence acceptance5979646558 via operator account.
The implementation write lease is released. Owner: MIND Elderwyld completion lane,
with explicit operator design/implementation/review/merge authority; no standing
Steward check-in or ARCHITECTURE/PRIME coordination gate.

## Accepted capability and proof

Public AliasSearchReadService returns currently authorized alias witnesses with
ambiguity evaluated before truncation and explicit partial status. Its optional,
versioned, entry/posting-bounded cache stores structural IDs/postings/full computed
parse-meaning identity only, not whole parsed revisions, contexts or admission.
Every read reauthorizes through existing alias standing/evidence/source gates.
Aliases retain accepted space-wide semantics; consumers still establish scoped
entity presence. Exact/phrase/token/plural and Unicode/boundary cases are covered.
First alias query still pays alias-linear index build; warm reuse removes that
build. Posting bounds are not a peak-byte or constant-query-work guarantee.

ParsedKnowledgeRevision, builder, parsed-format/compatibility/source-wire and
frozen V0 bundles are unchanged. Existing artifacts remain source-verified; actual
ordinary/artifact preparation and neighborhood reads pass with alias-index
construction forbidden. No storage migration, default activation or latency claim.
ADR0030 records the generic contract. Source/ranking authority is not the index.

CI44569694692 passed Core3074/11skip, SQL520/1skip, accepted WorldKeeper source
consumer, lint/types/import and tiny benchmark smoke. Tested merge3bd0e6081fcb3620ebc1e5857c521d9aadb94870
has expectedcf+bae parents and tree88e20db4f502c000fef0e27ca8b8adbe139c1893,
identical to reviewedhead. Frozen classic retrieval baseline was not rerun.
Local index47 and SQLartifact21 plus combined owning/artifact diagnostics pass.
Local full unit run remains3fail/3191pass under an invalid extras profile/missing
uv PATH; local fullSQL was interrupted with runnerexit143 and no terminal result.
Those records remain non-green; completed correct-profile identical-tree CI
supplies qualification. No remaining local runner or owned DB connection at audit.

## Next primary question and remaining work

Can Buddy consume exact99e9, combine the authorized assertion/alias candidate
streams before its cap, and preserve the selected-canonical-label navigation
contract under exact managed/native binding and current authorization? Inspect
SubjectSearch's actual acquisition constraints before assuming arbitrary general
search equivalence. Complete native candidate streams alone do not establish
classic label/ranking parity. No raw-index grants or search-result facts/source
pins; subsequent selected object reads remain independently authorized.

Buddy main was verified still pinned tocf197 at this acceptance. Pin adoption,
native SubjectSearch default proof, general agent Graph/search/related-recap
migration, current classic import retirement, guarded optimized deployment and
rollback, V11 serving baseline and full roadmap completion remain open. Merged
source does not establish what5202 serves. No live/provider/ingestion change.

## Retention and cleanup follow-up

MIND retains /home/drakosfire/Projects/.codex/v7-elderwyld-scope worktrees/cache and
scratch/v8-core/v10-authorized-alias-search/acceptance.json, with raw CI/local logs,
XML, failure and interruption evidence. Owned disposable DB
codex_v10_alias_search_a8e1c12f223a on32903 is retained; prior proof/live DBs were
untouched. No new worktree, manual deletion or reclaimedbytes claim. Projects UUID
48fa5d10-fe99-4557-9fc9-d8a2a4b41ac8 verified before allocation. Cleanup follow-up at
goal completion requires specifically approved scope and active task/process/mount,
DB connections, dirty/unique-data and protected-commit checks.

This one-file post-merge acceptance sync is based on99e9. It records known facts
without changing runtime/ADR/API or making a consumer implementation gate. Next
runtime work is in Buddy; its disjoint implementation can proceed independently.
