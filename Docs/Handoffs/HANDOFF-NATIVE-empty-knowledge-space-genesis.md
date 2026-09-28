# HANDOFF — NATIVE: initialize one empty native KnowledgeSpace

**Created:** 2026-09-27
**Status:** DESIGNED / BLOCKED — MIND design adoption, V6 state sync and fresh activation required
**Owner/repository:** DungeonMind; MIND is designing steward, PRIME controls merge
**Consumer:** Buddy DEMO-J3 fresh-World doorway; no consumer implementation authorized here
**Design base:** DungeonMind `b83baf82c381b1929c2c7989326d667200ff544c`
**Buddy checkpoint:** `11d7b5801b51f664e7a6eeafcb2aa2b0f5922b71`
**Accepted WorldKeeper consumer pin:** `49a8620f066ce7ef8972a699020c012f50af9158`
**PR topology after activation:** serial — one assigned DungeonMind initialization PR
**Suggested branch/title:** `codex/native-empty-knowledge-space-genesis` / `NATIVE: initialize an empty native KnowledgeSpace`
**Phase placement:** post-V6 native-new-space prerequisite supporting DEMO-J3, not V7 migration

This pinned design is not an ACTIVE write lease. It authorizes neither runtime
implementation nor another PR. The author inspected accepted code/contracts and
review evidence; no new runtime witness has been executed or claimed.

## 1. Decision and accepted capability inventory

V6 preservation is accepted at Buddy #780: reviewed head
`dd1accc35e63e518555894db769a23c2a9c75171`, PRIME Cycle 2 PASS review
`5333525840`, merge `11d7b5801b51f664e7a6eeafcb2aa2b0f5922b71`.
Independent review records 98 tests, zero skips. Buddy pins DungeonMind to
accepted #81 merge `b83baf82c381b1929c2c7989326d667200ff544c`: reviewed head
`6a0a51f49a1f72bc336444908cff824c26516325`, PRIME Cycle 2 PASS `5331842204`.
That repair binds source visibility privately into anchor identity without a
public source DTO change. WorldKeeper remains at the pin above.

The requested end-to-end journey is NOT already accepted:

- **Container identity:** Buddy `POST /api/live/world-containers` calls
  `world_container_registry.create_world_container`. It allocates a managed
  World ID/name and an empty source directory. It does not create a native head,
  select a domain/profile, import a source, or allocate a database.
- **Blank Plan:** the UI can open a blank authoring shell without a graph head.
  Durable `POST /api/live/workspace-documents` → `create_workspace_document`
  → APP-STATE `create_plan` still requires `campaign_id`; `world_id` is rejected
  for `kind=plan`. The current World-only UI uses the World slug as campaign ID.
  This is not proof of the selected no-fake-campaign World-only Plan contract.
  That durable product repair belongs to Buddy, not DungeonMind.
- **Native authority primitive:** `KnowledgeRevisionRepository.publish_revision`
  and `PostgresKnowledgeRevisionRepository.publish_revision` accept a null-parent
  `PublishKnowledgeRevisionCommand`, then allocate the native namespace row and
  atomically publish revision/head/event. `publish_publication` additionally
  persists an exact receipt with replay. The port explicitly says it is **not a
  product write API**. No bounded public empty-initialization operation exists.
- **Keeper governed changes:** accepted
  `DungeonMindWorldKeeperRuntime.prepare_change/commit_prepared_change` consumes
  a native parent. `DungeonMindVNextPreparationAuthority.read_current_space`
  returns no authority without a head; preparation validates evidence against
  the parent's evidence witnesses. It cannot admit the first source/evidence.
  Its generic scope supports World-global assertions; Buddy's PLAY mapper still
  requires a campaign and is not a World-only production composition.
- **Persistent composition:** Buddy #779's
  `tests/integration/test_demo_j3_play2_persistent_vnext_postgres.py::_seed`
  publishes a synthetic entity/evidence parent through the repository primitive.
  It proves atomic child/replay/restart, not authentic first-source admission or
  an ordinary product genesis/read route. Preserve its historical meaning.
- **Sources and citations:** native `SourceArtifactV3`, `SourceRevisionV2` and
  `EvidenceRefV3` express classification, visibility, exact revision/digest and
  locator metadata. `KnowledgeSourceReader` and V4.2 evidence/anchor services
  enforce coherent admission/revalidation. V6.5 uses an in-memory source reader.
  The existing PostgreSQL source repository/Buddy source-admission adapter uses
  the older World-shaped source contracts. No accepted ordinary native
  source-registration/body-verification/evidence-admission path is inferred.
  Existing locator strings/navigation flags are not a new typed-body reader.
