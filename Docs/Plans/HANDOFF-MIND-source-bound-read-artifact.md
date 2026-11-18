# Source-bound compact native read artifacts

Status — active design and implementation lease. Independent review found
no fundamental blocker; promotion obligations are specified below.
Owner — the active Elderwyld pre-cutover performance lane.

## Authority and outcome

The operator requires optimization before V8 acceptance and V9 cutover
preparation. Authoritative base is Core main
3025ac182ebdaae3544dd52f965bb3c472bad514, the accepted #215 merge.
Core #211 and #213 are also accepted. Metadata reuse #212 and bulk decoding
#214 are closed without merge. The source family remains the frozen generic
vNext contracts and the current parsed-model/read-context semantics.

The target is the same authorized, ordered, exactly cited neighborhood result
at or below the retained approximately 540 ms paired classic cold reference.
Preserve the native warm advantage and check affected governed-write routes.
The complete objective continues through accepted V8 and the vNext roadmap.

## Existing evidence

At Core runtime e8f70e45 and retained Buddy
ca5a0450489a94cd364183af1c53d3f041ad7d0f, the ordinary 10k native route took
1599 ms cold and 194–206 ms warm. Full verified revision retrieval took
175–183 ms. Exact responses and citations passed.

Scratch v4 represents the complete parsed model with dense primary tables,
exact-byte metadata pooling, string references and sparse default indexes.
Its retained artifact is 6156911 bytes. Hash/decode samples were 151–224 ms.
A file-backed HTTP test hook measured 519 ms cold and 198–202 ms warm.
It retained full get_revision checks, verified complete source-envelope and
graph pins, checked artifact bytes, cleared the parsed memory cache, compared
full response bodies and reopened exact citations.

These are single diagnostic runs on a retained Buddy pin, with a precomputed
artifact and warm OS file cache. Production storage and hardened decoding
remain unproved. The original baseline remains retained.

## Production representation and source proof

A production artifact represents compact native primary wire data. Exact
canonical source metadata bytes are pooled within one artifact. Numeric
representations, signed zero, JSON ordering where meaningful, and timestamp
offsets retain their source form. Cache parsing derives immutable metadata
from validated source metadata once per distinct canonical byte sequence.

The reader first performs the existing full get_revision verification.
It binds the artifact to the complete verified revision-envelope digest,
graph payload SHA, codec version and parsed format/schema manifest.

The decoder reconstructs the canonical native primary payload represented by
the artifact and recomputes its SHA-256 against the verified graph payload SHA.
Implement this as a streamed canonical reconstruction with fixed, reviewed
wire-field ordering. Metadata and value chunks must each validate as complete
contract values. This binds every decoded fact to the actual source payload
even if persisted artifact bytes and their own checksum are changed together.

Build cached representation from the original stored canonical source data.
A parsed model alone can lose source array order, default-field presence or
timestamp representation. Source forms outside the codec's lossless support
use the ordinary parser through an absent/unsupported artifact result.

Derive parsed identity from the fresh verified source envelope. Derive all
structural indexes and the semantic digest from the verified primary facts
using shared current builder logic or a proven equivalent canonical stream.
The production fast path must establish complete record/index/digest equality.

The exact expanded chunks used in the source-hash proof are also the inputs
validated and converted into parsed facts. A parallel supplied decoded value
cannot establish authority. Test an artifact that keeps the proof stream
unchanged while attempting to alter separately supplied normalized data.

Version-one eligibility is explicit. Preserve actual source array order and
raw canonical metadata/value chunks, including timestamp spelling and coercible
wire values. Root extensions and omitted entity/assertion schema fields are
unsupported until the codec can represent their exact presence. The producer
checks complete payload reconstruction against the source SHA before storing.
Raw source chunks must validate as complete records through the same contract
validation mode as the ordinary parser.

The artifact checksum protects its byte representation. The separate source
payload proof establishes graph equivalence. Current source/provenance
authority opens afresh after immutable graph preparation.

## Decoder contract

