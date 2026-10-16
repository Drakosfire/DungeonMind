# Verified publication discovery at a pinned revision

ACTIVE. PRIME solo implementation; ARCHITECTURE independent review/advice.
Base `f28000d557d97639dca65978fc237bbadc691c5f`; branch
`codex/publication-history-discovery`. Re-anchored remote main; no open Core PRs.

## Outcome and contract

Expose an embedded Core application read service that discovers finalized
publications on one exact World's pinned revision ancestry, selected by verified
reviewer ID and exact source-plan schema. Return the verified terminal publication
and durable review/contribution together, newest ancestor first, with complete
scan semantics. An empty successful result proves no matching publication on that
ancestry. Missing/cyclic/foreign/corrupt required records or unavailable authority
raise; they never become an empty result. Non-review revisions may have no terminal
finalized-review publication. Do not read mutable head to replace the supplied pin.

Use existing verified repository reads. No new schema, repository query, transport,
publication replay, provider, serving runtime or retained data writes. This explicit
review/reopen path may scan O(history); do not put it in every Agent turn.

Buddy will separately resolve its sealed run/source/managed World, derive selectors,
and map proven native assertions to candidate coverage. Actor/schema are selectors,
not proof that every candidate or source description was published. Historical
publication is distinct from current withdrawal. This slice establishes successful
publication discovery, not pending/failed attempt history.

## Exclusive write set

- This handoff
- `src/dungeonmind/application/publication_history.py` (new)
- `src/dungeonmind/application/__init__.py`
- `src/dungeonmind/application/world_graph_retrieval.py` (CI repair below)
- `tests/unit/test_publication_history.py` (new)
- `tests/integration/test_postgres_publication_history.py` (new)

## Owning evidence

Prove real publication and fresh repository discovery without original plan or
confirm calls; complete zero match; selector isolation; multiple publications and
interleaved non-review revisions; older pins exclude descendants; broken ancestry,
wrong World/revision, damaged publication/review joins and unavailable authority
fail closed; no mutation. Use synthetic memory and a newly created disposable
PostgreSQL database, never a retained DSN with truncating fixtures. Review cumulative
base-to-head diff, push/open one PR promptly, dispatch exact head to ARCHITECTURE,
then merge only after independent review. Preserve beginning/end refs for task gold.

Author evidence: 82 focused tests pass, including three fresh PostgreSQL discovery
and corruption cases, existing publication/withdrawal regressions, 130 intervening
revisions, and two matching historical publications after a description withdrawal.
The additional explicit two-receipt assertion passes in the 22-test focused suite.
Ruff and cumulative diff checks pass. Disposable database was removed. An initial
test-runner setup restored schema without Alembic version rows and failed migration
with DuplicateTable; the corrected runner starts from an empty disposable database
and executes real migrations. No retained data, runtime, provider or corpus writes.

PRIME scope amendment: CI exposed 38 inherited Pyright errors in the earlier
observation-selection constructor's untyped dict expansion (same failing Core job
on prior #127). Repair only that constructor through typed dataclass replacement,
preserving serialized result bytes, full-record selection and exact byte counting.
This sixth path restores the merge gate; no new retrieval behavior or contract.
Re-run observation-selection regressions and type checking; obtain independent
review of the amended cumulative head before merge.
