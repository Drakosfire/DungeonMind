# REPAIR: fence reviewed identity publication preconditions

Status: IMPLEMENTED, SOURCE REVIEW PENDING. ROOT activated the portable proposal SHA dda53487c4827e405c128654fe33249c077e94faac190027f843b6558ba6944d after freezing rebind checkpoint 1dda0b5274d24292c7a3661de7b124e06dc7628b. No data/runtime activation.
Repository: Drakosfire/DungeonMind.
Design base: main 4bf8333bbc3fb3c848701d80f2d0f3e20ce0ef84, tree 152882d3c0e2bb00f2c711a7bdb21ff89b90711d, independently read through GitHub branch metadata. The deployed replay consumer is still pinned separately to a501784f21aaafb46d7561f46397a3afdc42f125. No pin or runtime adoption is implied.
PR topology: SERIAL, prerequisite before the existence-evidence rebind implementation.
Suggested title: REPAIR: fence reviewed identity publication preconditions.
Canonical destination in the same implementation PR: Docs/Handoffs/HANDOFF-REPAIR-reviewed-identity-publication-preconditions.md. No separate handoff/process PR or prior main landing is required for this pinned portable contract.

## One invariant

A new finalized-review publication that uses one reviewed HUMAN_OVERRIDE must atomically prove that exact active, unsuperseded decision and its selected authoritative source records while holding the same existing per-World fence as graph parent CAS, child and receipt publication. A decision/source change ordered before this publication rejects without child or receipt. A writer ordered after a successful publication cannot retroactively invalidate that historical receipt. Exact durable receipt replay remains read-only/idempotent.

No corpus-to-native registry, new effect model, locking framework, graph-data repair or identity-decision creation belongs in this slice. Core does not interpret Buddy's corpus-reference spelling or reason prose as proof of equality; Buddy owns that reviewed semantic attestation. Core fences the selected native authority records and immutable parent preconditions committed by the review.

## Actual boundary and concurrency facts

The existing application publisher accepts world/review IDs, reloads durable review, constructs an internal publication command, and asks the publication repository to commit. The PG repository already takes lock_world (worlds row FOR UPDATE), rereads review/parent and atomically publishes child/head/receipt. It currently has no selected identity/source precondition.

Identity records and ordinary source artifact/revision puts are insert/reconcile, not unrestricted mutable upserts. Different bytes for an existing ID fail. A newly appended active superseding decision can nevertheless invalidate a selected decision without changing graph head. Postgres _append_identity_in_transaction currently does not acquire lock_world. Typed source-classification changes in existing_world_adoption already take the World lock; ordinary puts must not become a bypass. This design reuses those existing owner locks, not an optimistic precheck outside the UoW.

The precise present failure window is after Buddy's last ledger/catalog read and before Core obtains its publication lock/commits. Repeating the Buddy read does not close it.

## Immutable typed commitment

Add one strict, frozen, versioned nested ReviewedIdentityPublicationPreconditionsV1 value, with exactly one selected decision and 1–16 sorted unique artifact/revision pairs. Required fields:

- native world_id, campaign_id, expected_parent_revision_id;
- selected decision_id and complete canonical native decision payload SHA256;
- target_object_id, target full parent-object SHA256 and ordered existence-evidence SHA256;
- each source_artifact_id/source_revision_id plus complete canonical typed artifact/revision SHA256;
- no paths, credentials, raw source bodies, arbitrary mappings or executable callbacks.

The selected record must be ACTIVE HUMAN_OVERRIDE in this World; its exact subject/target/actor are committed by the complete native record hash, and target must be the declared existing native NPC. Reject any active same-World decision superseding it. Validate target standing, immutable parent evidence closure and exact source-pair coverage; source artifacts must be active, belong to the declared World/campaign, and revisions must belong to their artifacts. Core must reject malformed/foreign/missing records, conflicts and unproved closure. It must not parse or infer a corpus identity from reason prose.

Introduce guarded typed variants of the existing V2 review intent and durable review record, and internal publication command, with REQUIRED nested preconditions. Keep legacy models unchanged: no added nullable/default field in legacy serialized objects. Explicit guarded/legacy decoding must preserve the guarded subtype on round trip. The nested version distinguishes the new capability; same outer V2 review/state and V1 internal-command schemas are acceptable only with actual PG constraint/JSON round-trip proof. If constraints require another outer schema or migration, STOP and rebrief before editing an unleased path.

For guarded intent only, add the nested canonical preconditions to digest material. Finalization must persist that identical commitment in the guarded review record; the state validator must recompute the guarded intent digest from durable content. Existing review ID/confirmation/receipt identities then bind the commitment through review_intent_sha256. Legacy intent digest material, records, command bytes and receipt bytes remain exactly unchanged.

