# HANDOFF — complete selected-object one-hop read

**Created:** 2026-09-08
**Status:** ACTIVE — Cycle 2 HOLD assertion-completeness repair on this branch; awaiting Cycle 3
**Repository / branch:** `Drakosfire/DungeonMind` / `retrieval/complete-selected-object-one-hop-v1`
**Base:** `e82e790e011773369f07b1b431482d5026d4dd3e`
**Predecessor:** DungeonMindBuddy PR #697 stop condition on full World-object projection
**One-line mission:** Add one DungeonMind-native selected-object read that returns the complete admitted one-hop object view at one exact World revision, with explicit completeness and no product result caps silently truncating object truth.

---

## §1 Outcome

A client can ask DungeonMind for one exact object ID under one ordinary `WorldGraphProjectionRequestV2` scope/admissibility/revision context and receive one authoritative object-centric result containing every admitted incoming/outgoing one-hop relationship touching that object, every related endpoint needed to interpret those relationships, every admitted selected-object property/assertion needed by the current retrieval contract, all supporting evidence/source-anchor metadata available through the existing authority, and the temporal assertion metadata already carried by authoritative graph views.

The operation is **complete by contract** when it reports `complete`; ordinary `RetrievalBounds` caps such as 12 objects / 24 relationships / 32 assertions / 32 anchors may not silently define the selected object's truth.

This is an independently useful DungeonMind read capability. DungeonMindBuddy PR #697 remains blocked until it exists and is accepted.

---

## §2 Authority and anchors

Read these first:

1. `Docs/Architecture/ARCHITECTURE.md`
   - one World Graph per world;
   - reads are explicit: one world, revision, scope, admissibility;
   - retrieval may narrow but may not broaden/manufacture truth;
   - product adapters may not reconstruct a foreign graph;
   - product clients are replaceable.
2. `src/dungeonmind/application/world_graph_retrieval.py`
   - current `RetrievalBounds` hard ceilings;
   - `WorldGraphRetrievalService.get_object`;
   - `get_neighborhood`;
   - evidence/source-anchor revalidation;
   - read observability.
3. `src/dungeonmind/application/world_graph_read_context.py`
   - coherent read context; do not open a second authority path.
4. `src/dungeonmind/application/world_graph_projection.py`
   - projection/admission authority; do not duplicate scope/admissibility logic.
5. `tests/unit/test_world_graph_retrieval_service.py`
6. `tests/unit/test_world_graph_read_observability.py`
7. Buddy dependency, for acceptance semantics only:
   - `Drakosfire/DungeonMindBuddy` PR #697
   - canonical Buddy handoff: `Docs/Plans/HANDOFF-DOGFOOD-CONTINUITY-surface-neutral-full-world-object-projection-v2.md`

Observed stop condition from Buddy:

```text
Object-centric DungeonMind reads exist, but product-facing retrieval bounds cap:
  objects        <= 12
  relationships  <= 24
  assertions     <= 32
  anchors        <= 32

coverage.truncated_fields is honest, so this is a partial read.
Buddy needs a selected-object operation that can truthfully say complete.
```

---

## §3 Scope

### In scope

- One new or explicitly specialized **complete selected-object** application operation.
- Exact stable object-ID lookup; no search fallback.
- One exact `WorldGraphProjectionRequestV2` context:
  - world;
  - revision/head pin behavior;
  - scope mode, including cross-campaign/world mode;
  - admissibility;
  - focus metadata as already defined by projection.
- Every admitted relationship touching the selected object, incoming and outgoing.
- Every related endpoint object required by those relationships.
- Selected-object admitted property/assertion rows required by current retrieval semantics.
- Supporting source anchors/evidence metadata for returned facts using existing provenance validation.
- Preserve authoritative assertion metadata, including temporal semantics already present in graph/assertion views; do not reduce fictional state.
- Explicit result completeness:
  - `complete` when all required admitted selected-object material was returned;
  - `partial` only for a named, honest authority/integrity/resource reason.
- Existing bounded `get_object`, search, and neighborhood APIs remain valid for callers that intentionally want bounded retrieval.
- Read observability for counts, duration, and completeness/partial reason.
- Unit/integration evidence including a fixture whose degree exceeds the old 24-relationship hard cap.

### Out of scope

- Changing graph write/publication semantics.
- Graph mutation or head advancement.
- New current-fictional-state reducer.
- Timeline ordering or temporal inference.
- Search ranking changes.
- Generic neighborhood depth > 2.
- Making all existing `RetrievalBounds` unlimited.
- Returning the entire World graph to Buddy as the selected-object result.
- Pagination/fragment unioning in Buddy.
- Client-specific presentation fields.
- APP-STATE/source-body reads; DungeonMind returns authoritative source/evidence identity only.
- Agent policy or prompt behavior.