- **Agent:** existing Buddy Agent World-query/citation paths still use the World
  Graph adapters. Dormant native complete-object/evidence services plus PLAY-2
  restart do not prove ordinary native Agent citation of a governed child.

The smallest selected *DungeonMind authority prerequisite* is therefore a
public **empty native genesis operation**, composing mechanisms already accepted
in V5.2/V5.3 rather than asking Buddy to construct authoritative graph JSON.
It is independently useful and does not bundle the separate Buddy Plan, source
admission, Keeper composition or Agent cutover contracts.

V7 remains necessary for existing durable Worlds: exact legacy authority freeze,
deterministic manifest, preserved IDs and explicit migration-origin bridge.
A genuinely new namespace has no legacy history to translate. Do not label this
operation a V7 bridge, add fake migration origin, or mark V7/V8/V9 complete.

## 2. One merge-ready invariant

A trusted in-process caller can initialize one explicitly selected, previously
uninitialized native namespace using exact DomainContract/SemanticProfile
descriptors. DungeonMind publishes exactly one validated, completely empty
native genesis plus head/event/receipt in the configured repository transaction.
Exact replay/restart returns that same genesis; competing or conflicting
initializations cannot overwrite authority, add another root, or rewind a head.

The operation creates no entity, assertion, alias, evidence, source, campaign,
legacy World graph or second database. It needs no corpus, recap, imported
document, model call or fixture-seeded parent.

## 3. Public operation and ownership

Add an explicitly public transport-neutral application entry point, proposed
name `initialize_empty_knowledge_space`, exported from
`dungeonmind.application.vnext`. Exact local class/function names are latitude;
the semantic inputs and return below are not.

Inputs:

- repository implementing the accepted `KnowledgeRevisionRepository`;
- exact caller-selected `space_id`;
- exact validated `DomainContractDescriptor` and V2 or V3 semantic descriptor;
- nonblank initialization/publication operation identity and timezone-aware
  creation timestamp, stable for the caller's one create intent.

Return the existing exact `KnowledgePublicationReceipt`; its published revision
must be read back and verified through the repository before success.

**Identity distinctions:** Buddy allocates its managed container identity and
decides the explicit mapping to `space_id`. DungeonMind owns the namespace's
revision/head/receipt authority and computed revision ID. A display name, slug,
source path or DSN is never DomainContract/Profile identity. The caller selects
descriptors; DungeonMind canonical-hashes their complete contents and derives
their exact refs. There is no default/latest profile, inferred D&D domain,
environment-selected semantics or profile transition. Do not remint a Buddy
container ID or allocate per-World databases here.

The initializer accepts **no graph payload, evidence collection, durable object
IDs, migration origin or claimed existing parent**. Construct the canonical four
empty collections using the accepted native encoder; validate/build the parsed
revision and envelope before repository mutation. Set parent and expected parent
to null, `migration_origin_ref=None`, native schema, and one initialization
operation ID. Validate inputs before any write. Snapshot mutable descriptor
inputs so later caller mutation cannot change a sealed operation.

Reuse V5.2 CAS, V5.3 receipt identity/probing, canonical revision identity and
stored-revision verification. A narrowly scoped extraction of existing receipt
validation into a shared internal helper is allowed if needed; do not duplicate
a second recovery ledger or weaken ordinary governed publication checks.

Replay rules:

1. Same space, initialization identity, timestamp and descriptor bytes yield the
   exact same command/receipt/genesis, including after process reconstruction.
2. Same initialization identity with different authority/timestamp is an
   idempotency conflict, not permission to choose the old meaning silently.
3. Different initialization identity against an existing native head fails CAS,
   even if the graph is empty. No adoption, reset, rebase or new genesis.
4. After a child advances the head, exact original replay returns the original
   receipt/revision and **does not move the head**.
5. A thrown transport/repository call uses exact receipt recovery; known
   conflicts/integrity errors remain errors, and unknowable outcome is reported
   as such. A recovered receipt must match this exact requested command, not
   merely the same publication ID. Never infer success from current-head equality
   or an arbitrary scan.

