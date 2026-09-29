# HANDOFF — V7: exact-authority bridge-genesis migration

**Created:** 2026-09-28

**Status:** DESIGN CHECKPOINT / BLOCKED — §3 activation gates are made reviewable below; required owner artifacts/decisions remain absent; no implementation or live migration authorized

**Design/implementation repository:** `Drakosfire/DungeonMind`

**Exact design base:** `daed279792402aa813c647251d21724c68768b03` — accepted PR #86 settlement

**Activation-contract amendment base (remote main):** `c79fc297296afa8c110e51c357d21a4fbb70cdcc` — PR #93 merge; pinned historical review base, not activation authority

**Design branch:** `codex/design-v7-bridge-genesis`

**Owner:** ARCHITECTURE designs; MIND stewards DungeonMind; Buddy owns domain mapping; PRIME controls acceptance/merge

**Prospective PR topology:** serial, one DungeonMind V7 implementation PR after activation; no stacked prerequisites authorized

**Prospective branch/title:** `codex/v7-bridge-genesis` / `V7: migrate frozen authority into bridge genesis`

**Execution authority:** none. This artifact is a pinned design checkpoint, not an ACTIVE write lease, an implementation PR, a consumer cutover, or permission to migrate production authority.

## §1 One invariant and roadmap placement

An approved, coherently frozen legacy World authority can produce exactly one
native K0 with the same root identity, an exact migration-origin reference,
preserved durable identity and lineage, and an atomic recoverable receipt.
Repeating the exact operation returns that same result without additional writes.
Legacy immutable history remains byte/digest-identical and historically readable.

The falsifier is any successful receipt whose K0, provenance, identity map or
lineage differs from the approved frozen input, any partially committed target,
or any semantic widening hidden by a successful structural parse.

V7 implements migration mechanics and proves preservation on approved fixtures/
isolated frozen copies. V8 independently accepts joint semantic/performance
evidence; V9 owns the production freeze/migration/routing switch. V10 retires old
current paths. None is pre-accepted by a V7 merge.

Fresh native Worlds are a separate path. PR #83 accepted empty initialization at
`031b6650d0a506cf40f0189fc5cfac055ac37308`. PR #85 accepted immutable native
text-source/evidence admission at `7c69e447f6d4acc963ac09c6fb9cb48cc1c5b9cc`,
reviewed head `0803faf9f84b44148291c68c8dd115f73c68d464`, PRIME Cycle 2
`5334796956`. PR #86 settles that state at this design base. Those capabilities
do not import legacy authority. #85 allocates new source identities and requires
an existing native parent; calling #83 and then #85 cannot create V7's parentless
bridge or preserve legacy IDs.

Buddy main at design is `132cb80bea50ef2814074a52832ab763286a1900`, with DM
pin `b83baf82c381b1929c2c7989326d667200ff544c` and Keeper pin
`49a8620f066ce7ef8972a699020c012f50af9158`. The separate BLOCKED native-source
consumer-proof checkpoint is `d45a3e81ab70657b24ddae2fc6990cb5fbddf457` on
`codex/design-native-consumer-proof`. At this design base DEMO PR #785 head
`07ec031ab5b62b8dbcd34f51ed4b6eaf0fa25262` was open; it has since merged at
`f8b923875f9444a1addfb2472a2b8fab35eceb4c`. Its accepted J4 witness remains
limited to selected-World draft ownership/recovery; it does not prove graph
publication/read-after-write or complete J4/LOCAL DEMO. Do not transfer its
lease or fold its proof into V7.
DungeonMind has no open PR at this anchor; absence of a collision is not activation.

## §2 Binding authorities and limits of existing mechanisms

Read current `Docs/Architecture/AUTHORITY.md`, both vNext architecture documents,
`Docs/Roadmaps/ROADMAP.md`, `HANDOFF-STEWARDSHIP-vnext-roadmap.md`, the accepted
native source handoff/report, ADR-0019/0021, and the current contracts/code.

- `MigrationOriginRef` already binds source system/root/revision/payload SHA and
  migration-manifest SHA. Native revision identity includes this ref plus exact
  domain/profile pins, payload SHA, parent and ordered operation IDs.
- Historical `legacy_compat.py` serves schemas `dm_union_graph_v1` through V6.
  Its mapping revision is `dm_legacy_world_compat_v1`, manifest SHA
  `f408ce73b8efb32a36e4fb29eb68e9242cb358a76c0c0b60eafdce5046abbe4f`.
  It preserves historical revision identity and exposes compatibility terms; it
  is an oracle, not an approved native DungeonBuddy migration mapper.
