# HANDOFF — V5.4 prospective-reference identity allocation + substitution

**Provenance:** MIND  
**Status:** ACTIVE — PR #75 Review Cycle 1 repair; implementation not accepted
**Repository:** `Drakosfire/DungeonMind`  
**Roadmap phase:** `V5.4`  
**Suggested branch:** `kernel/v5-4-prospective-reference-allocation-substitution`  
**Suggested PR title:** `KERNEL: V5.4 prospective-reference identity allocation and substitution`  
**Implementation base:** `a811afffa43dc4b5875003f6ab7023d66554e128` — merged PR #74  
**Predecessor:** V5.3 — durable publication replay and recovery  
**Accepted V5.3 head:** `be1d4e3760965f2c95d7c8d776bf0cf49441be84`  
**V5.3 review cycles:** `4`  
**V5.3 final PASS review:** `5293886209`  
**V5.3 disposition:** `V5_3_DURABLE_PUBLICATION_REPLAY_RECOVERY_ACCEPTED`  
**V5.3 merge:** `a811afffa43dc4b5875003f6ab7023d66554e128`  
**Current Alembic head:** `0009_vnext_publication_receipts`  
**Frozen V0 aggregate:** `fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea`

## 1. Mission

WorldKeeper must be able to prepare one governed change in which a new entity does not yet have a durable DungeonMind ID, dependent assertions refer to that create result transaction-locally, and DungeonMind allocates the durable identities, substitutes them consistently, validates the complete child, publishes it atomically through the accepted V5.3 publication path, and returns the exact client-operation → durable-ID mapping.

The smallest acceptance witness is:

```text
existing durable entity B
+
prospective create P
+
prospective assertion A whose subject is result_of(P)
  and whose entity-ref target is durable(B)
+
stable publication_id
+
exact expected parent

→ one committed child revision
→ one V5.3 publication receipt
→ P -> one DungeonMind-allocated entity ID
→ A -> one DungeonMind-allocated assertion ID
→ assertion A contains the exact allocated entity ID for P
→ retry by the same publication_id returns the exact same receipt and mapping
```

This is the last known DungeonMind owning-boundary blocker for WorldKeeper WK-3 runtime work.

## 2. Primary question

> Can DungeonMind accept one governed transaction containing create-new results referenced by dependent assertions before durable IDs exist, allocate those IDs under DungeonMind authority, substitute them into one canonical governed contribution, validate the complete resulting child, publish it through the V5.3 recoverable atomic publication path, and durably return the prospective/client-operation → durable-ID mapping without letting the caller predict, reserve, or reconcile durable identity?

A PASS answers only that question.

## 3. Required guarantees

V5.4 must prove all of these simultaneously:

1. DungeonMind allocates durable entity and assertion identity for prospective creates.
2. A caller-supplied `client_op_id` is a transaction-local handle, never a durable graph ID.
3. Every `result_of(client_op_id)` referring to one prospective entity resolves to exactly one allocated entity ID.
4. Substitution completes before canonical child validation and before head advancement.
5. Entity creation and all accepted dependent assertions publish in one revision or none publish.
6. Create-new remains create-new. No similarity search, alias lookup, identity merge, or existing-object substitution may satisfy a prospective create.
7. Missing references, duplicate handles, wrong result kinds, references to rejected creates, ID collisions, malformed assertions, and stale parents fail closed with no partial authority.
8. V5.4 uses the accepted V5.3 `(space_id, publication_id)` replay/recovery authority.
9. The durable result includes the exact mapping required for a consumer to build `VerifiedCommittedChange` without its own identity ledger.
10. Exact replay returns the original mapping even after the head advances.
11. Lost-response recovery returns the durable mapping with the V5.3 terminal publication result.
12. The frozen V0 contracts remain unchanged.

## 4. Important design decision — allocation without a long database transaction

Do **not** move V5.1 governed materialization and domain validation inside the PostgreSQL publication transaction merely to make identity allocation happen physically under a database lock.

V5.4 should use a DungeonMind-owned deterministic allocator before command freeze:

```text
(space_id, publication_id, client_op_id, result_kind)
  → DungeonMind provisional durable ID
```

These IDs are Kernel-generated, not caller-generated. They are not reserved, published, or authoritative when computed. They become durable identity only if the V5.3 publication transaction commits the revision, receipt, and V5.4 result mapping together.

A caller must treat an allocated ID as nonexistent until the committed V5.4 result returns or is recovered.

This preserves the existing architecture:

```text
prospective governed intent
→ DungeonMind allocation + substitution
→ ordinary canonical KnowledgeContribution
→ existing V5.1 materialization / validation
→ existing V5.2 CAS authority
→ existing V5.3 receipt/replay/recovery
→ V5.4 result mapping committed atomically with V5.3 authority
```

The allocation algorithm is Kernel implementation authority, not a public reservation API. WorldKeeper must not reproduce it and treat predictions as committed IDs.

## 5. Identity allocation

Add a versioned internal allocator identity schema equivalent to:

```text
dm_prospective_result_identity_v1

material:
  schema
  space_id
  publication_id
  client_op_id
  result_kind   # entity | assertion
```

Recommended output forms:

```text
entity    -> ent:<first 32 hex of canonical SHA-256>
assertion -> asrt:<first 32 hex of canonical SHA-256>
```

Exact prefixes may follow repository convention, but must be type-distinct and pinned by test vectors.

The allocator must prove:

- same exact material → same ID;
- changed space → different ID;
- changed publication ID → different ID;
- changed client operation ID → different ID;
- changed result kind → different ID;
- entity and assertion allocations can never alias by type;
- an allocated create ID already present in the exact parent fails as a create-new collision rather than adopting the existing object.

Do not include the expected parent in allocation identity. A stale publication remains stale; a caller that wants to re-prepare against a new parent must use a new publication identity. Excluding the parent keeps exact same-publication recovery stable.

## 6. Additive prospective contracts

Do not modify the existing frozen V0 `Entity`, `Assertion`, `KnowledgeContribution`, `PublishKnowledgeRevisionCommand`, or `KnowledgePublicationReceipt` contracts.

Add a separate V5.4 contract module, preferably:

```text
src/dungeonmind/contracts/vnext/prospective.py
```

The existing V0 aggregate must remain byte/digest exact. V5.4 receives its own schema/digest tests.

### 6.1 Entity references

Conceptual contract:

```text
DurableEntityRef
  kind = durable_entity
  entity_id

ProspectiveEntityRef
  kind = result_of
  client_op_id

EntityOperand = DurableEntityRef | ProspectiveEntityRef
```

`result_of` is transaction-local syntax. It never survives into the graph payload.

### 6.2 Prospective entity create

Conceptual contract:

```text
ProspectiveCreateEntity
  kind = create_entity
  item_id
  client_op_id
```

The current generic `Entity` contains only `entity_id`; therefore the prospective create requires no caller-owned entity payload. Domain meaning such as name, classification, role, or location is expressed through assertions that may refer to this result.

### 6.3 Prospective assertion create

Conceptual contract:

```text
ProspectiveCreateAssertion
  kind = create_assertion
  item_id
  client_op_id
  subject: EntityOperand
  predicate
  value:
    prospective entity ref value
    | existing LiteralValue
    | existing TermRefValue
  metadata: existing AssertionMetadata
```

For an entity-ref assertion value, the target may be either:

```text
durable(existing_entity_id)
result_of(prospective_entity_client_op_id)
```

The assertion ID itself is allocated by DungeonMind from this item's `client_op_id`.

### 6.4 Prospective contribution envelope

Prefer an additive `ProspectiveKnowledgeContribution` that mirrors the governance envelope of `KnowledgeContribution` while allowing a mixed item union:

```text
existing V1 ContributionItem
|
ProspectiveCreateEntity
|
ProspectiveCreateAssertion
```

This allows V5.4 to add the missing create-result primitive without replacing retract, supersede, identity-decision, or existing durable-ID proposal semantics.

Existing `ContributionDisposition` remains the governance disposition keyed by `item_id`.

