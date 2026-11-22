# Typed PostgreSQL citation proof reads

The exact-text reader uses typed span proof rows and a separately stored
publication manifest. The canonical native admission, extension, and governed
publication receipts remain the immutable publication records. Admission metadata
and body bytes still come from the owning native source row. Authorization still
runs through the pinned evidence and source access context.

A manifest binds each proof fingerprint to the exact source revision, original
admission, publishing receipt, and authority epoch. The read reconciles scoped
manifest headers against canonical receipt identifiers and fingerprints. It
reconstructs only requested proofs. Independent manifest membership distinguishes
an absent proof from a damaged or missing projection row. Changes to canonical
receipt or admission rows invalidate linked manifests rather than silently
reusing projections of the prior contents. Only the backfill and authorized
publication transactions populate the projection.

Migration `0025_native_citation_proofs` needs a live database. It verifies
canonical records before deriving proof rows, under the same source authority
lock as the publisher. Migration failure rolls back the schema and data changes.
For rollout, quiesce native source publication while applying the migration and
switching the Core pin. Old Core binaries do not populate the projection when
publishing. Keep the previous pin available for rollback. If that pin publishes
after rollback, rebuild the projection with publication quiesced before
re-enabling the typed reader.

The parity gate uses the frozen 31-case Elderwyld cohort, starting with Q06 and
Q16, and compares authorization, graph ordering, evidence, and cited bytes.
Qualification compares span-loader and writer-ready timing against the two
retained serial runs without rerunning them. Buddy integration is a pin-only
change and follows successful qualification.