- Compatibility scope/visibility terms and coarse historical metadata differ
  from Buddy's native domain. `legacy.unprofiled`, compatibility descriptor pins,
  and unknown historical epistemic meaning may not be silently relabeled as
  accepted product semantics. Structural conversion is not semantic acceptance.
- Graph publication locks the World row. Legacy source/identity mutations do not
  all share that lock. A graph-head check, World lock, or source-only repeatable
  read therefore does not prove a joint maintained authority freeze.
  `world_authority_recovery.py` is a read-only Eldyrwild preflight, not a generic
  exporter, writer fence or source/identity freeze implementation.
- Native publication has CAS and receipts. Public repository calls commit their
  own transactions; sequential source-import and publication calls are not one
  transaction. A native migration transaction must compose their internals.
- #85's global source epoch and lock order (epoch before space) are binding.
  Existing admission receipts, allocations, bodies, spans and reader behavior
  remain unchanged. There is no accepted public native head-rollback/delete API.

## §3 Activation gates — unresolved decisions are not worker latitude

MIND must re-fetch main and open PRs, then obtain and record all of the following
before changing BLOCKED to ACTIVE. New inputs may require revising this design
and returning it to PRIME; do not dispatch a worker to discover policy by coding.

1. **Buddy/domain-owner approved mapping.** Pin executable mapping version/code,
   domain/profile descriptors, complete identity disposition rules and owning
   semantic witness. Decide coarse/unknown claim metadata, scoped and GM aliases,
   relationship-to-assertion representation, old source classifications, and
   identity reconciliation (`canonical_rebind` included). No policy is invented
   by DungeonMind or inferred from the compatibility decoder. Supply a sealed
   owner-produced mapped payload/map plus independently reproducible mapping
   proof, or separately design the product-owned mapper; generic Kernel code
   must not import Buddy/TTRPG interpretation.
2. **Approved freeze/export authority.** Name the real authority owner, every
   participating writer, storage set, fence mechanism, coherent capture point,
   verification/release procedure and approved frozen fixture/copy. Exporter
   code/version and authenticated ownership of the export must be recorded.
   A caller-written checksum is not proof that the export was authoritative.
   If a maintained live fence needs new writer coordination, design that bounded
   prerequisite separately; this lease does not modify legacy writers.
3. **Source/body disposition.** Approve how each legacy storage class and evidence
   revision is represented and read. Preserve exact metadata and revision linkage;
   do not fabricate bodies/spans from line/locator strings or navigation flags.
   Historical evidence may reference a revision other than artifact.current.
   #85 preview requires equality to current; applying it blindly would narrow
   historical behavior. Do not broaden #85 in this slice. An approved separate
   bridge-body access contract is required if typed body opening is an acceptance
   requirement. Missing bodies, external locators, non-UTF-8 data, or bodies beyond
   #85's 1 MiB bound require explicit dispositions, never truncation/refetch guesses.
4. **Cross-owner proof and operating authority.** Pin Buddy mapping/read witnesses,
   exact frozen legacy fixture, isolated database/resources, allowed runner, and
   owners signing the matrix in §9. No production DB credentials/provider call
   or destructive reset is authorized. Any existing native target must be rejected.
5. **PRIME acceptance and refreshed lease.** Approve the additive companion
   contracts/receipt below, resolved decisions, exact activation base, all expected
   paths, serial topology and implementation/proof assignment. Inspect other
   active handoffs/worktrees and PR files again, not just this design-time list.
   Complete §10's bounded current-state control-plane closure before code
   activation; accepting this design alone is not a V7 implementation merge.

Current Buddy base domain/profile witnesses are `dungeonbuddy.world` revision 2,
descriptor SHA `d12f3a517a37d29a2ba52455d9ae1691bc5e4ff3fd6853b701a9e28e46ec65cd`,
and `dungeonbuddy.dnd5e` revision 1, SHA
`51ea47ff45bc86ea158939c34a5769e7ee56de3911278d473570e3795edb7e14`.
They are design references, not permission to apply these pins to every old World
or upgrade a V2-pinned space to V3. The approved mapping must select exact pins.

### §3.1 Gate record contract — required before V7 activation

Each gate is satisfied only by a pinned, reviewable artifact that records its
authority/owner, exact input identities, output artifact and digest, validation
method, failure disposition, and the owner attestation appropriate to that
boundary. A passing local test or a caller-supplied checksum cannot substitute
for an upstream owner's authority evidence. The gates are ordered dependencies;
work may prepare an owner decision earlier, but no V7 implementation lease
activates until all five are accepted at exact pins.