Do not make `client_op_id` double as `item_id`; they serve different authority purposes.

## 7. Handle and dependency rules

Before materialization, V5.4 must fail closed unless:

- every prospective result-producing item has one nonblank `client_op_id`;
- `client_op_id` is globally unique across entity and assertion creates in the transaction;
- `item_id` remains unique across the entire contribution;
- every `result_of(x)` resolves to a prospective **entity** create with client op `x`;
- an accepted item never depends on a rejected or unresolved prospective create;
- a prospective assertion cannot use an assertion-producing handle as an entity endpoint;
- no prospective reference points outside the current transaction;
- all durable entity refs resolve in the exact parent or to canonical state otherwise valid under existing materialization rules.

Rejected prospective create items produce no durable graph identity and must not appear in the returned committed result mapping.

It is acceptable for the resolver to calculate deterministic provisional IDs for rejected items internally while building the canonical contribution, but they must not be represented as committed results.

## 8. Resolution to existing canonical contracts

V5.4 should not create a second graph materializer.

Introduce one pure resolver conceptually equivalent to:

```text
resolve_prospective_contribution(
    prospective_contribution,
    dispositions,
    publication_id,
    expected_parent,
) -> ResolvedProspectiveContribution
```

where the result contains:

```text
canonical_contribution: KnowledgeContribution
committed_result_bindings: tuple[ProspectiveResultBinding, ...]
request_sha256
```

Resolution does:

```text
1. validate handle uniqueness and dependency closure
2. allocate all required Kernel IDs
3. replace prospective create entity with ProposeEntity(Entity(allocated_id))
4. replace prospective create assertion with ProposeAssertion(
     Assertion(
       assertion_id = allocated assertion ID,
       subject_entity_id = resolved durable entity ID,
       entity-ref value = resolved durable entity ID when applicable,
       ...
     )
   )
5. preserve all existing canonical contribution items unchanged
6. preserve original item ordering and item_id values
7. build the committed mapping only for accepted prospective create items
```

Then call the accepted V5.1 `materialize_governed_revision(...)` unchanged.

The final native graph payload must contain no `client_op_id`, `result_of`, prospective reference object, or WorldKeeper vocabulary.

## 9. Request identity

V5.3 binds the resolved `PublishKnowledgeRevisionCommand`, including `created_at`, to `(space_id, publication_id)`.

V5.4 additionally needs to bind the caller's prospective intent so recovery can return the exact mapping and changed prospective handles cannot masquerade as the same operation.

Compute:

```text
prospective_request_sha256 = canonical_sha256({
  schema: dm_prospective_publication_request_identity_v1,
  publication_id,
  prospective_contribution,
  dispositions,
  publication_identity: {
    operation_ids,
    created_at,
    expected_parent_revision_id,
  }
})
```

Exact field packaging is implementation latitude, but the identity must bind every input capable of changing the resolved canonical contribution or result mapping.

V5.4 does **not** alter V5.3's timestamp-sensitive command identity. A resubmission under the same `publication_id` must preserve the original prepared request, including its `created_at`. Recovery by publication ID does not require the caller to regenerate the request.

## 10. Durable result mapping

Do not mutate `KnowledgePublicationReceipt v1`.

Add a separate versioned durable result contract equivalent to:

```text
KnowledgeProspectivePublicationResult
  schema_version = dm_knowledge_prospective_publication_result_v1
  space_id
  publication_id
  prospective_request_sha256
  published_revision_id
  results[]
  status = published

ProspectiveResultBinding
  client_op_id
  result_kind = entity | assertion
  durable_id
```

Bindings must be unique by `client_op_id` and deterministically ordered.

The returned application result may expose:

```text
publication_receipt: KnowledgePublicationReceipt
prospective_result: KnowledgeProspectivePublicationResult
```

or an equivalent immutable aggregate.

WorldKeeper must be able to obtain, at minimum:

```text
publication_id
published_revision_id
client_op_id -> durable ID mapping
```

without reading the graph and without maintaining its own durable identity ledger.

## 11. Persistence