---

## §4 Invariants that bind this slice

1. **One World Graph per world.** Campaign remains assertion/scope metadata, never another graph.
2. **One coherent read.** The operation must derive from exactly one `WorldGraphReadContext` / authoritative projection context. No second lookup path may broaden or disagree with it.
3. **Retrieval never becomes authority.** The operation returns already-admitted facts only.
4. **PLAYER fails closed.** Material excluded by scope/admissibility/provenance is not recovered merely because it touches the selected object.
5. **Exact object identity.** Missing selected object is an explicit miss, not lexical fallback.
6. **Complete means complete.** Product/default bounded retrieval caps may not truncate a result labeled complete.
7. **Partial means explicit.** If a hard safety/resource/integrity ceiling exists, the result must name `partial` and the reason/counts; never silently drop edges/endpoints/assertions/evidence.
8. **Direction survives.** Incoming and outgoing relationships retain subject/object/predicate semantics.
9. **Temporal semantics survive.** Assertion metadata exposed by authority—including source/occurrence/valid-time semantics or unresolved temporal qualification—must not be flattened into session IDs or discarded.
10. **Source identity remains exact.** Existing evidence/anchor validation and source revision identity are reused; this slice does not guess source revisions.
11. **No client reconstruction.** The result itself is sufficient for a client to render the selected one-hop object without querying search/neighborhood fragments to recover omitted truth.
12. **No whole-World transport workaround.** A client must not need `project_world_graph` and local slicing to obtain the selected object.

---

## §5 Contract direction

Prefer a dedicated result/operation rather than weakening the semantics of all bounded retrieval.

Illustrative naming only:

```python
@dataclass(frozen=True)
class SelectedObjectCompleteness:
    status: Literal["complete", "partial"]
    reason: str | None = None
    truncated_fields: tuple[str, ...] = ()

@dataclass(frozen=True)
class CompleteObjectLookupResult:
    snapshot: ProjectionSnapshotV2
    found: bool
    object: GraphObjectView | None
    related_objects: tuple[GraphObjectView, ...]
    relationships: tuple[GraphRelationshipView, ...]
    property_assertions: tuple[AdmittedAssertionValue, ...]
    anchors: tuple[SourceAnchorMetadata, ...]
    completeness: SelectedObjectCompleteness
```

Possible service shape:

```python
WorldGraphRetrievalService.get_complete_object(
    request,
    *,
    object_id: str,
) -> CompleteObjectLookupResult
```

Exact names are implementation latitude. Semantics are not.

### Important distinction from `RetrievalBounds`

`RetrievalBounds` remains appropriate for:

- lexical search;
- generic bounded neighborhoods;
- deliberately bounded product retrieval.

It is not appropriate as the hidden definition of "all facts touching this selected object."

Do not solve this by simply raising `_RELATIONSHIPS_LIMIT` from 24 to an arbitrary larger number. That only moves the correctness cliff.

### Endpoint rule

For every returned relationship touching selected object `N`, the opposite endpoint object must be present in `related_objects` unless authority has an explicit integrity condition that makes the relationship itself partial/invalid. A relationship must not point at an omitted endpoint in a result called complete.

### Evidence/anchor rule

The complete selected-object result must include all evidence/source-anchor metadata the existing retrieval authority can validly derive for the returned selected-object facts. If provenance validation rejects a chain, preserve the current fail-closed coverage semantics rather than manufacturing an anchor.

If anchor material itself has a defensible independent safety ceiling, do not silently call the whole provenance result complete. Either:

- remove the product-result cap for this operation; or
- report explicit partial provenance/completeness with a reason that Buddy can fail closed on.

---

## §6 Performance and implementation boundary

The reason for this contract is not only payload shape. Buddy's requirement is "the whole object at need and fast."

The implementation may reuse the existing projection/read-context machinery; it must not create a second graph authority. However, do not normalize an implementation that requires the client to request the entire admitted World graph per click.

Record selected-object read timings and result counts at the DungeonMind owning boundary.

Required witnesses:

1. ordinary low-degree object;
2. object with >24 admitted touching relationships, proving the old cap is not the new completeness definition;
3. practically highest-degree object available in the Eldyrwild acceptance authority if live read evidence is available.

If the only viable implementation requires materializing/serializing the entire World result for each selected-object call and this causes materially poor selected-object latency, stop and report the lower-level read-index/query capability needed. Do not push a whole-World workaround into Buddy.

---

## §7 Work plan