This generic service does not inspect legacy World semantics. It cannot certify
that a name belongs to an existing legacy World or authorize its cutover. The
later Buddy composition must explicitly select a newly allocated container/
fresh native namespace, reject legacy destinations, and preserve all other
World routing. Absence of a native head is not evidence of absence of legacy
authority. No product route is changed in this slice.

The empty genesis is a native authority parent, not sourced knowledge. Keeper
prepare must still reject unknown evidence against it. Supplying a synthetic
evidence stub to make a first node+edge pass is forbidden.

## 4. Expected write lease, only after activation

```text
src/dungeonmind/application/vnext/initialization.py              # new public operation
src/dungeonmind/application/vnext/__init__.py                     # bounded export
src/dungeonmind/application/vnext/publication.py                  # shared receipt helper only if required
tests/unit/test_vnext_empty_initialization.py                    # new
tests/integration/test_postgres_vnext_empty_initialization.py    # new
Docs/Handoffs/HANDOFF-NATIVE-empty-knowledge-space-genesis.md      # activation/factual handback
Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md                 # completed V6 state/active pickup
Docs/Roadmaps/ROADMAP.md                                        # completed V6 state/bounded prerequisite
Docs/Reports/REPORT-NATIVE-empty-knowledge-space-genesis.md        # new owning-boundary receipt
```

Reuse existing public errors/receipt shapes. A required new durable contract,
database schema/migration, source writer, repository protocol/adapter change or
new public error taxonomy is a steward stop, not worker scope expansion.
Do not regenerate/change the frozen V0 bundle for a Python application entry
point. No Buddy, WorldKeeper, dependency, frontend, API-host or benchmark change
is expected. Normal init bookkeeping remains backward-looking; do not mark
this in-flight slice complete before its merge.

## 5. Activation and completed-predecessor sync

Before activation, MIND must:

1. adopt this phase ruling/design and synchronize both mutable MIND authorities
   to V6 COMPLETE / `V6_DUNGEONBUDDY_PRESERVATION_ACCEPTED`, with #81 and #780
   exact head/review/merge, 98/zero-skips proof and unchanged WK pin;
2. remove the stale V6.5 BLOCKED/current-next instructions in both their current
   checkpoint and final stewardship ledger; keep V7 undispatched and retain
   bridge-genesis obligations for existing Worlds;
3. coordinate Buddy V6.5 handoff/report settlement with DEMO: record accepted
   #780, release its implementation lease and reconcile any current-state
   roadmap mirror that still calls the proof pending. The report at the design
   Buddy head still says `V6_5_IMPLEMENTED_AWAITING_PRIME_CYCLE_2`;
4. re-fetch all owners/PRs and record exact implementation base, adopted handoff
   ref, serial topology and current source/runtime collision checks;
5. allocate one isolated DungeonMind lane and explicitly activate it. Current
   inventory has no open DungeonMind/WorldKeeper PR. Buddy #785 and #781 plus
   Rules #763–765 and UI design #760–761 are not authority for this capability;
6. name the permitted isolated PostgreSQL integration environment. No live/demo
   database, fixed-URL DEMO pair, shared APP-STATE store or consumer files are
   leased to the worker. PRIME controls review/merge, not this design author.

The two-document MIND correction may be accepted as a guarded steward operation
before dispatch, or carried backward-looking in the adopted implementation PR
with an explicit current checkpoint pinned for the worker. This branch is a
proposal, not a main sync or implementation activation. OverMind merge-control
authority is accepted at `bfd6490730089e857f2cf760f85b1c979837e3f8`; do not
create a routine documentation PR just for bookkeeping.

Unit tests are hermetic. PostgreSQL tests must exercise several spaces in the
**same** database URL and reconnect to it, never provision a database per space.
Existing integration `pg` fixtures TRUNCATE tables; they require an explicitly
owned disposable integration database/CI service, not DEMO's persistent pair.
No destructive cleanup/reset is authorized against user state. In implementation
handback state how the test fixture is isolated before invoking it.

## 6. Required evidence at the owning boundary

1. Call the **new public entry point**, not a handcrafted `publish_revision`
   command, against in-memory and PostgreSQL repositories. Exact parsed genesis
   has zero entities/assertions/aliases/evidence, null parent/origin, exact refs,
   exact payload hash, one operation, head/event/receipt correspondence.
2. No source/evidence/legacy graph/campaign rows or provider calls are created.
   Read-only test SQL may count/inspect rows, never seed or repair authority.