Add a new table after migration `0009`, preferably:

```text
knowledge_prospective_publication_results
```

Recommended fields:

```text
space_id
publication_id
schema_version
prospective_request_sha256
published_revision_id
result_bindings jsonb
record_fingerprint
status = published

PRIMARY KEY (space_id, publication_id)
FOREIGN KEY (space_id, publication_id)
  -> knowledge_publication_receipts(space_id, publication_id)
FOREIGN KEY (space_id, published_revision_id)
  -> knowledge_revisions(space_id, revision_id)
```

If PostgreSQL requires a compatible unique constraint on the referenced receipt columns, add it explicitly rather than weakening the logical key.

This table is a durable result/correspondence record. It is not a second graph authority and not an identity-resolution ledger.

## 12. Atomic publication boundary

A prospective fresh publication must commit all of the following in one repository transaction / one in-memory lock:

```text
KnowledgeRevision
KnowledgeHead transition
KnowledgeHeadEvent(kind=publish)
KnowledgePublicationReceipt              # V5.3
KnowledgeProspectivePublicationResult     # V5.4
```

There must be no application sequence equivalent to:

```text
publish revision
then write mapping
```

or:

```text
reserve entity IDs durably
then later publish graph
```

Both are rejected.

Implementation should share the accepted V5.3 publication transaction internals rather than copy the CAS algorithm into an unrelated repository.

A clean shape is:

```text
repository.publish_prospective_publication(
    command,
    publication_id,
    prospective_request_sha256,
    result_bindings,
) -> ProspectivePublicationAggregate
```

Exact naming is flexible.

## 13. Replay and identity-claim rules

### Exact prospective replay

If both V5.3 receipt and V5.4 prospective result exist:

```text
verify receipt
verify result fingerprint
verify prospective_request_sha256
verify published revision
verify every returned binding
return original result
no head mutation
no event
no new revision
```

### Changed prospective retry

Same `(space_id, publication_id)` with a different prospective request digest:

```text
KnowledgePublicationIdempotencyConflictError
zero mutation
```

A specialized subtype is optional; do not invent a broad new retry taxonomy.

### Publication ID already used by non-prospective V5.3 publication

Receipt exists, prospective result does not:

```text
idempotency conflict
```

The identity is already claimed and cannot be retrofitted into a prospective mapping.

### Prospective result exists without receipt

This is persistence corruption:

```text
PersistenceIntegrityError
```

### Existing graph revision without receipt/result

Do not infer prospective success from graph bytes or allocated IDs. V5.3 receipt authority remains required.

## 14. Create-new semantics

A prospective entity create is an instruction to mint a new durable graph identity.

DungeonMind must not satisfy it by:

- exact-name lookup;
- semantic similarity;
- alias lookup;
- identity candidate selection;
- merge/reconciliation;
- returning an existing entity whose data appears equivalent.

If the Kernel allocator produces an ID already present in the parent, fail closed with an identity-allocation collision. Do not adopt it.

Identity reconciliation remains a separate governed operation.

## 15. Validation order

Required logical order:

```text
prospective request structural validation
→ disposition completeness / accepted-dependency closure
→ Kernel identity allocation
→ prospective reference substitution
→ canonical KnowledgeContribution construction
→ existing V5.1 governed materialization
→ child structural + domain/profile validation
→ exact command freeze
→ V5.3/V5.4 atomic repository transaction
→ head advancement at commit
```

No invalid prospective reference may survive to durable graph payload.

No head mutation may occur before the complete substituted child has passed existing materialization validation.

## 16. Lost-response recovery

V5.4 must inherit V5.3's failure classification, not create a second recovery model.

After an ambiguous repository exception, perform one exact prospective-result recovery read by `(space_id, publication_id)`.

Recovery succeeds only if the repository can verify:

```text
prospective result record
↔ V5.3 receipt
↔ exact published revision
↔ graph payload digest
↔ deterministic result bindings
```

Valid result → success.

Deterministic zero-commit failures preserve their typed error, including at least the accepted V5.3 set:

```text
KnowledgePublicationIdempotencyConflictError
KnowledgeStaleParentRevisionError
ImmutableRevisionConflictError
PersistenceIntegrityError
```

Unavailable / ambiguous attempt or probe with no verified result → existing `KnowledgePublicationOutcomeUnknownError` with the same retry-safe `(space_id, publication_id)` identity.

Do not infer success from the head, revision existence, or an allocated ID appearing in graph history.

## 17. PostgreSQL and in-memory parity

Both adapters must prove the same semantics:

- deterministic allocation;
- create-new collision failure;
- exact substitution;
- atomic mapping + receipt + revision + head + event;
- exact replay;
- changed-request conflict;
- response-loss recovery;
- corruption fail-closed behavior.

PostgreSQL remains the concurrency/transaction authority proof.

## 18. Required acceptance matrix

The owning tests must include at least:

### Allocation

1. entity allocation is deterministic for the exact identity material;
2. assertion allocation is deterministic;
3. changed publication/client-op/kind changes ID;
4. entity/assertion namespaces cannot alias;
5. allocated ID collision with an existing parent object fails create-new.

### Resolution

6. one prospective entity + one dependent assertion resolves to one canonical entity and assertion;
7. two references to the same prospective entity resolve to the same exact durable ID;
8. prospective entity used as an entity-ref value resolves correctly;
9. durable existing entity references remain unchanged;
10. duplicate `client_op_id` fails;
11. unknown `result_of` fails;
12. assertion-handle used as entity endpoint fails;
13. accepted assertion referencing rejected prospective entity fails;
14. no prospective syntax appears in the final graph payload.

### Governance / validation

15. rejected prospective items create no durable graph object and no committed mapping;
16. existing disposition completeness rules remain intact;
17. domain/profile validation runs on the fully substituted canonical assertion;
18. malformed final child causes zero publication mutation.

### V5.3 integration

19. fresh prospective publication produces one revision/head/event/receipt/result mapping;
20. exact same `publication_id` + exact same prospective request returns the original mapping with no new event;
21. replay after a descendant advances the head returns the original mapping and does not rewind the head;
22. same publication ID + changed prospective request conflicts;
23. publication ID already claimed by plain V5.3 publication conflicts;
24. post-commit response loss recovers the exact mapping;
25. ambiguous recovery failure returns retry-safe outcome-unknown;
26. persistence corruption in receipt/result/revision remains integrity failure.

### Concurrency / atomicity — PostgreSQL required

27. same publication ID + same prospective request concurrently converges on one receipt/result mapping;
28. same publication ID + different prospective requests concurrently yields one winner and one idempotency conflict;
29. different publication IDs on the same expected parent preserve one winner / one stale CAS result;
30. injected failure after prospective result insertion rolls back result + receipt + revision + head + event;
31. no durable mapping exists without its exact V5.3 receipt.

### Compatibility

32. V5.1 ordinary materialization remains unchanged;
33. V5.2 raw repository CAS remains unchanged;
34. V5.3 ordinary publication/replay remains unchanged;
35. frozen V0 aggregate remains exact;
36. legacy World publication paths remain unchanged;
37. no WorldKeeper/TTRPG vocabulary enters generic Kernel runtime.

## 19. Canonical WorldKeeper unblock witness

Use generic lab vocabulary in Kernel tests, but prove this exact structural shape:

```text
parent revision rev:X contains:
  durable entity ent:castle

prospective contribution:
  item create-1:
    client_op_id = npc-7
    create entity

  item assert-1:
    client_op_id = rel-4
    create assertion
    subject = result_of(npc-7)
    predicate = lab:located_at
    value = durable_entity(ent:castle)

both dispositions = accepted
publication_id = prepared:worldkeeper-witness
expected_parent = rev:X
```

Required result:

```text
receipt.published_revision_id = rev:Y

result bindings:
  npc-7 -> ent:<allocated>
  rel-4 -> asrt:<allocated>

rev:Y graph:
  contains ent:<allocated>
  contains asrt:<allocated>
  assertion.subject_entity_id == ent:<allocated>
  assertion.value.entity_id == ent:castle
```