Use explicit, versioned field and constructor schemas. Public generic
contracts remain the validation reference. Freeze all returned JSON values.
Private reused mutable validation models stay inside the decoder.

Validate exact packet fields and tag arities, canonical bounded references,
primary identity uniqueness, allowed field types and record variants.
Reject duplicate JSON keys, unexpected dictionaries, nonfinite numbers,
exponent overflow, illegal forward references and wrong table relationships.

Bound work relative to the verified source size and fixed index schema.
Streamed source reconstruction must stop if it exceeds the verified canonical
source byte count. Artifact-size/framing limits must cover every output of
the supported encoder. Unsupported cache representation preserves the ordinary
read fallback for otherwise supported source data.

Apply the verified-source-relative byte limit before packet parsing. Require
the format's fixed nesting shape, bounded reference counts and referenced
string/metadata tables. Reject unused entries and stop repeated-reference
expansion at the verified source byte ceiling before constructing records.

Persisted-source timestamps are validated through the same current wire
contracts. A general Python ZoneInfo roundtrip is outside this codec's
persisted-source interface; test that boundary explicitly.

A matching-version malformed artifact raises a typed persistence-integrity
failure. An absent or unsupported-version artifact uses the ordinary parser.

Known unsupported source representation produces no cache row and preserves
ordinary publication/read behavior. Unexpected generation faults or artifact
write failures roll back the new publication transaction. Receipt replay adds
no implicit cache-generation work. Explicit backfill takes source identities,
locks/revalidates that exact source and writes only its derived artifact.
Test backfill races with head advance and source-row updates. Read-only
consumers perform no cache writes.

## Serial PR slices

1. Private source-bound codec and builder helpers on this pinned Core base.
   Include source-hash proof, strict decoding, immutable output and exact
   record/index/digest differential tests. Preserve public signatures.
   Prototype the hardened implementation through the ordinary 10k route.
2. Core artifact store, read integration and writer/backfill generation.
   Base this child on the accepted codec commit. Use an optional read capability
   so existing repository implementations keep their normal fallback.
   Persist byte-exact artifacts and their source/format binding. Generation
   accepts source identities and derives content internally.
   Keep ordinary revision/head/event/receipt publication atomic. Preserve
   existing generic/opaque source behavior when artifact generation is unsupported.
3. Buddy dependency adoption and owning route acceptance.
   Pin accepted Core and use the actual PostgreSQL artifact store.
   Capture current candidate cold/warm data and exact output parity against
   retained evidence before preparing cutover.

Name the exact parent PR and merge/rebase order when each child is dispatched.
A handoff can be pinned on its implementation branch under existing repo law.

## Required proof

Compare complete parsed records, every index and semantic/compatibility digests
against the ordinary parser. Include all visibility/temporal variants, empty
graphs, Unicode, complex literal/domain JSON and source-order/default variants.
Use representation-sensitive checks beyond Python equality.

Cover bool versus int versus float, signed zero, offset timestamps, metadata
mutation isolation and no mutable validation-model escape. Cover malformed
packet framing and references, duplicate identities/keys, unknown constructors,
index inconsistencies and resource expansion.

Forge primary facts and recompute artifact checksums. The source payload proof
must still reject them. Cover wrong space/revision/envelope/format pins and
source-row corruption under the unchanged full revision verifier.

Verify read-only cache consumption, old-data fallback, source withdrawal at
an unchanged graph pin, historical reads and concurrent access. A memory-cache
key must snapshot complete envelope representation and canonical graph text;
mutable model equality must not conflate changed timestamp representations.

At the store boundary prove generation from the exact source, publication and
cache rollback, same-ID replay, concurrency and descendant replay. Measure
publication/cache generation costs before accepting the complete change.

At Buddy verify the current requested route, full ordered DTO equality,
exact reopened citation bytes, scope/visibility isolation, fresh source
authority and both cold/restart and warm conditions. Record exact candidate
pins and cache conditions. V8 acceptance requires actual production-path proof.

## Retention