Collecting these gate artifacts does not authorize live fencing or export. Use
only an explicitly approved nonproduction frozen fixture/export already
available, or a separately authorized owner-capture prerequisite. This V7
handoff amendment grants neither live capture nor a writer-fence lease.

#### Existing D_A candidate qualification — design/rehearsal input only

`tests/fixtures/v7_bridge_genesis/authority_v1.json` qualifies the existing
checked-in Eldyrwild adoption bundle only as bounded historical design input and
a candidate for a separately approved D_A-only rehearsal. It records the exact
fixture commit/blob/file digests, derived counts and reference closure, the
different source-world revision `rev:0c644e56b45bcaac709012206e3e41c2`, adopted
DungeonMind D_A `rev:34b1f8e2625d5ba693fc726a2a1a4720`, and later recovery
checkpoint D_B `rev:680c246047d67f9fe0293ee90526f670` as distinct stages. It also
records fixture-local omissions, unknowns, external-body limits, and pending
owner attestations.

This sidecar is not an approved complete export, does not satisfy any §3.1 gate,
and does not turn fixture-local omission into proof of absence from source
authority. In particular, it does not contain post-adoption D_A→D_B history,
the M0/M1 repair lineage, body bytes or verified body access, a complete
writer/store census, or a freeze witness. MIND's evidence is limited to
read-only parsing, hashing, and linkage verification; Buddy/export/domain
owners, actual source/body owners, and the operator retain their respective
attestation boundaries. No V7 implementation or migration lease is activated.

| Gate | Required input → recorded output | Owner and sequence | Fail closed when |
|---|---|---|---|
| **1. Domain mapping** | Input: the complete frozen export from Gate 2 plus the source/body dispositions from Gate 3. Output: owner-versioned executable mapping/code digest; exact selected DomainContract and SemanticProfile descriptors/digests; a disposition for every durable identity and semantic record; mapped payload digest; and independently reproducible Buddy semantic witness. | Buddy owns product/domain meaning and the mapper. MIND owns a separate structural/identity validator, not semantic interpretation. Final mapping follows Gates 2–3. | Any record or identity is omitted, ambiguous, silently normalized, semantically unsupported, or mapped under unpinned code/descriptors; no compatibility-decoder fallback. |
| **2. Authenticated freeze/export** | Input: named authority, every writer/storage owner, and an approved nonproduction frozen fixture/export or separately authorized capture plan. Output: immutable export bundle with exact source/root/head/envelope/payload digests, full positive and negative storage/lineage inventory, capture point, exporter identity/version, fence witness where applicable, and verifiable owner provenance. | The actual legacy application/storage owners supply authority and writer inventory; the operator coordinates any separately authorized capture. They must be identified from the deployment, not inferred to be Buddy, WorldKeeper, or MIND. This is prerequisite to the frozen inputs for Gates 1, 3, and 4. | Any writer, storage class, mutation generation, capture interval, export owner, or verification/release procedure is unknown; a mutable snapshot or self-asserted checksum is not an authenticated freeze. Gate collection may not fence/export live authority without separate explicit authorization. |
| **3. Source/body history disposition** | Input: Gate 2's inventory and every evidence reference/revision. Output: a total typed disposition for each artifact and revision, preserving exact metadata, lifecycle/visibility, linkage and digest; each body is classified as retained exact bytes, immutable external reference with defined access, explicitly unavailable/missing, or rejected/unsupported. | The owner of each actual body/source store attests availability and retrieval/retention facts; Buddy decides product-semantic usability; MIND defines and validates only the generic destination representation. This follows the captured inventory and precedes final Gate 1 mapping and Gate 4 proof. | A record is dropped, a body/span is fabricated, a locator is treated as body, revision linkage is lost, or a body required by an accepted semantic/read witness has no supported disposition. Current #85 V1 admission limits do not decide historical bridge policy. |
| **4. Cross-owner preservation proof readiness** | Input: exact Gate 1–3 packages and an owner-approved historical fixture. Output before implementation: pinned Buddy mapping/read witnesses, immutable-history byte/digest parity, identity/lineage accounting, a row-by-row §9 proof plan with named owner and expected result for every case, and a reproducible nonproduction runner/resource plan. The actual transaction, replay, rollback and PostgreSQL results in §9 are implementation acceptance evidence, not prerequisites that must exist before code is authorized. | Buddy proves semantic mapping/read behavior; source owners prove export/body facts; MIND specifies the Kernel proof obligations; operator specifies isolation. This follows Gates 1–3. | A required §9 row has no owner, input fixture, expected result or permitted proof mechanism; mapping/history witnesses disagree; or the plan presumes shared/live resources. |
| **5. Exact target and activation lease** | Input: accepted Gate 1–4 artifacts, refreshed `main`/PR/worktree inventory, proposed path list, commands and recovery plan. Output: a PRIME activation record naming exact base/head lineage, owners, all writable paths, an isolated disposable target identity and emptiness check, permitted commands/resources, serial topology, required reviews, and stop/recovery conditions. Output also states that completed §9 runtime proofs are required before merge/acceptance. | PRIME owns activation/acceptance and merge; operator owns exact target/resource authorization; MIND owns its bounded implementation and proof. This is the final gate before any implementation code or V7 target mutation. | Target/database/resource identity is ambiguous or non-empty, lease collides or omits paths, a required owner/gate is unaccepted, or PRIME has not explicitly activated the exact lease. |