Retry the exact operation and require byte/field-equivalent mapping and receipt identity with no second event.

This witness is the acceptance gate for declaring WorldKeeper WK-3 unblocked.

## 20. Files in scope

Expected surface:

```text
Docs/Decisions/ADR-0026-vnext-prospective-reference-allocation-substitution.md
Docs/Handoffs/HANDOFF-v5-4-prospective-reference-allocation-substitution.md
Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md
Docs/Handoffs/HANDOFF-v5-3-durable-publication-replay-recovery.md
Docs/Roadmaps/ROADMAP.md

src/dungeonmind/contracts/vnext/prospective.py
src/dungeonmind/contracts/vnext/__init__.py

src/dungeonmind/application/vnext/prospective.py
src/dungeonmind/application/vnext/ports.py
src/dungeonmind/application/vnext/errors.py
src/dungeonmind/application/vnext/__init__.py

src/dungeonmind/infrastructure/memory/vnext_knowledge.py
src/dungeonmind/infrastructure/postgres/vnext_knowledge.py

migrations/versions/0010_vnext_prospective_publication_results.py

tests/unit/test_vnext_prospective_publication.py
tests/integration/test_postgres_vnext_prospective_publication.py
tests/integration/test_migrations.py
```

`src/dungeonmind/application/vnext/publication.py` may be modified only if needed to extract/reuse the accepted V5.3 recovery/error-classification helper. Do not alter V5.3 observable semantics.

Focused existing tests may receive bookkeeping assertions for V5.3 COMPLETE / V5.4 ACTIVE. Record any expansion beyond this surface in the checked-in handoff before requesting review.

## 21. Explicitly out of scope

Do not include:

- public HTTP/service transport;
- WorldKeeper runtime code;
- DungeonBuddy adapter code;
- bridge-genesis migration;
- legacy World writer cutover;
- source/evidence prospective creation;
- prospective identity decisions;
- result-of references to assertion results as entity endpoints;
- arbitrary DAG/job language;
- durable ID reservations before publication;
- similarity-based dedupe or entity reconciliation;
- pending/running/retry worker lifecycle;
- V5.3 receipt schema mutation;
- V0 Entity/Assertion/KnowledgeContribution contract mutation;
- storage/performance redesign.

## 22. ADR-0026 decisions to record

ADR-0026 should explicitly record:

1. prospective handles are transaction-local caller references, not durable IDs;
2. DungeonMind owns deterministic allocation of entity/assertion IDs;
3. allocated IDs are provisional until atomic publication commits;
4. allocation is domain-separated by space/publication/client-op/result-kind;
5. `result_of` resolves only prospective entity creates in V5.4;
6. create-new never invokes identity reconciliation or substitutes an existing object;
7. prospective contracts are additive and do not mutate frozen V0 contracts;
8. resolver produces an ordinary canonical `KnowledgeContribution` and reuses V5.1 materialization;
9. V5.4 durable result mapping is separate from the accepted V5.3 receipt schema;
10. result mapping commits atomically with V5.3 receipt/revision/head/event;
11. V5.3 remains the only replay/recovery authority;
12. WorldKeeper WK-3 is unblocked only after the canonical prospective-create witness is accepted.

## 23. Stewardship bookkeeping in the first commit

PR #74 was accepted before merge, but current `main` still contains pre-acceptance V5.3 status text.

The first V5.4 commit must reconcile authority before runtime work:

```text
V5.3 COMPLETE
V5_3_DURABLE_PUBLICATION_REPLAY_RECOVERY_ACCEPTED
accepted head: be1d4e3760965f2c95d7c8d776bf0cf49441be84
review cycles: 4
final PASS review: 5293886209
merge: a811afffa43dc4b5875003f6ab7023d66554e128

V5.4 ACTIVE
IMPLEMENTATION NOT YET ACCEPTED
```

Update:

- V5.3 handoff status to COMPLETE and append final acceptance/merge record;
- Steward current-main anchor and last merged roadmap implementation to PR #74;
- Steward current primary question to V5.4;
- roadmap V5.3 COMPLETE / V5.4 ACTIVE.

