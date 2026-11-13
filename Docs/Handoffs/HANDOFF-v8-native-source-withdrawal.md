# V8 native source withdrawal

Status: proposed Core prerequisite. Base: `71bdd318c76ed24266068c4237e70e86c98d1f9b`.

V8 requires fresh source authorization to reflect withdrawal without a graph
publication. The native source port currently exposes admission, evidence
extension, and epoch-pinned reads. The Core refresh test injects a retracted
source into a newer view. It proves read policy but supplies no durable
transition. Buddy's classic assertion withdrawal publishes a graph child and
does not satisfy this requirement.

## Serial delivery

1. Core owns the source authority transition and adapter conformance. Prove it
   with in-memory and disposable PostgreSQL fixtures. Review this change on
   Core main before Buddy repins.
2. Buddy owns the mounted citation witness at the merged Core pin. Verify exact
   bytes before withdrawal and no body afterward at the same graph pin. Record
   the route, principal, Core/Buddy commits, source epoch and result digests.
   Review on Buddy main before crediting the witness in joint acceptance.

This slice requires independent review. It uses synthetic sources. Any serving
authority change remains a V9 operation.

## Core invariants

- Scope withdrawal to an exact space and admitted source identity. Missing or
  cross-space selectors fail without advancing the authority epoch.
- Preserve admitted bodies, immutable admission records, receipts, and proofs.
  Record withdrawal separately under the same authority lock that orders epoch
  changes. A repeat of the same transition must not advance the epoch again.
- A view pinned before the transition must keep coherent source metadata.
  A new view must see withdrawn standing. Verify that metadata and exact body
  opening agree, including access through extension spans and PDF readers.
- A withdrawal commits no revision, head change, head event, or graph
  publication receipt. Verify rollback, retry and concurrent same-target
  behavior in PostgreSQL. Verify the graph and source read paths at the same
  current and historical graph pins.

The V8 joint artifact remains open until the mounted witness and the other
semantic and performance gates are proved.