### §3.2 Fixed Kernel mechanics versus decisions still owned elsewhere

The following mechanics are already fixed by accepted DungeonMind code/contracts
and are not open Buddy policy: canonical JSON sorts object keys, uses compact
separators and UTF-8, preserves Unicode, and rejects NaN/Infinity; durable
canonical SHA-256 is defined by `dungeonmind.domain.canonical`; K0 uses the
existing `compute_knowledge_revision_id` schema and omits `created_at` from
content identity; `MigrationOriginRef` remains its strict five-field contract;
K0 has the exact old World ID, null parent, pinned approved descriptors, and may
not overwrite a non-empty target. Frozen V0 and existing source-admission
contracts are not widened.

Within an additive V7 contract, MIND can propose and implement deterministic
record ordering, duplicate rejection, digest domains, manifest/command
serialization, cycle-free hash inputs, golden vectors, exact replay comparison,
and atomic target semantics. §5 is the current MIND proposal for those choices;
the new schemas and golden bytes still require PRIME acceptance as part of Gate
5. Buddy supplies the exact mapped payload and its meaning, not Kernel hashing
rules. The following remain genuine cross-owner/operator decisions: who owns
each live authority/store and its fence; which descriptors/mapping rules accept
each legacy record; what historical bodies exist and whether any particular
acceptance requires their bytes to remain openable; and the exact isolated
target/resource and activation lease. No gate may turn an unresolved item into
worker discretion.

### §3.3 Candidate first capability — design only

After the owner artifacts exist and PRIME activates the exact lease, the narrow
first capability can be deterministic validation/construction from one
authenticated frozen export plus one sealed Buddy mapping package into a
canonical migration manifest and bridge-genesis command. Inputs are immutable
owner artifacts; outputs are the manifest/command bytes, digests, and a
validation report. MIND may verify completeness, IDs, closure, descriptor pins,
hashes, and exact target-space identity. It must not read or freeze live stores,
invent missing body content, choose Buddy semantics, or make the cross-owner
acceptance decision. This is a candidate within the single V7 implementation
PR, not an authorization for a preparatory runtime PR or an active code lease.

## §4 Prospective implementation write lease

The current design transaction changes **only this handoff**. After §3 acceptance,
the proposed V7 implementation lease is the following exact paths; paths marked
new are proposed, not existing capabilities. Re-review additions before activation.

- `src/dungeonmind/contracts/vnext/migration.py` (new companion contracts)
- `src/dungeonmind/contracts/vnext/__init__.py`
- `Docs/Contracts/vnext/dm_bridge_genesis_v1.json` (new additive schema artifact;
  frozen V0 bundle unchanged)
