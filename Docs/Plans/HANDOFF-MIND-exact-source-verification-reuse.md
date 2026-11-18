# Exact current-source verification proof reuse

Status: ACCEPTED DESIGN ONLY; no runtime implementation accepted.
Reviewed24a8bdf merged as0dc8c357f05d884d01a9fdd720a20f33d0f52fa0 via226,
independent approval and all CI44412416098 jobs passed.
Owner: Elderwyld pre-cutover optimization lane. Authority: operator goal and
implementation/review/merge authorization; this is an explicit owning-lane rebrief.
Base: accepted224 f174923bf7962f78d14faeb36a41f77004520676.

## Problem and decision boundary

The paired10k reference remains~540ms classic versus original~2.12s native.
Accepted parsed/index reductions and Buddy3994 remove real work but full-app
misses still exceed the reference. Whole get_revision verification reconstructs
and canonicalizes identical source JSON on every context, before parsed lookup.
Buddy read_repository creates a fresh repository each time: an instance-local
memo alone cannot remove repeated work. Source parser225 was rejected unmerged:
no speed improvement and deep-fallback recursion compatibility loss. Do not reuse
that parser or silently absorb another capability into draft storage218.

Propose reusing a successful PURE verification proof only when the COMPLETE
current database representation is byte/representation-identical. Always query
current source first. This explicitly revises earlier handoffs' no-verification-
cache condition and literal repeated-recomputation requirement. It does not
revise source authority, corruption detection, admission or source freshness.
This document must receive independent design review before implementation.
Neither it nor allocation acceptance is performance/V8/cutover acceptance.

## Mandatory proof and ownership

1. Read the entire exact requested source row in one fresh SELECT on every call;
   no digest-only SELECT, head-only key, TTL, missing-row reuse or graph-ID trust.
   Retrieve graph JSONB and envelope JSONB as text to avoid decoding a hit. Retain
   all scalar columns currently verified: space/revision/parent, created_at,
   graph_schema, graph hash, schema_version, record_fingerprint. Missing rows
   return None even if a prior proof exists. Database/permission errors propagate.
2. Key equality covers requested identity, every selected scalar, exact graph
   JSONB text, exact envelope JSONB text and explicit verifier compatibility
   version. No Python JSON/model equality: bool/int/float, negative zero, offset
   spellings and unknown envelope fields must not conflate. Snapshot timestamps
   into immutable representation strings, not equal-instant datetime keys.
   Nonstandard raw types bypass reuse and follow ordinary failure/validation.
3. A miss executes the UNCHANGED complete reconstruction proof: original JSON
   decoding, canonical graph serialization, full record fingerprint, payload SHA,
   all column/envelope checks and recomputed revision ID. Cache only after success.
   Never populate from declared hashes, artifact bytes, caller models or a failed
   proof. Keep ordinary serialization at its existing call depth; do not introduce
   another helper/callback frame around canonical serialization as225 did. Deep
   opaque fallback must retain the reference's supported depth/error behavior.
4. A hit means every current raw source field equals a previously proven field;
   changed raw representation forces the full proof even when values are Python-
   equal or declared hashes are unchanged. This is exact-content proof reuse,
   not authority delegated to a checksum or a belief that revisions never drift.
   Direct SQL corruption remains observable before parsed-memory lookup.
5. Store only immutable key/proof content: canonical envelope text, canonical
   graph text and verified hash/identity primitives. Return fresh envelope models
   and StoredKnowledgeRevision objects each call. Caller mutation of one returned
   model must not poison future results or the cached proof. No exposed mutable
   dict/Pydantic model, caller record or authorized read context retained.
6. Cache ownership is explicit, service/reader scoped and thread safe; no implicit
   process-global semantic cache. It must be injectable across ephemeral read
   repository instances without sharing transaction/session state. Keep a bounded
   single entry AND an explicit byte cap covering raw and canonical content;
   measure/select consumer budget before adoption. Oversized entries verify
   ordinarily and are not retained. No arbitrary source eviction or GC changes.
   Concurrent get/put/clear races must preserve semantics; failed loads cannot
   poison or evict a last-good proof accidentally. No lock around database I/O.
