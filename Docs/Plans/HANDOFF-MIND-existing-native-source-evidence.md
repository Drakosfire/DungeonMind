# MIND — existing native source evidence

ACTIVE: PRIME solo implementation under OverMind3bc3dc2c3f54137b0a5f74dfc333a9c393e84e06, independently approved and merged e0fbe634810fa1d218c90fcb2a4047dbfe0ce2b2. Base38c87bc78bcd05a538bd89fdbb928fca54c3a283, reused clean prime-first-world-spans checkout, branch codex/existing-native-source-evidence. Exact 12-path lease is in the owning OverMind handoff; no other files, retained data, runtime services or providers. Core143 and145–150 and Buddy1163 excluded.

One capability: append exact evidence for an immutable existing native source, preserving original identity/body/receipt, new immutable extension receipt, atomic epoch+head checks, authorized replay, and pinned reader composition. Duplicate intervals refused; distinct overlapping intervals allowed. Buddy consumption and independent actual-V7 integration follow separate activation.

Verification requires memory and real PostgreSQL public-boundary success/refusal/recovery/conservation, exact cumulative independent review and CI before PRIME merge. No claim of delivery or full-chain acceptance.

## Implemented boundary, pending independent review

Extension request contains only retained source identity/root, expected body digest,
parent/epoch and exact intervals; retained body and source metadata are resolved
through existing Core access. Every repository snapshots mutable inputs, holds
its epoch/publication lock, authorizes current source access, recovers exact prior
receipt before new-work CAS checks, and publishes an evidence-only native child
plus separate extension receipt. Duplicate intervals reject; overlaps remain
separate. Original records and receipts are never rewritten. Reader composition
checks extension lineage/fingerprints and pins proof visibility to source epoch;
old revision membership still controls access. Extension chains must descend from
the original admission. Memory rollback and PostgreSQL transactions own all writes.

34 memory/original-admission checks pass;32 actual PostgreSQL/original-admission/
migration checks pass using existing shared Python3.13 and a uniquely named
synthetic database per invocation, removed in finally. No retained database was
migrated. Coverage includes nonempty entities/assertions/aliases preservation,
original source/receipt/prior revision equality, epoch-pinned readers before and
between extensions, same-key replay after descendants, repository reopen,
current-access replay refusal, wrong root/source/body/slice/metadata/epoch/parent,
duplicate intervals, overlap, concurrent same-key and stale parent/epoch races,
every injected transaction rollback stage, lost acknowledgement, tamper refusal,
and populated downgrade refusal. Contract JSON reproduction, whole-repo Ruff
and cumulative whitespace checks pass. Initial local environment lacked psycopg
before database creation; existing shared environment was used without a new
installation. Initial synthetic assertion/fixture mistakes were corrected before
final runs; no product gate was relaxed.

No Buddy adoption, private corpus integration, provider call, deployment, accepted
native V7 publication or full-chain score is claimed. Exact cumulative independent
review and CI remain merge gates.
