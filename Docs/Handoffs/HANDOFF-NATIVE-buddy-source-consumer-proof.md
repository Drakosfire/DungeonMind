# HANDOFF — native source contract return and Buddy consumer proof

**Created:** 2026-09-28

**Status:** DESIGN CHECKPOINT / BLOCKED — receiver/PRIME acceptance and lane allocation required; no implementation authorized

**Design owner:** ARCHITECTURE → MIND → DEMO/Buddy; PRIME owns acceptance and merge control

**Disposition:** no demonstrated new DungeonMind runtime prerequisite for the bounded immutable-source composition. Return the accepted contract; next proof/adoption is consumer-owned, not another Kernel feature.

**Design repository/base:** DungeonMind `daed279792402aa813c647251d21724c68768b03` (accepted PR #86 settlement); runtime authority remains PR #85 merge `7c69e447f6d4acc963ac09c6fb9cb48cc1c5b9cc`.

**Prospective proof repository/base:** DungeonMindBuddy `132cb80bea50ef2814074a52832ab763286a1900`; re-anchor before any dispatch.

**Keeper authority:** use Buddy's accepted dependency `49a8620f066ce7ef8972a699020c012f50af9158`. Current WorldKeeper main is `662a028fb1882719c4c3e192134a1a6b7a58026c`, with no open PR; newer main is not an automatic consumer repin.

**Prospective topology/title:** serial Buddy DEMO proof, `DEMO: prove persisted source consumption through native Keeper`.

**Execution authority:** none. A published handoff is not an ACTIVE lease, a runtime adoption, J3 activation or permission to open a successor PR.

## 1. Accepted return and the actual remaining questions

Accepted DungeonMind entry points and composition:

1. `initialize_empty_knowledge_space()` creates empty native authority with exact
   caller-selected domain/profile and durable replay. No campaign, source, graph
   seed or per-World database is required.
2. `publish_native_text_source_evidence()` over
   `PostgresNativeSourceEvidenceRepository` atomically admits immutable UTF-8 text,
   typed byte spans, evidence membership, child/head/event and receipts.
3. `open_native_text_source_access_context()` and
   `open_admitted_native_text()` give exact-revision, source-epoch-bound verified
   preview. This is not a claim-admission/citation result.
4. The native repository supplies the existing Keeper revision/publication ports
   and `open_native_source_view(space_id)` supplies targeted provenance/body reads.
5. Actual Keeper `DungeonMindWorldKeeperRuntime` can prepare/commit from that
   admitted parent; ordinary native assertion/evidence reads can see the child.

PR #85 accepted head `0803faf9f84b44148291c68c8dd115f73c68d464`, PRIME Cycle 2
PASS `5334796956`, merge above. Exact CI run `36386951061` reports core 2,046
passed/3 skipped, PostgreSQL integration 308 passed/1 skipped, benchmark smoke
passed. These totals are not a claim of zero skips or full product acceptance.
Its required actual-Keeper witness creates authentic evidence through the public
admission API, commits a fact, checks replay/stale parent, reopens PostgreSQL, and
verifies source preview and native evidence reads with `seeded_evidence=false`,
`provider_called=false`. The authored text/generic domain are honestly fixtures.

Buddy #779's previous HOLD is closed: Cycle 2 PASS `5331441470`, reviewed head
`2d5ab6ade1d89ec608c941093819ea36404fd18e`, merge
`2ccc96ff2a7d76328578609d5289fd3babcf6442`. It proves persistent composition,
not an ordinary production caller or real source producer. #780/V6.5 preserves
native evidence/anchors. Do not reopen these accepted findings as new work.

DungeonMind #86's documentation-only settlement head
`4f8c13da695ce59d44aaf8278df6666f5e11d30e` merged during the final anchor check
as `daed279792402aa813c647251d21724c68768b03`. It settled the existing source
handoff, report, steward handoff and roadmap. This branch incorporates that real
accepted main, changes none of those four files relative to it, and does not
repeat settlement or create a competing status ledger.

## 2. What is product integration, not a demonstrated Kernel defect

At the Buddy base:

- DungeonMind pin is still `b83baf82c381b1929c2c7989326d667200ff544c`, Keeper
  `49a8620f…`, GE `9122257f…`. No production caller imports the new genesis or
  native source-admission APIs. Library availability is not product adoption.
- `WorldKeeperGraphAuthoringConsumer` rejects blank campaign IDs and emits a
  campaign scope. Keeper itself supports `scope=()`. The former restriction is
  a Buddy mapper contract, not a missing Kernel World-global scope.
- `build_dungeonbuddy_read_context()` already maps world scope and real Buddy
  domain/profile/GM-player policy, but explicitly does not select production
  authority. The ordinary graph reader still selects its older World-shaped
  authority through `DirectAuthorityBinding`; repinning is not a read switch.
- APP-STATE `application_state.source.service.persist_source_markdown()` and
  `get_source_markdown()` already persist exact immutable source text, digest and
  returned revision UUID, with optional campaign/session and explicit World.
  That is suitable producer authority for this bounded source proof.
- Content WorkObject/Plan and the workspace document create DTO still require
  campaign identity. The BLOCKED World-owned blank Plan handoff owns that change;
  do not manufacture a campaign to make the first-customer path look ready.
- Legacy file/line/excerpt citation readers are not the accepted native typed
  source-preview contract. Ordinary Agent routing/source hydration is separate.

Immediate return: native initialization, evidence membership, exact-body preview
and Keeper-compatible persistent publication are available. Adoption, World-only
product binding and ordinary native reads are still missing in Buddy.

Source-fresh governed writes are a separate unresolved cross-owner contract:
Keeper prepare witnesses carry source pointers, not current authorization/body
epochs; commit does not consult mutable source authority. #85 exposes immutable
V1 admission, not lifecycle/revocation. Do not claim general freshness from
head CAS, stable IDs, an old coherent context or a successful body read.
That gap remains a **pre-J3 activation gate**, but it does not justify inventing
a DungeonMind freshness API without an accepted owner design and failing fixture.

V7 is later migration for existing durable Worlds. It is not a prerequisite to
the selected fresh-native proof and is not dispatched here. Existing Worlds keep
V7/V8/V9 obligations; no implicit migration, reset, dual-write or bridge shortcut.

## 3. One next consumer-proof invariant

Using accepted libraries in an isolated proof environment, Buddy's exact persisted
World-owned source revision can become native evidence and support one explicit
Keeper-created object/fact, then be read back through Buddy's actual native domain
context with verified source bytes after reopening both repositories.

Use actual public source persistence, Buddy domain/profile/request mapping,
accepted DM initialization/admission, actual Keeper and real PostgreSQL. A test
with inline graph/evidence seeding, a generic replacement domain, an in-memory
source reader, or a fake Keeper does not satisfy this consumer boundary.

This is **proof-only composition**, not ordinary GM navigation or product
authorization orchestration. A positive direct Keeper call must be labeled as
such; it cannot stand in for the mandatory-campaign Buddy authoring mapper.
Capture that mapper's blank-campaign rejection as a known consumer restriction,
not an expected failure that makes the whole product accepted.

Why this is useful beyond #85: it binds the product's real persisted source
revision/digest and actual Buddy policy to the accepted native ports. It turns
the remaining owner requests into concrete producer/mapping/routing evidence,
without another Kernel capability or a broad UI/J3 implementation.

## 4. Exact composition and failure/replay contract

Use a fresh test World identity; generated product source identity is distinct
from allocated DM artifact/revision/evidence IDs. Never repair IDs through SQL.
Source persistence returns a revision UUID; reload that exact artifact/digest/
revision, verify its World, and submit its UTF-8 text/digest and selected byte
interval to DM. Origin is an opaque Buddy source-artifact/revision reference,
not a filename or claim that DM authenticated another database.

Use current `dungeonbuddy_world_domain_contract()` and explicitly selected
`dungeonbuddy_dnd5e_custom_predicate_profile()` for a new native space. Preserve
their exact descriptor identities; do not invent a V2→V3 transition. A simple
caller-authored fact uses an already-declared Buddy predicate/value/claim mode.
No model or extraction is needed to test the execution/authority seam.

Keep the three durable transitions distinct:

```text
APP-STATE immutable source revision
→ DM admission child containing exact evidence
→ explicit Keeper confirmation child containing knowledge
```

DM does not promise one transaction across APP-STATE and Keeper confirmation.
If admission fails, the source may remain but no partial DM admission succeeds.
If confirmation fails, admitted evidence remains, not a fact or a rolled-back
source. Preserve the original operation IDs/receipts and recover known outcomes;
do not retry unknown success with freshly allocated IDs or invent rollback.

Preview checks digest/span/membership/visibility. Claim reads use
`build_dungeonbuddy_read_context()` and existing entity/evidence services with
the exact committed child and real native source view. Preview availability does
not confer claim visibility. GM/player and World A/B negative cases must exercise
these actual gates. They do not prove Keeper itself enforces mutable audience
authorization between prepare and commit; report that boundary as still absent.

## 5. Prospective lease, collisions and activation

No DungeonMind or Keeper production/test changes are assigned. No code, dependency
pin, migration or state-sync change is assigned by this design turn.

If the Buddy steward and PRIME accept/activate the proof, the initial Buddy lease
is exactly three new paths:

```text
tests/integration/test_native_source_keeper_consumer_contract.py
tests/fixtures/vnext/native_source_consumer_authored.md
Docs/Reports/REPORT-NATIVE-source-keeper-consumer-proof.md
```

Public service/domain code is verify-only. This handoff's pinned DM ref is portable
design authority; do not create a second live handoff copy merely for ceremony.
Any receiver activation/naming adjustment is steward-owned, not a worker choice.
No ordinary UI/API route, source mapper, read switch or general fixture refactor
fits this test-only lease. Required production changes return to DEMO for one
separately bounded adoption handoff.

Use accepted DM #85 source and Buddy's existing accepted Keeper source in the
isolated proof import path; record exact Git HEAD and actual imported module paths.
Do not alter Buddy's pin/lock or operator environment to run the proof. The proof
does not claim the installed product dependency advanced.

Live lanes at capture: Buddy #785 `07ec031a…` (serial DEMO), #786 `614bb686…`
(statblock compatibility), #781 `cf7f5698…` (interaction proof), Rules #763–765
(#763 holds dependency files), UI #760/#761. DM #86 released its four sync paths
by merging at the final anchor; Keeper has none. This BLOCKED proposal reserves
no paths. Default serial DEMO
means no additional proof PR while #785 remains open unless PRIME explicitly
records a parallel-independent exception and safe runtime ownership. Re-check
actual paths and dispositions before activation; branch separation alone is not
runtime isolation.

Require receiver/PRIME design acceptance, fresh main/pin/lease inventory, approved
test-only topology and a named disposable APP-STATE/DM database pair on the
development PostgreSQL before any proof IO. No live DEMO 54330/54331 targets,
operator runtime, API/UI ports, Firestore, licensed-source writes or provider
calls. Reuse one explicitly owned pair across test Worlds, not one DB per World.
Fixtures reject configured live DSNs, routing/query overrides and unowned targets;
no implicit create/drop/reset. Database provisioning/migration authority must be
explicit at activation. The eventual ordinary DEMO retains its existing fixed pair.

## 6. Required proof and commands after activation

New cohort must fail (not skip) when its declared accepted source checkouts or
approved disposable DB pair are missing. It must verify import origins before IO.

- Persist and reload actual APP-STATE source Markdown with World identity and
  null campaign/session; exact returned revision/digest and multibyte interval.
- Public native genesis/admission under actual Buddy descriptors; receipt
  identity, source origin, evidence membership and exact parent/child chain.
- Actual Keeper object/fact prepare is inert; explicit confirm commits once;
  exact replay after head advance returns same results; stale/foreign evidence
  rejects without partial knowledge. No seeded evidence or mocked Keeper.
- Reopen both repositories/connections; reload the exact producer revision;
  use actual Buddy world/GM/player read mapping, native entity/evidence/anchor
  services and verified body/span preview on the accepted child.
- Byte/digest/span mismatch, wrong World/space, hidden source, wrong descriptor,
  changed-command same-ID replay, admission failure and confirmation failure
  stay truthful and non-disclosing. Confirm partial-step states via public reads.
- Document that the current Buddy authoring mapper rejects campaign-free intent;
  do not change it, silently substitute a campaign or call the direct composition
  an ordinary product-path success. Mutable-source freshness remains unproved.

At the accepted DM checkout, only after approved test DB selection:

```bash
uv run --frozen alembic upgrade head
```

At the isolated Buddy checkout, require named `DMB_NATIVE_PROOF_DM_SOURCE` and
`DMB_NATIVE_PROOF_KEEPER_SOURCE` checkouts, plus approved explicit test DSNs
`DMB_NATIVE_PROOF_APP_STATE_DSN` and `DMB_NATIVE_PROOF_DM_DSN`. The new fixture
validates these and sets service configuration only inside the test process:

```bash
PYTHONPATH="$DMB_NATIVE_PROOF_DM_SOURCE/src:$DMB_NATIVE_PROOF_KEEPER_SOURCE/src:src:." uv run --frozen pytest -q tests/integration/test_native_source_keeper_consumer_contract.py
PYTHONPATH="$DMB_NATIVE_PROOF_DM_SOURCE/src:$DMB_NATIVE_PROOF_KEEPER_SOURCE/src:src:." uv run --frozen pytest -q tests/test_v6_1_dungeonbuddy_vnext_domain_runtime.py tests/test_v6_2_vnext_complete_object_adapter.py tests/test_v6_5_evidence_anchor_preservation.py tests/test_con_ready_play_worldkeeper_consumer.py
uv run --frozen ruff check tests/integration/test_native_source_keeper_consumer_contract.py
git diff --check
```

DM migration invocation requires its DB environment to match the approved DM test
DSN, never an ambient operator URL; APP-STATE uses its existing public migration
entry point against the approved separate test DSN. This is a prospective recipe,
not a command executed by this design turn. Required new proof has zero skipped
cases; record regressions honestly, no filtered-green surrogate for the invariant.

The tiny checked-in authored fixture proves producer authenticity of those test
bytes only. Do not copy licensed Of Conks into fixtures. Actual licensed/authored
GM material, ordinary source selection, review/confirm UI, later Agent citation
and process restart remain the later receiver-owned product witness.

## 7. Cross-owner acceptance, handback and stop conditions

MIND returns #83/#85 accepted contract/pins and this checkpoint to DEMO/PRIME.
Buddy/DEMO accepts product source identity, exact revision selection, domain/profile,
World scope and consumer-proof ownership. Keeper confirms its unchanged accepted
port/empty-scope behavior; no change to its witnesses is implied. PRIME decides
proof topology and keeps source-fresh preparation/commit and ordinary J3 gated.
Owner acknowledgments and the final activation ref are required; silence is not
cross-repository acceptance.

Handback: exact repo/base/head/import origins; actual lease; DB ownership and
migrations; commands/counts/skips; producer artifact/revision/digest; DM admission
and Keeper receipts/child chain; authorized reads/body/span; replay/negative/partial
states; explicit mapper/routing/freshness limitations. No full J3, DEMO, V7 or
runtime adoption token follows from this proof. Do not repeat #86's settlement.

If accepted ports fail under real Buddy descriptors/bytes, preserve the minimal
failing fixture, exact installed/imported versions and actual expected/observed
contract. Route to the owning repository for re-decomposition; only a demonstrated
Kernel defect can justify a new MIND runtime handoff. Do not open a speculative
repair, weaken a schema, edit another owner's lease or seed around the failure.

Other stops: false activation gate, serial/DB collision, production repin or route
needed, fake campaign, raw private body bypass, missing required PostgreSQL,
fixture-only claims of ordinary UX, implicit migration, live/provider/Firestore IO,
new lifecycle/freshness contract, or scope beyond the three prospective paths.

Next question after this proof: what is the smallest Buddy adoption transition,
and which exact source-authorization/freshness witness must bind preparation and
commit before J3? Design that with the actual product consumer and owners. Do not
assume it is another Kernel feature or prematurely move extraction ownership.