Do not claim V5.4 acceptance in implementation commits.

## 24. Suggested commit sequence

```text
1. STEWARDSHIP: accept V5.3 and activate V5.4
2. CONTRACT: add prospective reference and publication-result contracts
3. KERNEL: allocate and resolve prospective identities into canonical contributions
4. KERNEL: atomically persist prospective result mappings with V5.3 publication
5. KERNEL: prove PostgreSQL prospective replay concurrency and rollback
6. DOCS: record V5.4 characterization/handback if required
```

Keep commits capability/proof sized. Do not collapse the whole implementation into one opaque commit.

## 25. Verification

Required before review:

```text
uv run ruff check .
uv run pyright
uv run pytest -m "not integration"
uv run pytest -q tests/unit/test_vnext_prospective_publication.py
uv run pytest -q tests/unit/test_vnext_publication_recovery.py
uv run pytest -q tests/unit/test_vnext_cas_publication.py

DUNGEONMIND_DATABASE_URL=<test db> \
  uv run pytest -q tests/integration/test_postgres_vnext_prospective_publication.py -o addopts=''

DUNGEONMIND_DATABASE_URL=<test db> \
  uv run pytest -q tests/integration/test_postgres_vnext_knowledge_publication.py -o addopts=''

DUNGEONMIND_DATABASE_URL=<test db> \
  uv run pytest -q tests/integration/test_migrations.py -o addopts=''
```

Also run repository CI and classify the inherited legacy `world_graph_reads.py` benchmark-smoke failure exactly if it remains present. Do not call the whole repository green while that job is red.

No new latency threshold is required for V5.4. If allocation/resolution timing is measured, record it as characterization rather than weakening validation.

## 26. Stop / rebrief conditions

Stop rather than compensating locally if:

- the only implementation requires caller-generated durable entity or assertion IDs;
- prospective refs cannot be resolved before V5.1 materialization without changing `Entity` or `Assertion` V0 contracts;
- V5.4 requires moving full graph materialization into the database transaction;
- result mapping cannot commit atomically with the V5.3 receipt;
- exact replay cannot recover the mapping without scanning graph history;
- create-new semantics require identity reconciliation or similarity matching;
- V5.3 receipt semantics must be weakened or rewritten;
- a durable pre-publication reservation table becomes necessary;
- WorldKeeper-specific vocabulary is required in generic contracts/runtime;
- source/evidence prospective creation becomes necessary for the minimum unblock witness;
- the canonical WorldKeeper witness cannot be represented without a broader prospective transaction language.

When a stop condition fires, record the failed assumption and rebrief before adding scope.

## 27. Acceptance token

Only Steward review may record:

```text
V5_4_PROSPECTIVE_REFERENCE_PUBLICATION_ACCEPTED
```

That token means the DungeonMind boundary has proven the minimum create-result/dependent-reference atomic publication primitive and WorldKeeper WK-3 may begin implementation against it.

It does **not** mean DungeonBuddy/WorldKeeper integration has landed, transport exists, bridge migration is complete, or legacy writers may be removed.

## 28. Current implementation handback

```text
branch: kernel/v5-4-prospective-reference-allocation-substitution
base: a811afffa43dc4b5875003f6ab7023d66554e128
status: ACTIVE — IMPLEMENTATION NOT YET ACCEPTED
migration filename: 0010_vnext_prospective_publication_results.py
migration revision: 0010_vnext_prospective_results
```

The shorter migration revision identifier is required by Alembic's existing
32-character `alembic_version.version_num` column; the descriptive migration
filename remains unchanged.

### Recorded changed-path expansion

`tests/unit/test_vnext_cas_publication.py` is modified in addition to the §20
surface. This focused predecessor test contained a pre-acceptance assertion
that V5.3 must not be accepted and an entire-directory source hash that made an
additive V5.4 contract module appear to mutate the frozen V0 bundle. The repair
updates the status assertion to prohibit premature V5.4 acceptance and retains
the exact frozen aggregate-digest check as the compatibility authority.