7. Parsed-format/profile compatibility and parsed revision caching remain separate.
   Every successful context still opens fresh provenance/source authority. Audience,
   domain/profile validation, scope/standing/visibility, withdrawals and citation
   body/span checks remain current. This cache stores no permission/admission.

## Serial reviewable delivery

Slice A (this PR): design/handoff only, exact one-file lease; independent review
of proof equivalence, ownership, memory bounds, error and compatibility policy.
No runtime edits, no performance claim. Accept or revise this decision first.

Slice B: separate Core implementation from accepted compute main. Private
bounded proof cache plus PostgreSQL raw-row read integration and owning unit/PG
regressions; pin exact changed paths and commit a bounded implementation lease
before code. Ordinary get_revision behavior remains correct without injection.
No new required repository-port method, migration, table or artifact source.
Reject/refine if supported-depth parity cannot be preserved. Independent cumulative
review and exact CI required. This is not an amendment to rejected225.

Slice C: separate Buddy wiring of an explicit service-owned proof cache, dependent
on accepted Core API/pin. Pin changed adapter/test/dependency paths and prove normal
standalone defaults and process ownership. Required Buddy owning/auth/frontend
checks follow its repository process. No routes/DTO/authorization changes.

Pinned local Core-storage-Buddy compositions may measure before acceptance;
name exact parents and source fingerprints. Rebase draft storage218 only after
accepted compute; do not fold the proof-cache implementation into its scope.
Joint candidate evidence must precede accepting the optimization/cutover gates;
never deploy an unaccepted dependency composition to5202.

## Required evidence

- Owning tests count a fresh complete database source read every call and full
  reconstruction once for identical rows; raw representation changes force work.
- Direct PG/current-memory-hit corruption matrix covers every selected column,
  malformed/unknown envelope, changed graph with unchanged declared hashes,
  self-consistent forged fingerprint/hash but invalid revision ID, missing source,
  and equal-semantics/different-number-or-offset representations. Compare results
  and typed failures to ordinary reconstruction; never trust helper-only tests.
- Caller-envelope mutation, thread races, incompatible verifier namespaces,
  clear/eviction/byte-budget bypass, deep/opaque payloads and rollback/failure
  behavior preserve independent verification and immutable ownership.
- New/historical/current pins each read exact current source; a successful proof
  cannot mask later SQL corruption, source withdrawal or cross-scope denial.
- Full-app/lifespan/real HTTP candidate: normal readiness with zero graph prep,
  first/warm/eviction/new/history/citation, exact ordered authorized output and
  citation bytes, fresh source views, actual loaded source fingerprints, byte/RSS
  budget, matched write cost and affected routes. Keep work-removal regressions.
- Reuse the retained classic baseline; do not rerun it. Native must meet or beat
  comparable retained cold latency, retain warm advantage, and resolve slower
  representative misses before V8 acceptance. V9 remains gated until jointV8.

## Current state and resources

Accepted main224 f174923. Storage218 remains draft, runtime equivalent to measured
b2263ae; source-streaming225 final3773333 closed unmerged, measured5e0d6f2.
No verified-source cache exists or is accepted. No serving pin/deployment/cutover
change. Remaining full-goal gates include affected routes/withdrawal/history,
matched writes/current Buddy adoption/jointV8, then rollback/V9,V10,V11.

Reuse task-owned Projects Core/Buddy checkout/env. Scratch evidence/unique refs
remain under v7-elderwyld-scope; filesystemUUID48fa5d10-fe99-4557-9fc9-d8a2a4b41ac8.
This lane owns retained preflights/probes/JSON/log/pytest/resource receipts for
review and dependent integration. Cleanup follows explicit scope and process/
mount/dirty/unique-data/commit checks. No new worktree/env/cache or removal.
All previous probes terminal; owned disposable PG databases dropped when idle.
