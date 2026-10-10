# HANDOFF — NATIVE: operator-attested binding for an existing source span

**Created:** 2026-10-09

**Status:** DESIGN FOR INDEPENDENT REVIEW; no runtime or data lease active

**Repository / branch:** `Drakosfire/DungeonMind` / `codex/operator-attested-source-span-binding`

**Base:** `b340cffabd93fda411b7aac68e6ad2c0aeb66522` (PR #107 merge)

**Owner sequence:** DungeonMind contract and source authority → trusted owner/GM approval host → Buddy producer and consumer adoption → separately governed rollout

## §1 Decision and reason for this slice

PR #107 accepted the additive legacy-to-native proof-binding shape, but its implementation stopped at a real authority gap. A body digest proves exact bytes, and a slice digest proves a byte interval; neither proves that the passage is what an existing semantic `source_span_ref_id` and `evidence_ref_id` were intended to cite. A newly supplied mapping record would merely restate the caller's choice. Current DungeonMind has no independently authenticated mapping-provenance registry or original producer receipt for this exact association.

The minimal repair is a **server-prepared, operator-attested association**. An authorized owner/GM sees the exact existing claim and evidence identity beside a bounded passage from the immutable revision and explicitly approves that passage as the intended support. The server records the authenticated actor and approved command in an append-only receipt. This approval establishes the missing semantic association; byte and digest checks then establish that the approved association has been stored unchanged. Approval does not accept a source claim as new graph truth, change the evidence, or rewrite legacy history.

This document extends `HANDOFF-NATIVE-legacy-source-span-proof-binding.md` at its mapping-provenance gate. Its identity, source-epoch, idempotency, privacy and no-graph-mutation constraints continue to apply. This PR is design only.

## §2 Authority and authentication prerequisite

Read `Docs/Architecture/AUTHORITY.md` §§1–5, 8; ADR-0028; the PR #107 handoff; `contracts/vnext/native_source.py`, `application/vnext/native_source_access.py`, the native source ports/adapters, and the legacy source/adoption contracts before runtime work. Also inspect `contracts/contribution_review_v2.py`, `contracts/capability.py`, `contracts/mind_turn.py`, and `service/publication_access.py` before choosing a host binding.

The existing review intent and confirmation receipt compare `reviewer_id` with `actor`, but both values are supplied in the submission. `CapabilityPolicy` scopes agent tools and does not identify an authenticated human. `CallerScope` is filled by an external authorized host; a raw request object is not proof of identity. `PublicationAccessBinding` authenticates a bearer token for one world but does not identify an owner/GM actor. None can be reused as an authenticated `approved_by` field by itself.

**Implementation prerequisite:** the owning host must provide a trusted, server-derived approval context that authenticates a specific actor, verifies owner/GM authority for the exact space/world and review action, and binds that actor to the approved prepared command. The Core operation must consume that trusted result through an authority-approved boundary and derive receipt actor/time server-side. The exact principal/session representation, trust anchor and host adapter remain a concrete owner contract to settle before runtime implementation. Do not create a request field called `approved_by`, accept a caller-supplied actor string, or treat a world bearer token as a human identity. If the host cannot provide this binding, the implementation remains blocked; there is no fallback self-attestation.

## §3 Prepare → review → approve → commit

1. **Prepare.** The server accepts an exact `space_id`, expected current native head, typed claim target, existing `evidence_ref_id`, existing opaque `source_span_ref_id`, legacy artifact/revision IDs and exact UTF-8 body bytes supplied through the trusted producer host. It resolves the claim and evidence from that exact native graph revision and verifies the evidence is an admitted support for the selected claim with matching artifact/revision/span/role and open/highlight flags. It reads the authoritative legacy artifact/revision metadata and verifies the supplied body SHA against the stored revision. It computes candidate half-open byte intervals from an explicit producer passage selection against those verified bytes. Opaque IDs never yield offsets. A non-unique or missing passage yields no approvable candidate until the operator selects an unambiguous server-produced occurrence. Each candidate carries start/end bytes, slice SHA-256 and body SHA-256; a caller path or locator never grants body authority.
2. **Review.** The trusted host presents one immutable prepared candidate: exact claim target and safe claim text, existing evidence ID and semantic span ID, source artifact/revision identity, bounded passage and enough surrounding context to judge support, byte interval and digest pins, and an expiry. It does not expose an arbitrary source browser. The operator must be able to reject or approve the exact candidate; review does not auto-approve based on a matching hash.
3. **Approve.** The host authenticates an owner/GM and authorizes this action for the exact space/world. It passes a trusted approval binding for the prepared command; the public request carries only the prepared operation identity, never an `approved_by` value. The server records its own approval time and the authenticated actor/role provenance. The server durably retains the immutable prepared command, bounded review excerpt, expiry and canonical digest; no native source body/proof or source-epoch change occurs at prepare. Its lifetime is at most fifteen minutes. Its digest binds the exact claim/evidence/span, artifact/revision/body SHA, interval/slice SHA, policy snapshot and expected head. Commit obtains the same complete bytes again and verifies them against this preparation.
4. **Commit.** In one source-epoch-before-space locked transaction, Core rereads the exact prepared record, current head and graph evidence membership; legacy artifact/revision standing and policy; body and interval digests; trusted approval binding; and expiry. It rejects a changed or stale prepared command before mutation. It atomically stores the native body copy, `NativeUtf8SpanProofV1`, source epoch increment and an append-only `dm_native_operator_span_attestation_v1` receipt under the existing artifact/revision/span/evidence IDs. No native child, graph event, head movement, legacy-row rewrite or V1 admission receipt is created. Later source reads still require exact evidence membership in the caller's native revision, audience visibility, active standing and the complete proof.

The receipt records `provenance_kind=operator_attestation`, operation/preparation IDs and canonical hashes, source artifact/revision/body SHA, claim target, evidence/span IDs, interval/slice SHA, authenticated actor and approval time, original expected head, committed source epoch and a record fingerprint. It contains no source body or unbounded passage. The prepared record and receipt are immutable; replay with the same operation ID and exact command returns the original receipt after descendants, while changed intent is an idempotency conflict. A lost response is recovered by that same ID. A different operation cannot overwrite an existing binding for the same exact evidence/span; corruption is a typed integrity failure.

The review display is a trust boundary. It must be generated from the same server-held prepared record used at commit, with an exact preparation digest. A client may choose among server-generated candidates but cannot alter the displayed passage, claim, interval, expected head, actor or role in transit. Rechecking only the body SHA at commit is insufficient: the prepared command, approval binding and all member identities must still match.

## §4 Alternatives and applicability

- **Recovered original producer receipt:** If a preexisting immutable producer record can independently prove the original association of the *same* artifact/revision/body SHA, evidence/span IDs and byte interval, Core may accept it through a separately reviewed verifier instead of a new operator attestation. Merely generating a receipt from today's chosen offsets does not qualify. The PR #107 stop remains until that verifier is specified and proven.
- **Fresh native text admission:** `NativeTextSourceAdmissionV1` already stores bytes and proofs atomically, but allocates new artifact/revision/span/evidence IDs and publishes a new child. This can support a new source ingestion; it does not make the existing Session 22 evidence readable without a separately governed graph rebind. It is not a shortcut for this operator-attested binding.

## §5 Synthetic acceptance and falsifiers

Use invented UTF-8 text and claims. A fixture carries exact native space/head, typed claim target and its evidence membership; existing legacy artifact/revision/body digest and generic policy; existing evidence/span IDs and flags; prepared operation ID, candidate interval and slice digest; preparation schema/version/digest/expiry; server-generated review display digest; authenticated owner/GM approval binding; and the final receipt fields in §3. The Session 22 IDs in PR #107 are a shape witness only; do not include actual source text or offsets in tests or this design PR.

Owning-boundary tests for the later implementation must prove:

- valid operator approval makes only the exact existing evidence and revision openable; old source-epoch views remain unchanged and a fresh view sees the complete proof;
- a different passage in the same body with a valid slice SHA fails when it is not the passage in the reviewed prepared command;
- expired, altered or replayed-with-changes preparation fails; switching claim, evidence, span, artifact, revision, interval, policy, head or review display after approval fails;
- caller-supplied `approved_by`, missing/unauthorized/wrong-world actor and missing trusted approval binding fail before mutation;
- stale graph head, removed or changed evidence membership, changed legacy source standing/visibility/revision/digest, malformed UTF-8 and wrong body/slice hash fail before mutation;
- same-ID exact replay, conflicting replay, concurrent competing approvals, response-loss recovery and corrupted stored receipt are distinct outcomes;
- every rejected case leaves native body, proof, receipt, epoch, graph/head and legacy source rows unchanged in both in-memory and PostgreSQL adapters; accepted V1 native admission remains unchanged.

The approval test double must represent a trusted host result and must not be constructed from the public submission's actor field. PostgreSQL tests must cross the transaction boundary. A live corpus or operator review is not an acceptance fixture for the Core PR.

## §6 Execution gate and handback

This PR writes only this document. Independent design review must first settle the approval trust anchor and exact host-owned identity/role binding. Subsequent implementation is one bounded Core contract/port/adapters/source-view PR with synthetic tests, only after that prerequisite is pinned. Buddy's producer/review surface and live Session 22 operator approval are later separately leased work. No actual corpus review, body/offset write, migration, runtime change, provider call or graph mutation occurs here.

Stop future implementation if no trusted owner/GM approval context can be proven, a prepared passage cannot be tied to the exact claim/evidence/span, policy standing is ambiguous, a candidate requires inferring positions from an opaque ID, the current head or source changed, or the operation would change graph truth. Return the exact missing authority or identity to PRIME; do not weaken the attestation requirement to keep the flow moving.

Hand back repository/base/head/PR, reviewed contract choices, the unresolved host authentication prerequisite, synthetic proof obligations, what remains false, and the next named Core and Buddy owner actions. The present Session 22 source remains unavailable until those later operations are accepted and the operator actually approves its exact passage.