- `src/dungeonmind/application/vnext/bridge_genesis.py` (new public bounded operation)
- `src/dungeonmind/application/vnext/ports.py` (migration repository/read ports)
- `src/dungeonmind/application/vnext/errors.py` (bounded failure/recovery taxonomy)
- `src/dungeonmind/infrastructure/memory/vnext_migration.py` (new transactional double)
- `src/dungeonmind/infrastructure/postgres/vnext_migration.py` (new atomic repository)
- `src/dungeonmind/infrastructure/postgres/vnext_sources.py` (source-view composition
  only; no #85 contract/policy change)
- `migrations/versions/0012_vnext_bridge_genesis.py` (new; recheck sequence at activation)
- `tests/unit/test_v7_bridge_genesis.py` (new)
- `tests/integration/test_postgres_v7_bridge_genesis.py` (new)
- `tests/fixtures/v7_bridge_genesis/authority_v1.json` (design-only D_A qualification sidecar; not an approved export or Gate 2 evidence)
- `tests/fixtures/v7_bridge_genesis/mapping_v1.json` (new owner-approved mapping/witness)
- `tests/fixtures/v7_bridge_genesis/manifest_v1.json` (new deterministic golden manifest)
- `scripts/verify_v7_bridge_genesis.py` (new isolated proof runner)
- `Docs/Decisions/ADR-0029-v7-bridge-genesis.md` (new; recheck numbering)
- `Docs/Reports/REPORT-v7-bridge-genesis-acceptance.md` (new)
- `Docs/Handoffs/HANDOFF-v7-bridge-genesis-migration.md`
- `Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md`
- `Docs/Roadmaps/ROADMAP.md`

No Buddy, Keeper, Server, GE, dependency/lockfile, legacy writer, production route,
compatibility codec, frozen V0 bundle or #85 source contract change is leased.
If a required change crosses this list or adds another independent capability,
stop for split/rebrief. Do not open a second PR. Runtime isolation requires a
dedicated PostgreSQL database/schema agreed by the test owner, no shared DEMO
services/output/cache and no provider execution.

## §5 Frozen input, closure and digest definitions

Proposed additive schemas: `dm_legacy_authority_freeze_v1`,
`dm_bridge_genesis_manifest_v1`, `dm_bridge_genesis_command_v1`, and
`dm_bridge_genesis_receipt_v1`. Their exact fields/schema/golden bytes need PRIME
acceptance; do not modify existing frozen contracts to fit the import.

The freeze binds one exact source-system identifier, World ID, head revision ID,
original revision envelope/schema, canonical graph payload SHA and retained
ancestry references. Ancestry/old payloads remain legacy authority, not native
parents. Verify the exact head and payload rather than choosing the latest time.

Required source/evidence closure: every evidence record in the frozen graph;
all referenced artifact/revision records plus each artifact's current revision;
explicit missing-record entries; classifications, lifecycle, visibility, foreign
refs/domain metadata and exact revision/artifact linkage. Include typed proof and
body digest/disposition where approved. Missing/inactive/hidden evidence is not
silently fixed or dropped: preserve its historical record and fail-closed read
outcome. Capture all related mutation generations or the actual fence witness.

Required lineage closure: operation references, contribution/items/dispositions,
review/publication records, identity-decision versions/status/supersession,
reconciliation records, aliases and accepted adoption provenance needed to explain
the head. External producer records must have exact accepted bundle/authority
references; do not require them to masquerade as local contributions. Eldyrwild
M0 `membership_sha256`, sanctioned M1 `effective_membership_sha256`, exact member
manifest and sole accepted classification repair remain distinct immutable facts.
Do not re-submit contributions or identity decisions as new native operations.

Use `dungeonmind.domain.canonical.canonical_sha256` and its canonical encoding for
new JSON digests. Retain original payload/record digests and bytes independently
when historical encoding differs. Sort membership records by declared typed IDs;
reject duplicates. Preserve semantically ordered lists/order in original records.
No wall clock, row order, random UUID, host path, DB sequence or network result
may determine manifest/payload/identity. Pin an aware created-at input once.

Define separately:

1. graph SHA: existing stored graph's canonical payload digest, verified unchanged;
2. source/evidence SHA: canonical typed closure above, including negative entries;
3. lineage SHA: canonical membership/index of original record versions and hashes;
4. frozen-authority SHA: root/head/envelope and the three closure digests plus
   freeze authority/fence identifiers; mutable execution logs are not identity;
5. mapping SHA: approved mapping version/code, input authority SHA, descriptor
   snapshots/digests, complete identity dispositions and mapped payload SHA;
6. manifest SHA: canonical manifest over those exact pins, target space ID,
   publication/migration ID, fixed created-at and ordered bridge operation IDs;
7. command SHA: manifest SHA plus exact publication envelope/mapped payload used
   for replay comparison, without self-referential receipt/result fields.

The manifest must not contain its own SHA or resulting K0 ID, whose origin ref
contains the manifest SHA. Receipts may contain both. Changing any input produces
a different fingerprint, not an update of a previously accepted manifest.

## §6 Identity mapping and K0 construction

Every durable input ID receives a recorded disposition: preserved as the same
native identity; preserved only in immutable historical/lineage storage; or
represented by explicitly approved deterministic derived native IDs. No omitted
or silently renamed record. The map records kind, old ID, destination IDs,
reason/mapping rule and relevant source record hash. Mapping may be one-to-many;
merges require existing accepted identity authority, not name/text similarity.

Keep World/space, entity, evidence, artifact, source revision, usable assertion
and alias IDs wherever semantics permit. Global source collisions or derived-ID
collisions fail closed; equal bytes alone do not establish same source identity.
Any approved reuse of an already-global source must compare complete immutable
identity/provenance and record the cross-space disposition. Never mint replacement
IDs merely to make a collision pass.

Scoped/GM aliases cannot become unscoped `IdentityAlias` rows. Relationship/summary/
kind/label representations and coarse old metadata require the approved rules in
§3. Preserve ambiguous/rejected/retracted/superseded meaning; do not promote it
to active World truth. Record original versioned identity lineage without losing
`canonical_rebind` because the current V3 decision enum lacks that exact kind.

Construct native K0 as:

```text
space_id                         = exact legacy World ID
parent_revision_id               = null
expected_parent_revision_id      = null
migration_origin_ref.source_system       = approved exact legacy system ID
migration_origin_ref.source_root_id      = exact legacy World ID
migration_origin_ref.source_revision_id  = exact frozen legacy head
migration_origin_ref.source_payload_sha256 = exact verified legacy graph SHA
migration_origin_ref.migration_manifest_sha256 = exact manifest SHA
domain/profile                   = approved exact descriptor refs
operation_ids / created_at       = deterministic manifest inputs
revision_id                      = existing compute_knowledge_revision_id(...)
```

These are the existing five strict `MigrationOriginRef` fields, not new roadmap
pseudocode field names. Legacy graph schema/envelope remains in the frozen manifest
and retained historical records; it is not an extra field in this frozen ref.
If that cannot express the approved origin, stop for a separately reviewed
contract decision rather than widening V0/V1 in the migration implementation.

The new content-addressed K0 revision ID is necessary; it does not rename old
revisions. Validate canonical native graph, declared terms, metadata and complete
reference/identity mapping before publication. Reject compatibility-only pins or
placeholder semantics unless explicitly approved as a real native domain decision.
An existing target head from #83, #85, another migration or a later native write
is a conflict: no overwrite, synthetic child bridge, implicit rollback or reset.

## §7 Atomic publication, replay and recovery

Proposed operation `publish_bridge_genesis(repository, approved_input, command)`
validates the sealed input/mapping/freeze witness and delegates one atomic target
transaction. The generic operation does not discover live product policy or fetch
external source bodies. The proposed repository owns migration receipt recovery
and the bridge-provenance read view; not a second graph head.

In PostgreSQL, take existing global source epoch lock before the space lock, then
check replay/collisions and target emptiness. Commit the manifest/original lineage
records, mapped source provenance, any approved body/proof records, K0, existing
publication receipt, one head event/head, migration receipt and source epoch as
one transaction. Epoch increments only for an actual new commit. Reference existing
transaction helpers rather than calling separately committing public repositories.
All injected failures before commit leave no published target or orphan bridge
records. Source views must join approved bridge provenance at the same epoch,
O(1) view pinning and targeted closure reads; no live legacy-source fallback.

Keep bridge provenance in additive migration storage. Do not forge #85 admission
receipts, attach legacy IDs through its allocator, mutate its fingerprints, or
change preview semantics. Migration body policy must first satisfy §3.

Replay key is `(space_id, migration_id)` with exact command SHA. Same key/input
returns the original committed receipt and IDs without rewriting time/head/events/
epoch, even after later native head movement. Different input on the same key
is a conflict; another key cannot initialize the same space. Same migration ID
in different spaces is isolated. Concurrent equal calls produce one receipt and
one event; conflicting calls produce one winner and a safe conflict.

For unknown commit outcome, expose a safe outcome-unknown error and exact receipt
lookup/retry instruction. A new process recovers using the same key/fingerprint,
checks stored manifest, source/lineage closure, exact K0, origin and publication
receipt, and never guesses from current-head equality. Integrity mismatches are
failures, not replay success. No partial/raw source body is included in errors.

## §8 Freeze lifetime, rollback/restart and no dual write

V7 execution is limited to approved immutable fixtures/frozen copies; no current
production World switch. A coherent as-of export can remain a historical migration
candidate after live legacy writers resume, but it is not proof of current parity.
Production V9 must re-freeze/revalidate its exact accepted authority point and
must not use a stale V7 receipt merely because IDs match.

The operator owns fence acquisition/release and named recovery checkpoints. Stop
if any graph, source lifecycle/visibility/revision, contribution/review or identity
writer can mutate the captured input during the claimed freeze. Prove this with
barrier-based mutation tests; head CAS alone does not cover metadata writers.

Before commit: failure rolls back the target transaction; correct inputs/fence
may be retried under the same approved operation. After uncertain commit: recover
receipt first. After verified commit: do not delete K0, edit its manifest, rewind
legacy history or repoint native head to hide a defect. Preserve evidence and
return to PRIME. Restoring an explicitly disposable isolated DB from a verified
backup is an operator action outside the public capability, not a silent API.

If another live freeze is needed after a candidate was committed to the same
native target, activation/cutover must stop for an approved recovery strategy;
there is no accepted reinitialize/rollback mechanism to assume. Native rollback,
profile transition, source lifecycle and incremental catch-up are separate designs.

There is no mirroring service, continuous dual write, background importer or
automatic legacy-to-native catch-up. Keep ordinary consumers on accepted legacy
authority until V9 authorizes switching. Reads of old revision IDs stay on the
historical compatibility path; do not reinterpret them as native K0 descendants.

## §9 Acceptance/proof matrix — every required row must pass

The implementation report records exact DM/Buddy/mapping/fixture/contract pins,
manifest/result digests, each witness/result and any skips. The following named
groups are required; aggregate CI green is not a substitute for them.

1. **FREEZE_AUTHORITY — MIND + source/identity writer owners.** Coherent closure
   contains all positive/negative state and exact lineage. Barrier witnesses try
   graph advance, source revision/status/visibility changes and identity/status
   changes during capture/validation. A broken fence/stale export is rejected
   before target publication, or is demonstrably an immutable historical fixture,
   never represented as a current maintained freeze.
2. **MANIFEST_DETERMINISM — DungeonMind.** Two fresh processes and differently
   ordered DB/input rows produce identical manifest/command/K0 IDs and payload
   bytes. Golden hashes verify; mutations of each authority/mapping/descriptor
   input change identity or fail validation. Duplicate and incomplete maps fail.
3. **IDENTITY_LINEAGE — DungeonMind + Buddy mapping owner.** Verify complete ID
   accounting, relationship/alias transformations, merge/split/unmerge/rebind,
   ambiguous/rejected candidates, withdrawn decisions, M0/M1/adoption repair,
   external producer references and exact old operation records. No replayed
   historical operation acquires new truth.
4. **SEMANTIC_PRESERVATION — Buddy + independent reviewer.** Real approved Buddy
   frozen authority/witness proves exact entities/assertions/relationships,
   World/campaign/cross-campaign scope, GM/player exclusion, claim modes, time,
   aliases, evidence, anchors and missing/broken provenance outcomes. Use the
   unchanged historical decoder/witness helpers as an oracle plus actual Buddy
   native domain reads; do not compare two executions of the new mapper alone.
   Existing `build_historical_semantic_witness`,
   `build_parsed_revision_semantic_witness`, and
   `verify_historical_semantic_parity` remain historical-oracle tools, not
   substitutes for the owner-approved native semantic transformation.
5. **SOURCE_BOUNDARY — DungeonMind + source owner.** Preserve historical evidence
   to non-current revision, active/inactive/hidden/missing sources, approved body
   dispositions and locators. Digest corruption fails closed. No fabricated typed
   span, unauthorized bytes, widening, source fetch or #85 receipt forgery.
6. **PG_ATOMICITY — DungeonMind repository boundary.** Inject failure at manifest,
   lineage/provenance/body, revision, publication receipt, event/head and migration
   receipt writes. Zero partial target; exact transaction rollback. Verify source
   epoch and readers from another connection; concurrent #85 writes in unrelated
   spaces respect lock order and remain correct.
7. **REPLAY_RECOVERY — PostgreSQL + fresh process.** Identical/concurrent replay,
   changed-key/input conflicts, cross-space same migration ID, post-commit lost
   response and restarted receipt lookup. One K0/event/receipt, stable IDs/time/
   epoch; recovery remains valid after a governed native child advances head.
8. **COLLISION_NATIVE_REGRESSION — DungeonMind.** Existing #83/#85 target rejected,
   global/derived ID collisions rejected, unrelated native sources/spaces intact.
   Re-run #85 authentic actual-Keeper consumer witness without seeded evidence
   or provider calls. Migration does not mutate #85 body/preview contracts.
9. **OLD_HISTORY — DungeonMind.** Schemas V1–V6, exact historical payload/envelope
   digests and reader outputs unchanged before/after migration. Old parent chains,
   adoption/repair receipts and profile pins remain independently reconstructible.
10. **CROSS_REPO_DISPOSITION — Buddy + MIND + PRIME.** Approve mapping/semantic
    evidence at exact pins and identify product-route limitations. V7 acceptance
    says migration accepted, not V8 performance accepted, DEMO/J3 accepted or V9
    production cutover. WorldKeeper semantic ownership is unchanged.

Fixture bundle must include an owner-approved living-World frozen copy, six
historical schema cases, non-TTRPG and adversarial provenance/identity cases,
negative membership, external/missing bodies, accepted adoption repair, and native
target/global ID collisions. Do not manufacture a conveniently clean graph and
call it real-World preservation. Any required schema/decision unsupported by the
approved mapping is a named rejection/gate, not silently excluded from coverage.

Prospective commands (not run by this design transaction):

```bash
uv run pytest tests/unit/test_v7_bridge_genesis.py
uv run pytest tests/unit/test_vnext_legacy_compatibility.py tests/unit/test_vnext_revision_ids.py tests/unit/test_vnext_contract_bundle.py tests/unit/test_vnext_empty_initialization.py tests/unit/test_vnext_native_source_admission.py tests/unit/test_vnext_publication_recovery.py
uv run pytest -m integration tests/integration/test_postgres_v7_bridge_genesis.py tests/integration/test_postgres_vnext_knowledge_publication.py tests/integration/test_postgres_vnext_empty_initialization.py tests/integration/test_postgres_vnext_native_source_admission.py
uv run python scripts/verify_v7_bridge_genesis.py --authority tests/fixtures/v7_bridge_genesis/authority_v1.json --mapping tests/fixtures/v7_bridge_genesis/mapping_v1.json --expected-manifest tests/fixtures/v7_bridge_genesis/manifest_v1.json
uv run python scripts/verify_native_source_evidence_consumer.py --keeper-source .ci/worldkeeper
uv run pytest -m "not integration"
uv run pytest -m integration
```

Runner/interface names for new V7 files are proposed contract requirements, not
claims they exist. Use approved isolated `DUNGEONMIND_DATABASE_URL`; runner must
reject absent/unapproved target configuration, never default to production.
Before PG proof, sync the locked postgres/api extras and migrate only that approved
isolated database with `uv run alembic upgrade head`. `.ci/worldkeeper` must be a
verified checkout at `49a8620f066ce7ef8972a699020c012f50af9158`, as current CI does;
otherwise supply the approved exact checkout path explicitly. No new dependency
or unpinned download is implied by the commands.
Owning required PG/mapping/history cases may not skip; record unrelated inherited
skips separately. Benchmark smoke remains a regression, not V8 scale acceptance.
Design-only inspection ran no DB migration, provider inference or runtime proof.

## §10 Backward-looking authority correction and handback

At this exact base, ROADMAP §V6 still contains stale *current-status* claims that
native source/evidence admission needs a bounded design checkpoint or remains a
missing prerequisite. The steward's bounded control-plane acceptance/closure must
replace only those present-tense claims with accepted #85 runtime/#86 settlement
refs and **consumer adoption still pending**. Preserve the historical selection
of a fresh World, old dated reports/PR evidence, V7/V8/V9 obligations and the
separate World-only Plan/Keeper/Agent/freshness product gaps. Do not rewrite old
handoff research inventories as if they were written after acceptance.

The same transaction reconciles the steward's current-state summary/accepted-main
anchor, adds this handoff and its truthful BLOCKED/accepted design disposition to
the return point, and records completed predecessor facts. It does not pre-mark
V7 complete, activate an unresolved lease, or invent a merge SHA/review-cycle count.
If MIND/PRIME explicitly choose a reviewed control-plane design PR, these narrowly
scoped corrections belong with that design landing. Such a PR is not a roadmap
runtime implementation merge. Otherwise use an authorized guarded steward closure.
PR #87 is the single-file design checkpoint only; it intentionally leaves
ROADMAP/steward/runtime unchanged. The current-state correction must land before
V7 code activates, not wait for the implementation PR. Record that closure's
exact accepted ref at activation.

After implementation merges, re-anchor and settle V7 handoff/report/roadmap/
steward facts through the next authorized consuming slice or a guarded steward
transaction. Every formal review is bound to one distinct exact head; record the
real cycles without treating helper/CI reruns as new judgments.

Return to PRIME before implementation: this exact committed design checkpoint,
resolved §3 decisions/artifact pins, refreshed proposed lease, matrix witnesses,
and the truthful ACTIVE/BLOCKED disposition. Stop/rebrief on unsupported mapping,
unfenced writer, unknown source policy, identity collision, preexisting native
target, non-atomic storage boundary, historical drift, extra public capability,
lease conflict, production resources, or evidence that requires changing #85.
No category migration, consumer proof, ownership move or production cutover is
authorized by this V7 design.
