# MIND — verified native extension receipt recovery

ACTIVE design prerequisite under explicit operator full-lane implementation,
review and merge authorization. Owner MIND; independent review required. Base
fdcf65435b25e49ad24789a6ed66ab8abb3bad87 on origin/main; branch
codex/v10-native-extension-receipt-recovery in existing task Core checkout.

## Outcome and sequencing

One capability: read-only verification/recovery of the exact committed native
source evidence extension, including governed contributions and result mappings,
after descendants or source withdrawal. This does not authorize source reads or
fresh publication. Buddy immutable profile declaration is an independently
reviewable prerequisite; Buddy manual backend adoption follows accepted Core
recovery and exact dependency repin. No standing ARCH/PRIME permission gate.

Existing publisher explicitly requires current source availability before replay.
Preserve that behavior and its current-access refusal tests. Do not move its
receipt lookup ahead of authorization as a shortcut.

## Bounded proposed write lease

- This handoff.
- src/dungeonmind/application/vnext/native_source_extension.py: new recovery
  entry point and narrowly shared immutable verification only.
- src/dungeonmind/application/vnext/__init__.py: explicit public export if needed.
- src/dungeonmind/application/vnext/ports.py: only if existing read ports cannot
  express the immutable verification; checkpoint exact addition before editing.
- tests/unit/test_vnext_native_source_evidence_extension.py.
- tests/integration/test_postgres_vnext_native_source_evidence_extension.py.

No migrations, persisted contract edits, private Buddy imports, D&D/profile
meaning, adapters, publishers, withdrawal behavior, source restoration, serving,
provider calls or real corpus writes. Checkpoint before expanding this lease.
Audit current open PR regions before code. Current audit found process158 and
historical143/145-150; none grants ownership of their changes.

## Contract and integrity

Trusted host checks current principal, World ownership and binding before receipt
IO. Core operates on the exact host-selected space and original request plus
original immutable descriptors. Recovery is a privileged persistence result
capability, not a projection or source-access capability.

Match the complete original extension intent including governed contribution,
dispositions, source identities, expected parent/body/epoch/time, spans and
metadata. Changed same-ID input or descriptors is an idempotency conflict.
Verify original admission and origin, parent ancestry and refs, deterministic
span/evidence bindings and exact committed child command/payload. Recompute
governed materialization and result bindings from immutable parent/evidence;
never trust an unverified stored mapping. Validate proof metadata against retained
immutable authority without requiring present availability or original epoch to
equal current epoch. Missing/corrupt referenced committed state fails closed as
persistence integrity, never outcome_unknown or a recovery miss.

Absent receipt returns absence without writes/reservation/publish/retry. A generic
publication receipt claiming the ID with missing extension receipt is a conflict
or integrity error, never permission to publish. Return only verified receipt and
mapping; no body/source text. Successful recovery must not make withdrawn
citations available or allow fresh extension publication.

## Metadata-only verification decision

Independent readiness review selected metadata-only committed-outcome verification.
Reconstruct span proofs from the exact original request and validate them against
immutable committed evidence/receipt/child and original admission linkage. Do not
open source views/body readers or reauthorize projection access. This proves the
committed operation and mapping, not independent recomputation of source byte
slices or UTF-8 boundaries. Those were publication admission obligations; do not
claim fresh body verification after withdrawal. No persistence adapter expansion
is authorized for internal body access.

Verify revision envelope identity, payload digest, descriptor refs and command
linkage for original admission, expected parent and committed child. Absence is
an observation before a concurrent commit, not a promise that no later commit can
occur; completed atomic commits must never be classified absent. No receipt plus
a publication is corruption/conflict. SQL/memory public-boundary tests must cover
these distinctions without inventing a write retry.

## Required proof

Memory and disposable PostgreSQL public-boundary tests: exact recovery, governed
result mapping, later-head and withdrawn-source recovery, source text not opened,
no duplicate events or writes, altered request/descriptors and forged bindings,
wrong space, missing/corrupt parent/child/proof/receipt, ambiguous publication
response followed by recovery. Preserve existing fresh-publication/replay refusal
under withdrawal and original admission/extension behavior. Host wrong-owner
checks belong in subsequent Buddy HTTP tests; Core tests do not pretend to own
product authentication. Unit/conformance, affected SQL, Ruff/Pyright, exact
cumulative independent review and CI are merge gates.

## Resources and state

No implementation or recovery test has run at activation. Existing findings were
source inspection: current-source opening precedes receipt lookup; public generic
receipt verification alone does not establish full extension intent/proofs.
Task root /home/drakosfire/Projects/.codex/v7-elderwyld-scope; Projects UUID
48fa5d10-fe99-4557-9fc9-d8a2a4b41ac8 and parent writability verified in actual
executor. Reuse existing checkout/environment, no new worktree/cache yet. New
scratch, if needed, stays task-owned beneath Projects after storage revalidation.
Retain active evidence, caches and checkouts under MIND ownership; cleanup awaits
approved scope and process/mount/dirty/unique-commit checks. No deletion or
reclaimed bytes. Full vNext deployment and V11 acceptance remain open.