1. **Characterize current cap failure.**
   - Add/extend a test fixture with one selected object and >24 admitted relationships.
   - Prove existing `get_object` reports `coverage.truncated_fields` and cannot satisfy completeness.

2. **Add the complete selected-object contract.**
   - Prefer `src/dungeonmind/application/world_graph_retrieval.py` unless bounded discovery proves a smaller neutral contract module is needed.
   - Reuse one `WorldGraphReadContext`.
   - Select exact object.
   - Collect all admitted touching relationships deterministically.
   - Collect all opposite endpoint objects.
   - Collect selected-object assertion/property rows.
   - Derive all valid evidence/source anchors under the same context.
   - Carry assertion metadata unchanged.

3. **Make completeness first-class.**
   - Normal success for a fully returned object: `complete`.
   - Exact miss remains miss, not partial.
   - Provenance/integrity/resource limitations: explicit `partial` with deterministic reason.
   - No inherited 12/24/32/32 product caps may create a `complete` response.

4. **Observability.**
   - Add/extend read observation operation name and fields for selected-object completeness.
   - Record object/relationship/assertion/anchor counts and timing.
   - Do not log source prose; DungeonMind does not own it.

5. **Public library seam.**
   - Export the new application capability through the existing public application boundary if `src/dungeonmind/application/__init__.py` is how retrieval types/services are exposed.
   - Do not create a Buddy-specific adapter inside DungeonMind.

6. **Live/fixture evidence.**
   - Demonstrate >24 relationship object returns complete with every endpoint.
   - Demonstrate cross-campaign/world-scope behavior under existing projection semantics.
   - Demonstrate GM/PLAYER fail-closed behavior remains unchanged.
   - Demonstrate temporal assertion metadata survives.

---

## §8 Expected write lease

Expected production paths:

- `Docs/Handoffs/HANDOFF-complete-selected-object-one-hop-read.md`
- `src/dungeonmind/application/world_graph_retrieval.py`
- `src/dungeonmind/application/world_graph_observability.py` only if a new operation/fields are required
- `src/dungeonmind/application/__init__.py` only if public export changes are required

Expected tests:

- `tests/unit/test_world_graph_retrieval_service.py`
- `tests/unit/test_world_graph_read_observability.py` if observability changes
- `tests/unit/test_retrieval_integrity.py` only if its owning expectations change

Bounded discovery: at most two additional production paths under `src/dungeonmind/application/` or `src/dungeonmind/contracts/` if the existing result types cannot truthfully express completeness.

A migration, durable schema change, graph write path, product-client import, or new repository storage model is a STOP/rebrief condition.

---

## §9 Acceptance gates

Focused tests must prove at minimum:

1. exact object miss is unchanged;
2. selected object with 0 relationships returns complete;
3. selected object with >24 relationships returns **all** admitted relationships and all opposite endpoints;
4. incoming and outgoing direction are both retained;
5. cross-campaign/world-scope admitted relationships survive when request scope admits them;
6. campaign scope still excludes material it should exclude;
7. PLAYER still fails closed;
8. every returned relationship endpoint exists in selected + related objects;
9. selected-object property/assertion rows are complete;
10. assertion metadata/temporal semantics survive unchanged;
11. evidence/source-anchor validation remains exact and fail-closed;
12. no arbitrary `RetrievalBounds.max_relationships` value controls completeness;
13. deterministic ordering/result equality for repeated exact reads;
14. observability reports actual counts and completeness status;
15. no durable writes/head changes occur.

Quality gates:

```bash
uv run pytest tests/unit/test_world_graph_retrieval_service.py
uv run pytest tests/unit/test_world_graph_read_observability.py   # if changed
uv run pytest tests/unit/test_retrieval_integrity.py              # if changed
uv run ruff check src tests
git diff --check
```

Run the repository's broader required unit/integration gate from `CONTRIBUTING.md` before merge if this public retrieval seam changes exports/contracts.

---

## §10 Buddy unblock witness

Before this DungeonMind PR is considered sufficient to unblock Buddy #697, provide an exact-head handback showing:

```text
DungeonMind repo/head
operation name
request world/revision/scope/admissibility
selected object ID
relationship count
related endpoint count
assertion count
anchor/evidence count
completeness = complete
truncated_fields = [] for required selected-object material
old 24-relationship cap exceeded by at least one fixture/witness
read duration / phase timings
World head before/after unchanged
```

Then Buddy #697 may resume CODE against the accepted DungeonMind contract. Buddy must not begin a workaround while this lane is open.

---

## §11 Stop conditions

Stop and report instead of improvising if:

- the authoritative read context cannot expose all admitted one-hop relationships without a new persistence/index contract;
- exact related endpoints cannot be obtained under the same coherent read;
- provenance/anchor derivation has an unavoidable independent cap that would make "complete object" misleading;
- temporal/assertion metadata would have to be reconstructed from raw source rather than retained from authority;
- the only implementation is to expose/transport the entire World projection to the client;
- PLAYER/scoping semantics would need weakening;
- a DB migration/new durable table appears necessary;
- a Buddy-specific dependency or import is proposed;
- graph write/publication semantics would change.

Required stop report:

```text
Stop condition:
Owning boundary:
Observed capability:
Missing lower-level contract:
Why selected-object retrieval cannot safely compensate:
Proposed successor:
Buddy #697 state:
```

---

## §12 Handback requirements

Return:

- repository / branch / base SHA / exact head SHA / PR / status;
- exact public operation/result names;
- cumulative changed-file list;
- review-cycle count and exact reviewed heads;
- focused + broad verification commands/results;
- >24-edge completeness witness;
- GM/PLAYER scope witness;
- cross-campaign/world-scope witness;
- temporal metadata preservation witness;
- observability/timing witness;
- confirmation World head/durable state unchanged;
- any remaining `partial` cases and their explicit reasons;
- what remains false;
- explicit statement that DungeonMindBuddy #697 may or may not resume CODE.

Named successor after acceptance: **DungeonMindBuddy #697 surface-neutral complete World-object projection implementation.**

---

## Addendum — Review Cycle 1 HOLD (`5149552871` on `082f53ac`)

The dispatch body above is unchanged. Cycle 1 required:

1. **Partial reason in telemetry.** `WorldGraphReadObservation.completeness_reason` is a closed vocabulary (`missing_related_endpoint` | `truncated_anchors`). Partial status requires a reason; complete/miss/other operations leave it unset. `truncated_fields` remains a separate field.
2. **>32 distinct anchors.** The high-degree fixture now admits 33 unique valid source anchors for the hub object. Bounded `get_object` still truncates at 32; `get_complete_object` returns all of them with `complete`.
3. **Empirical Eldyrwild timing.** Characterization runner: `benchmarks/complete_object_live_eldyrwild.py`. Record cold/warm wall and phase timings, parse-cache hits, admitted graph size, returned counts, completeness, and World head before/after. If warm selected-object latency is materially poor, do not call the full scoped-projection cost acceptable.
4. **PR body is the merge contract.** Update GitHub PR #52 after evidence is produced; do not leave “implementation has not started” in the description.

Partial graph states (`missing_related_endpoint`, `truncated_anchors`) remain modeled and observed. The current projection excludes relationships whose endpoints are not admitted, and this operation passes `max_anchors=None`, so those partial reasons are not expected on a well-formed admitted graph. They still must survive into telemetry when produced.

---

## Addendum — Review Cycle 2 HOLD (`5149678809` on `1df3a87a`)

Cycle 1 blockers are closed: partial-reason telemetry, the >32 distinct-anchor fixture, the live Eldyrwild timing witness, and PR/evidence synchronization.

Remaining defect: `get_complete_object()` used `_assertion_rows_for_object()`, which emits **property rows only**. Existence, alias, summary, and aspect metadata live on excluded `GraphObjectView` internals, so a result labeled `complete` could silently drop assertion-level evidence/temporal semantics. The live Bonogo witness `assertions=0` meant **0 property assertions**, not 0 admitted assertions about Bonogo.

---

## Addendum — Review Cycle 3 repair

`get_complete_object` now returns the full selected-object assertion ledger — existence, alias, summary, property, and aspect — with assertion ID, kind, payload fields, evidence refs, and assertion/temporal metadata. Anchors include those IDs in `supporting_assertion_ids` where applicable. Observability `result_assertion_count` counts the full ledger. Bounded `get_object` / search / neighborhood remain property-row retrieval.

Quality gates on this repair (not a full live re-characterization):

```text
uv run pytest tests/unit/test_world_graph_retrieval_service.py tests/unit/test_world_graph_read_observability.py
uv run pytest
uv run ruff check src tests benchmarks
uv run pyright
git diff --check
```

Cheap live honesty check for `pc:bonogo` (one `get_complete_object`, no cold/warm timing rerun):

```text
returned: relationships=30 endpoints=25 assertions=1 (existence=1) anchors=47
completeness=complete
revision/head=rev:680c246047d67f9fe0293ee90526f670 (unchanged)
```

The Cycle 2 live timing (~534ms cold / ~327ms warm) is still the characterization witness. Adding the existence row does not change that disposition.

DungeonMindBuddy #697 remains **DESIGN HOLD — CODE NOT STARTED** until this PR is accepted. After this repair, the Cycle 2 reviewer currently sees no remaining reason to keep #52 from merging.