Application publish_finalized_review derives preconditions ONLY from the stored guarded review record. It accepts no caller-supplied replacement guard. Its internal guarded command carries that exact value; repository validates command versus the stored record. No absence/downgrade from guarded record to legacy command is allowed. The existing publication receipt need not duplicate the commitment because it already commits the guarded review intent hash; demonstrate that correspondence on fresh readback.

## Owning UoW and writer participation

PostgreSQL: acquire existing lock_world first, reload review and immutable parent, verify command/guard commitment. Resolve exact already-published receipt before live-authority eligibility revalidation (after immutable command/record identity checks); return it unchanged even if later decisions supersede the carrier or the head advances. For NEW publication, read/verify selected decision and same-World supersession set while holding the World lock. Read selected source rows in sorted ID order, using row-share locks for artifact rows until commit as defense against typed catalog updates; revisions remain immutable but their payload fingerprints must match. Complete all checks before _publish_revision_in_transaction and receipt insertion on the SAME connection. Mismatch raises existing integrity/stale-authority failure with safe detail, rolling back without new child/head event/receipt.

Make _append_identity_in_transaction acquire that same lock_world BEFORE inserting/reconciling any native identity decision. This includes active superseding records and any owner path invoking that helper. Preserve identical append/replay results; no new identity data. Existing typed catalog-changing publication paths already lock their World. Make ordinary _put_artifact_in_transaction participate in its artifact's existing World fence before insert/reconcile; for _put_revision_in_transaction derive the owning artifact's World and use the same lock before insertion. No unqualified updates or source lifecycle API are introduced. Audit all typed source/decision writers for the same order; a bypass is a STOP, not evidence that publication is fenced.

In-memory conformance: guarded publication must use actual supplied identity/source repositories, never caller-authored detached dictionaries. Reuse graph per-World lock plus existing source/identity family RLocks in consistent owner order (graph -> source -> identity), held across guarded validation and publication. Existing writers already use their family locks; preserve them. Missing authority repositories for a guarded command fail closed; legacy publication needs no new constructor dependency. Avoid a lock order inversion with existing adoption/reconciliation publishers.

## Closed candidate lease

- src/dungeonmind/contracts/contribution_review_v2.py — strict nested guard, required guarded intent/record variants, guarded digest/state decoding and legacy compatibility.
- src/dungeonmind/contracts/review_publication.py — guarded internal command variant; no receipt-field churn unless owning proof demonstrates necessity and PRIME rebriefs.
- src/dungeonmind/application/contribution_review_v2.py — persist guarded intent commitment in finalized record.
- src/dungeonmind/application/review_publication.py — derive guard from durable record, no caller override, exact replay semantics.
- src/dungeonmind/application/repositories.py — only accurate guarded type aliases/signatures if needed.
- src/dungeonmind/infrastructure/postgres/records.py — guarded review decode and existing identity/source writer fence participation.
- src/dungeonmind/infrastructure/postgres/review_publication.py — same-UoW verification before new publication and legacy/exact receipt behavior.
- src/dungeonmind/infrastructure/memory/repositories.py — equivalent owning repository/lock behavior and guarded decoding.
- tests/unit/test_contribution_review_v2.py — guard validation/digest and old byte/hash vectors.
- tests/unit/test_review_publication_transport_contract.py — guarded command/record round trip and downgrade rejection.
- tests/conformance/test_review_publication.py — memory parity, authority drift and receipt replay.
- tests/integration/test_postgres_review_publication_v6.py — real PG guard, writer participation, concurrency and fresh readback.
- Docs/Handoffs/HANDOFF-REPAIR-reviewed-identity-publication-preconditions.md — this pinned handoff carried in the same Core implementation PR, with truthful activation/handback.

No materializer, contribution payload model, initializer, vocabulary, Buddy, root config, dependency, transport route, migration or live-data path is leased. Any necessary additional path is a STOP/rebrief.

## Collision and activation

The existing RAKE existence-evidence rebind lease overlaps contracts/contribution_review_v2.py, application/review_publication.py, application/repositories.py, both publication repositories and tests/integration/test_postgres_review_publication_v6.py. Its preserved checkout is clean at frozen draft checkpoint 1dda0b5274d24292c7a3661de7b124e06dc7628b; that draft has no source acceptance. These are NOT disjoint lanes.

Before activation the same RAKE owner should finish the currently running rebind source tests and safely checkpoint its exact source commit, recording outcomes and preserved checkout. No freeze/transfer may interrupt or discard that work. ROOT then explicitly freezes the rebind implementation lease and transfers the overlapping paths to this prerequisite; re-fetch/re-anchor and activate RAKE serially in an isolated implementation checkout against this exact portable handoff hash. Carry the handoff at its canonical destination in the same Core implementation PR; do not create a separate handoff/process PR or require prior main landing. ARCH remains independent reviewer. After this prerequisite merges and state sync finishes, re-anchor/rebase/re-activate rebind against the accepted publication contract. Rebind reuses the resulting UoW rather than introducing a second competing source-proof transaction design. Buddy binding remains HOLD pending its separately designed exact Core consumer adoption and publication witness.

