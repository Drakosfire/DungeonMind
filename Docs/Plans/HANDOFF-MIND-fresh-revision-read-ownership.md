# MIND — fresh PostgreSQL revision read ownership

ACTIVE by operator request to focus on MIND retrieval performance. PRIME implements solo; independent ARCHITECTURE review before merge. Base d83689cda92691758bdb132fb5ffcd170abb86df; branch codex/mind-read-reconstruction; non-serving checkout /tmp/prime-mirathorn-core-accepted. No open MIND PRs at activation. Serial bounded slice.

One capability: avoid deep-copying a newly reconstructed, fully verified graph revision a second time at the PostgreSQL adapter return boundary. Driver rows are fresh on each query; returned records are not cached or shared between callers. Preserve all strict model, fingerprint, extracted-column and graph-content hash checks. No schema, public API, admission, retrieval ranking/default, provenance, mutation or model change.

Write lease: this handoff; src/dungeonmind/infrastructure/postgres/graph.py; tests/integration/test_postgres_graph.py. Private retained-source benchmarks outside Git. No dependencies, migrations or serving rollout.

Evidence motivating slice: one read-only Council seed's discovery/selection/anchor resolution performs roughly114 stored revision reconstructions. About2.02s of low-overhead timed4.20s execution lies in reconstruction; cProfile identifies the final model_copy(deep=True) as most reconstruction CPU. Repeated ancestry/publication walks remain a separate follow-on; this slice does not claim to eliminate them.

Verification: actual PostgreSQL fresh-read nested mutation isolation and existing integrity/failure regressions on a disposable database only; no retained DB writes. Compare real read-only source acquisition before/after with exact action/unit/source hashes and qualifications, no provider calls. Record latency, repeated work and limits. Independent review, exact head, merge, consumer pin/adoption separately. Runtime changes remain behind Buddy-owned authority.