3. Blank/invalid identities, invalid/timezone-naive time, invalid descriptors
   and unsupported input types fail before writes. V2 and V3 descriptors each
   retain their exact identity/digest; changing descriptor bytes is not a default
   upgrade. Prove caller mutation cannot change an already accepted genesis.
4. Two distinct spaces in one fixed PostgreSQL URL initialize independently and
   remain isolated after new repository instances/reconnect. Test inputs use
   normal generated intent/space IDs, not product-facing manual-ID instructions.
5. Exact repeated request and process restart produce one revision/event/receipt.
   Same operation with changed descriptor/time fails unchanged. Different init
   operation against existing authority fails; race two calls on an absent
   space and prove one root, no overwrite/orphan or duplicate event.
6. Inject transactional failure after revision insertion: no partial namespace/
   revision/head/event/receipt commit. Simulated commit-success/lost-response
   resolves by exact receipt. Missing/corrupt receipt/child or unknowable outcome
   fails closed. Keep receipt/authority error truth and preserve original cause.
7. Advance a descendant using accepted governed materialization/publication,
   then replay initialization: original receipt returned, descendant head and
   all immutable history unchanged. The normal contribution path remains
   governed; initializer cannot carry nonempty content.
8. Build a real native read context over the resulting empty genesis with a
   test-owned generic domain policy/source reader: exact/entity/search reads
   return honest emptiness without source calls for nonexistent candidates.
   Record this as native-library proof, not ordinary Buddy Agent/citation proof.
9. Re-run accepted CAS/recovery/prospective/contract tests. Generic code imports
   no Buddy, campaign/GM/PLAYER, WorldKeeper or legacy initialization policy.
   Work accounting is bounded empty-payload construction plus indexed
   receipt/revision/head calls and CAS; no parent/full-space graph scan.

Verification, with PostgreSQL explicitly isolated and configured:

```bash
uv sync --locked --extra postgres
uv run pytest tests/unit/test_vnext_empty_initialization.py
uv run pytest tests/unit/test_vnext_cas_publication.py tests/unit/test_vnext_publication_recovery.py tests/unit/test_vnext_prospective_publication.py tests/unit/test_vnext_contracts.py
uv run pytest tests/integration/test_postgres_vnext_empty_initialization.py tests/integration/test_postgres_vnext_knowledge_publication.py tests/integration/test_postgres_vnext_prospective_publication.py
uv run ruff check src/dungeonmind/application/vnext tests/unit/test_vnext_empty_initialization.py tests/integration/test_postgres_vnext_empty_initialization.py
uv run pyright src/dungeonmind/application/vnext
git diff --check
```

Required new PostgreSQL cases have zero skips for acceptance. Report commands,
exact base/head, unchanged schema/dependencies, public signatures, row/event/
receipt counts, fixed-URL multi-space/restart proof, races, recovery failures,
regressions, work touched and remaining product gaps. Submit frozen exact head
to PRIME for review; no automatic merge or successor PR. After accepted merge,
MIND settles this handoff and both current-state authorities before dispatching
a dependent lane.

## 7. Exclusions and next question

Excluded: legacy freeze/bridge genesis/identity preservation, old Of Conks
adoption, profile transitions, source persistence/body storage/typed locator
design, source/evidence admission or membership publication, campaignless Buddy
Plan/WK mapper, production routes/Agent reads/citations, dual-write/wrappers,
fixture seeding, manual SQL/ID repair, migrations, reset/delete, other-World
cutover, providers/LLM execution, V8/V9 acceptance and performance redesign.

After this capability merges, re-anchor its exact revision. The next *knowledge
authority* question is how authentic versioned imported/GM-authored bytes become
durable native source records plus exact admitted evidence in a parent, with
typed locator, content digest, visibility, replay and fresh revalidation, so
Keeper may prepare the first real node+edge. Design that at its owning boundary;
the existing Keeper evidence-in-parent requirement must not be bypassed.

Separately DEMO must design true World-only durable Plan state (not World slug
in `campaign_id`), then a World-only Keeper/product composition and ordinary
native Agent read/citation after restart. These are named gaps, not dispatched
successors or a promise that empty genesis completes the journey. Reassess
ordering with DEMO after each accepted invariant; leave existing Worlds on their
accepted authority until V7/V8/V9 explicitly cover them.