## Deterministic owning concurrency proof

Use a disposable PG fixture, no operator DSN. Finalize one guarded review, pause before publisher lock acquisition, append and COMMIT an active superseding decision through the real identity repository while graph head remains unchanged, then resume publication. It MUST reject with no child/head event/publication receipt. This exactly reproduces the current Buddy-check-to-Core-transaction race.

Then exercise the opposite ordering with events/barriers: guarded publisher holds lock_world and has completed guard validation, a separate real identity append attempts supersession and blocks until publication commits, publication creates exactly one child/receipt, and the writer then completes. Exact publication retry after supersession must return the identical historical receipt without another child. Also exercise real typed catalog drift before guard acquisition and source mutation contention during its transaction. No timing-only sleep proof substitutes for observed ownership/blocking and row/receipt assertions.

Guard tamper, source fingerprint/domain/World/revision mismatch, missing/inactive decision, target/evidence mismatch, commitment stripping, and fresh-service readback are owning negatives. Freeze representative entire legacy intent/record/command/receipt JSON+hashes and repeat the old unguarded publication/replay suite. New failure after validation still rolls back all publication effects. No inference/provider calls.

## Source landing versus execution

This prerequisite may land after its own exact-head source/conformance/PG review; it creates no actual binding decision or replay child. Buddy then needs a reviewed consumer adoption that constructs the guarded intent, pins exact accepted Core source and proves publication through that contract.

An independently enforced exclusive execution lease covering ALL graph, identity, catalog and administrative writers could remove the operational race for a single bounded replay window. A verbal one-replay-writer declaration is insufficient, and sealed snapshot alone does not fence live authorization. Such an exception would require separately verified writer exclusion from the final check through commit, and would not prove general concurrent safety. PRIME has chosen the Core fence prerequisite instead. No exclusive-execution shortcut is authorized here. Full-World/operator hard gate remains in force.


## Implementation handback

- Isolated lane: `codex/reviewed-identity-publication-fence`, based on freshly fetched `4bf8333bbc3fb3c848701d80f2d0f3e20ce0ef84`.
- Classes: `ReviewedIdentityPublicationPreconditionsV1`, `ReviewedIdentitySourcePreconditionV1`, `GuardedContributionReviewIntentV2`, `GuardedContributionReviewRecordV2`, `GuardedFinalizedReviewPublicationCommand`.
- The required field is `reviewed_identity_preconditions`. Legacy objects do not serialize that field. Guarded decode is explicit and preserves the subtype. Required parent/World/campaign match is checked in the intent/record; the writer additionally compares complete guard equality with the durable record.
- Preconditions use `decision_sha256`, `target_object_sha256`, `existence_evidence_sha256`, and sorted `sources` entries with `source_artifact_sha256`/`source_revision_sha256`. Hashes are complete canonical typed native payload hashes; existence evidence is in the original metadata order.
- The owning writer rejects selected-decision disappearance/inactivity/supersession, active conflicting overrides, target redirects/standing/scope/fingerprint changes, unproved evidence/source closure, source domain/World/campaign/ownership/fingerprint mismatches and command guard stripping/replacement.
- New guarded PG publication sets read committed before its first World-lock statement, ensuring authority reads after waiting for the fence get a fresh statement snapshot even when the connection defaults to repeatable read. Decision append and ordinary artifact/revision puts now acquire the existing World fence. Selected artifacts additionally stay row-share locked until commit.
- Guarded memory publication holds graph -> source -> identity family locks. Unguarded publication takes no new family lock; this preserves unrelated-World concurrency. Historical receipt reconstruction retains the guarded command subtype and does not recheck current authority eligibility.
- Existing outer V2 review/state and V1 internal-command/receipt schema names are retained. Actual PostgreSQL finalized record JSON round trips preserve the nested guard and receipt intent-hash correspondence; no schema migration is needed.

Required evidence: pure contract/transport/conformance suite; whole legacy canonical intent/record/command/receipt hash vectors; real PG publication/CAS/replay suite; event/barrier drift before lock and actual `pg_blocking_pids` evidence for writer contention; ordinary artifact/revision writer participation; fresh-service guarded-record/receipt readback; post-validation failure rollback. Private evidence packet is `/tmp/rake-identity-publication-fence-fixture/` and contains only synthetic fixture data. The actual World, replay consumer pin and frozen corpus inputs have not changed.

No separate process PR, new locking framework, callback guard, registry, materializer change or rebind effect is included. ARCH remains independent reviewer. Buddy's later consumer adoption and exact accepted Core pin are separate required work; this source landing does not activate a binding decision or replay.