The task owns and retains the existing Core worktree under
/home/drakosfire/Projects/.codex/v7-elderwyld-scope/worktrees/DungeonMind
for design, implementation, review and delivery. Existing environments are
reused. Evidence is under the task's scratch/v8-core directory, indexed by
parsed-snapshot-findings.md. Synthetic artifact binaries and probe outputs
remain retained for diagnosis. Existing fixture databases were dropped.
The named codex_vnext_cold_20261118 verification database remains retained.
Cleanup follows delivery after active-process, dirty-data, mount and
unique-commit checks, with explicit scope for each removal.

## Design review and newer feasibility evidence

Independent review of 2c189898 against the pinned base found no fundamental
design blocker and confirmed the full revision/source freshness boundary.
The review required explicit lossless eligibility, shared proof/consumption
dataflow, complete canonical reconstruction, pre-expansion resource bounds and
defined fallback/store failures. These obligations are now part of the lease.

A newer scratch wire representation is 2291486 bytes for the same retained
10k payload. It proves the original source SHA, validates primary contracts,
rebuilds all indexes and recomputes the semantic digest. An offline diagnostic
under a synthetic lab envelope produced complete ordinary-parser equality and
rejected a forged fact after its artifact checksum was recalculated.
Hash/decode samples ranged from 185 to 458 ms, including object replacement.
Its matched HTTP probe remains a feasibility experiment. Production framing,
static helpers, actual-store measurements and full acceptance remain pending.

## Codec implementation checkpoint

The codec implementation branch is stacked on design PR #216 exact head
63d24166f40dcd1823b5a560c1c02d38162234cc. Merge/rebase order is design #216,
complete private codec/builder implementation, Core store integration, then
Buddy adoption. The implementation PR remains draft until its complete slice
passes independent review and candidate-route verification.

The first implementation unit adds `_source_wire.py` and its owning unit tests.
It losslessly encodes the supported primary wire, binds the complete fresh
revision envelope and graph SHA, and reconstructs that source through one
proof/consumption dataflow. It rejects duplicate JSON keys, nonfinite numbers,
wrong table references, unused/duplicate pool entries, oversized packets,
deep chunks, expansion overflow and altered facts. Source forms outside the
lossless representation are explicitly unsupported. Unknown codec versions
return fallback; malformed matching versions raise PersistenceIntegrityError.

This unit returns verified mutable primary wire, not a parsed snapshot or an
admitted result. The ordinary contract/parser/index/digest checks remain required.
It is private and unconnected to runtime reads. The fast immutable parsed factory,
static builder helpers, source-relative work checks and candidate-route measurement
are still required within this implementation slice before promotion.

Validation at this checkpoint: 53 new source-wire checks pass; 149 checks pass
across source wire, parsed revision, governed materialization and PostgreSQL
revision reconstruction unit suites. Focused Ruff passes. The original baseline
was not rerun. The existing 472 ms scratch HTTP observation is feasibility evidence
only; it does not establish production performance acceptance.

No new worktree, environment, database or standalone output was allocated for
this unit. The existing task-owned worktree and environments remain retained for
active implementation/review; cleanup follows delivery under the existing
retention rules. No artifacts were removed and no reclaimed bytes are claimed.

The next codec commit extracts the existing evidence, alias, assertion-metadata
and revision-identity conversions into private static builder helpers. Ordinary
builder reference checks and failure order stay in place. The ordinary builder
uses these helpers directly; the future fast factory will share them without
runtime AST extraction or global function substitution. The same 149 checks,
focused Ruff and diff checks pass after extraction. Independent review remains
required for the cumulative codec implementation.

Independent checkpoint review of258363fc found one P2 fallback issue: v1 packet
depth was enforced before version identification. The repair uses a generic
64-level preparse allocation bound for version identification, then applies
v1's three-level packet shape only to matching versions. Future-version packets
with deeper shapes now use ordinary-parser fallback. Generic byte/allocation
bounds continue to apply to every version. 56 source-wire and152 combined
owner checks pass after this repair; focused Ruff remains clean. This is
checkpoint review, not acceptance of the unfinished fast factory.
