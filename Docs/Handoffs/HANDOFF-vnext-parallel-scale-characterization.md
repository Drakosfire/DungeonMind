# HANDOFF — vNext parallel scale characterization

**Status:** DESIGN CHECKPOINT — not an implementation lease  
**Owner:** DungeonMind  
**Current main anchor:** `8111557b2f8ac797cf9d4f7de54e559d57f22c1d` (PR #88)  
**Current production-code anchor:** `7c69e447f6d4acc963ac09c6fb9cb48cc1c5b9cc` (accepted native source admission, PR #85)  
**Authority:** `Docs/Roadmaps/ROADMAP.md`, §“Parallel measurement lane”; `Docs/Architecture/ARCHITECTURE-vnext-read-path-and-performance.md`; `Docs/Architecture/AUTHORITY.md`  
**One-line mission:** establish a reproducible, semantically identified scale/cost baseline for the accepted current runtime, to inform V8 comparison and V11 post-cutover measurement, without changing runtime behavior or delaying V0.

## 1. Decision and question

The current vNext roadmap explicitly retains larger World-like / Rules-like characterization as a parallel evidence project, not a front-door blocker. This handoff is a refreshed current-authority lane. It does **not** revive the historical K0.3 implementation lease or adopt its stale runtime anchor and K1.1 sequencing.

Primary question:

> At representative scale, what work and observed cost does the accepted current DungeonMind implementation incur for the roadmap’s important read, provenance, serialization, and tiny-publication operations?

A measured regression or a resource limit is valid evidence. A faster result obtained by changing production behavior is not.

## 2. Anchor and evidence rules

The implementation must re-anchor to the latest accepted main and separately identify the exact production source tree measured. The refs above are dispatch context, not permission to benchmark a later or dirty runtime silently. Before measurement:

1. Verify that the production-code tree at the selected runtime anchor matches the accepted runtime intended by the roadmap.
2. Verify that no intervening `src/`, migration, dependency, lockfile, or runtime-configuration change alters the measured system. If one does, either rebase the measurement to that accepted tree and record it, or stop for a revised review.
3. Record both the roadmap/main ref and runtime-code ref in every output. A report must never imply that a docs-only later merge changed the measured runtime.
4. Use a clean isolated checkout. Do not reuse or modify the dirty historical branch `kernel/k0-performance-baseline-expansion`; it contains uncommitted benchmark work and unrelated vNext contract files. No cherry-pick or artifact reuse without a separate exact-path and provenance audit.
5. The old K0.3 handoff cites K0.2 oracle script/report paths that are not present at the current main anchor. Do not claim those commands ran or rely on those missing files. If a current checked-in semantic oracle is found during activation, record its exact path/ref and use it; otherwise the benchmark’s deterministic fixture, operation, and semantic-result digests form this lane’s baseline identity. Missing historical artifacts are not reconstructed from chat.

## 3. Workload and operation matrix

Use deterministic synthetic fixtures, not production/user data. Both workload labels describe shape only and execute through the current supported DungeonMind APIs and semantics:

- **World-like:** moderate-degree graph, mixed ownership/visibility, labels, aliases, assertions, evidence and source-revision links, bounded traversal, and deterministic search terms.
- **Rules-like:** many small records, high evidence density, dependency/reference/exception-style edges and repeated search terms. This is not a Rules domain, ontology, contract, or proof that current World semantics model rules correctly.

Required scale ladder:

```
100, 1k, 10k, 50k, 100k
```

Measure separately where the accepted public seams permit:

```
cold parse / load
full projection
exact and complete entity
neighborhood (depth 1 and 2)
evidence and source-anchor resolution
deterministic search
source/provenance snapshot load
large-parent tiny-delta governed publication
canonical serialization and hashing
peak memory / allocation observations
repository/query/work counts available without runtime instrumentation
```

Every shape × size × operation must have an explicit disposition: measured, not applicable (with semantic reason), not measured (with reason), or resource limited (with concrete host/runtime evidence). No silent omissions and no size-dependent reduction of result bounds. Time and memory are observations, not deterministic identity.

## 4. Artifact contract

Deliver a checked-in machine-readable artifact and human report. Proposed names:

```
benchmarks/vnext_scale_characterization.py
benchmarks/vnext_scale_fixtures.py
benchmarks/vnext_scale_validate.py
Docs/Reports/VNEXT-scale-characterization-v1.json
Docs/Reports/REPORT-vnext-scale-characterization.md
tests/unit/test_vnext_scale_characterization.py
tests/integration/test_vnext_scale_characterization_postgres.py  # only if approved isolated test service is available
```

The exact layout may change if ownership stays clear. The artifact must include:

- schema/version and exact DungeonMind runtime SHA;
- generator version, deterministic seed(s), workload parameters, fixture/input digests;
- operation and result-contract identity, deterministic semantic result digests;
- environment identity: Python, OS/architecture, relevant adapter/database version and command;
- raw timing samples/statistics, memory/allocation measures, and work/query counts when available;
- a row/disposition for every required matrix cell, with resource limits and failure reasons;
- explicit separation of deterministic identity from machine-dependent observations.

Do not produce a single aggregate performance score or universal latency pass threshold. The report explains environment comparability and limits; benchmark output is not a promise of future service-level performance.

## 5. Scope lease after design acceptance

Allowed:

- benchmark, synthetic fixture, validator, tests, and report/artifact files;
- benchmark-only repair of a demonstrated harness/API-construction drift, using real current dependencies and keeping setup outside timed regions;
- isolated test-only PostgreSQL measurement if an existing approved integration service can be used with a uniquely named disposable database, exact target validation, and guaranteed cleanup.

Forbidden:

- changes under production `src/`, migrations, public contracts, dependencies, lockfiles, or runtime configuration;
- behavior/performance optimization, instrumentation added to production, storage redesign, index additions, or altered result bounds;
- live, user, demo, or persistent PostgreSQL databases; production World data; paid/provider calls;
- invented RulesKnowledge or vNext contract semantics;
- treating benchmark evidence as V0 completion, V8 acceptance, V11 acceptance, or permission to dispatch V7/cutover.

If an operation cannot be measured at the benchmark boundary without production code changes, record the limitation and stop/rebrief rather than widening the lease. If no safe isolated PostgreSQL service is available, mark PG-only cells not measured with the reason; do not provision or target an unapproved external database.

## 6. Verification and acceptance

The implementation PR must provide exact commands and results for:

1. deterministic fixture/artifact regeneration twice, with byte-identical identity fields and result digests;
2. validator rejection of missing/duplicate cells, malformed digests, silent omissions, and invalid dispositions;
3. focused unit tests and the full relevant core test suite;
4. the normal benchmark-smoke command, if its current failure lies within the benchmark-only repair lease;
5. the current checked-in semantic tests/oracle actually available at the selected runtime anchor, named by exact path and ref;
6. PG rows only when the authorized disposable integration target exists, with zero persistent residue;
7. `git diff --check` and an explicit proof that production paths, migrations, dependency manifests, and runtime config are unchanged.

Acceptance means a trustworthy and reproducible observational baseline, not that current performance meets future targets. PRIME independently reviews the exact implementation head before any merge. The design handoff itself also requires PRIME review before merge. Stewardship and roadmap state must be re-anchored after each accepted roadmap merge before a successor implementation PR.

## 7. Stop conditions and handback

Stop and return to Steward/PRIME if:

- the accepted runtime anchor or authority tree is ambiguous or changed;
- a required operation cannot be represented faithfully through the current API;
- benchmark setup would touch a live/persistent database or require new production instrumentation;
- fixture semantics, visibility, provenance, or result bounds are not deterministic;
- a resource limit prevents the roadmap matrix from being represented truthfully;
- the work would require changing contracts, dependencies, runtime, or roadmap sequencing;
- the dirty legacy K0.3 checkout is the only available source of an artifact or implementation assumption.

This parallel lane does not resolve the open DEMO product decision, #785’s Buddy-owned unresolved-generation recovery, or V7’s missing legacy World/export authority. It does not change their gates.