`tests/unit/test_vnext_search.py` is also modified because its shared
stewardship-bookkeeping proof still required `V5.3 ACTIVE`. It now requires
V5.3 COMPLETE with the accepted disposition and V5.4 ACTIVE.

No other path expansion is authorized by this record. V5.4 acceptance remains
reserved for Steward review.

## 29. Review Cycle 1 repair handback

```text
PR: #75
review: 5295516481
reviewed head: 6b2d85e9ad710dbd89bd4cd2573d3ad231182ab8
verdict: HOLD
status: REPAIR IMPLEMENTED — AWAITING EXACT-HEAD RE-REVIEW
```

The repair remains entirely inside V5.4:

- ordinary V1 items are rejected if they contain a durable ID allocated for a
  prospective create in the same contribution;
- committed result bindings are checked against the fully materialized graph
  before the publication transaction begins, so a false durable mapping cannot
  advance the head;
- a V5.3 receipt without a V5.4 result is a deterministic
  `KnowledgePublicationIdempotencyConflictError` in memory, PostgreSQL, direct
  reads, and ambiguous-response recovery;
- deterministic recovery-probe failures retain their original typed failure;
- the deterministic allocator remains an internal V5.4 implementation detail
  and is no longer exported from `dungeonmind.application.vnext`.

Focused unit coverage proves retract and supersede attacks cause zero
publication mutation and that ambiguous recovery cannot turn an already
claimed publication identity into `outcome_unknown`. PostgreSQL coverage proves
the receipt-without-result state is the same deterministic conflict at the
durable boundary.

No WorldKeeper runtime, V5.5 work, frozen V0 contract change, or allocation
reservation/prediction API is included. Only Steward review may record V5.4
acceptance.

## 30. Review Cycle 2 repair handback

```text
PR: #75
review: 5295874723
reviewed head: ab7aeeeb0b13589ca32accad4f6221ba429c1542
verdict: HOLD — one repository-boundary blocker
status: REPAIR IMPLEMENTED — AWAITING EXACT-HEAD RE-REVIEW
```

The in-memory and PostgreSQL repository authorities now independently validate
every supplied result binding before entering the publication lock/transaction:

- recompute the deterministic V5.4 allocation from
  `(space_id, publication_id, client_op_id, result_kind)`;
- require the supplied durable ID to equal that allocation;
- require that exact ID to exist in the command graph under the correct entity
  or assertion kind;
- construct and validate the complete prospective result record before any
  revision, head, event, receipt, or result mutation;
- require an exact result-record match on replay.

Direct in-memory and PostgreSQL port tests forge `npc-7 -> ent:alice`, where
`ent:alice` is pre-existing rather than the deterministic allocation. Both fail
closed before mutation. The PostgreSQL proof retains exactly one genesis
revision/event and zero receipts/results.

This repair does not change contracts, allocation identity, WorldKeeper, or any
post-V5.4 capability. Only Steward review may record V5.4 acceptance.

## 31. Review Cycle 3 repair handback

```text
PR: #75
review: 5296218674
reviewed head: 0f6b78f165079cc97a77876232bcbca34031ae8f
verdict: HOLD — one create-new collision blocker
status: REPAIR IMPLEMENTED — AWAITING EXACT-HEAD RE-REVIEW
```

Repository authority now completes the create-new invariant before publication:
every validated deterministic binding must be absent from the exact immutable
expected-parent graph and present in the child graph under the correct kind.
The in-memory adapter performs this check under its publication lock. The
PostgreSQL adapter reads the exact parent and performs the check in the same
publication transaction before CAS, revision insertion, head advancement,
event creation, receipt insertion, or result insertion.

Direct in-memory and PostgreSQL tests construct a parent that already contains
the correct deterministic allocation and a child that still contains that ID.
Both repositories reject the binding as `identity_allocation_collision`; the
child revision remains absent and PostgreSQL remains at one parent
revision/event with zero receipts/results.

This repair remains entirely within V5.4 repository authority and proof. Only
Steward review may record V5.4 acceptance.
