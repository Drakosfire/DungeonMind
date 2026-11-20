# V11 Elderwyld serving evidence

**Disposition on merge:** `POST_CUTOVER_PERFORMANCE_BASELINE_ACCEPTED` and
`VNEXT_ROADMAP_COMPLETE` for the accepted fresh-native Elderwyld scope.

On 2026-11-20, the local Buddy UI on port 5202 switched to Buddy
`cf89e86624231a5e373d0afddc4d1be48e2af5de` with installed Core
`046791d09f7c0f7d3b348578763f9c87c7f1ecf1`. The managed World and native space
are both `elderwyld`, following the [fresh-native scope](../Handoffs/HANDOFF-v7-elderwyld-fresh-native-scope.md).
The exact native head at activation and the serving read check was
`rev:5293c1b237a0064bd16fffd080bfa6b1`. Core was on
`0023_native_source_publications`. Buddy application state advanced to
`20261120_0170` with hosted World creation disabled.

The release includes [Core #260](https://github.com/Drakosfire/DungeonMind/pull/260)
and [Buddy #4273](https://github.com/Drakosfire/DungeonMindBuddy/pull/4273).
The direct read path consumes the primary rows after exact source verification,
releases mutable rows before index construction, and opens a fresh source view.
The [V8 acceptance artifact](../Handoffs/dm_vnext_contract_acceptance_v1.json)
retains the joint fixture and scale disposition. The classic reference was reused.

## Observed performance

| Boundary | Condition | Milliseconds |
| --- | --- | ---: |
| Comparable 10k fixture, installed release, three fresh HTTP workers | First neighborhood | 401–403 |
| Same fixture | Warm neighborhood | 73–82 |
| Same fixture | After parsed-cache eviction | 349–354 |
| Same fixture | First access to a newly published revision | 674–688 |
| Same fixture | Return to prior pinned revision | 76 |
| Live loopback API at activation | First timed current-pin neighborhood, after startup | 631 |
| Three fresh release workers against read-only live authority | First current-pin neighborhood | 621–652 |
| Same fresh workers | Warm current-pin neighborhood | 151–156 |
| Live port 5202, current head and two historical pins | Warm neighborhood | 108–114 |
| Live port 5202, same pin sequence | Opens and returns during cache turnover | 356–990 |
| Live port 5202, same pin sequence | Exact citation reopening | 84–96 |

The retained classic reference is 540 ms on the comparable fixture. The direct
live observation and live pin sequence use the real Elderwyld authority and are
a separate workload. The fresh-worker check used the same release and live authority on separate
loopback HTTP ports while the serving proxy stayed on 5202. Each worker matched
the live neighborhood and citation hashes. The published-revision measurement used a disposable fixture with the exact
locked release. No synthetic publication was added to live Elderwyld.

At observation, the live API had **856 MiB RSS** and a **918 MiB** process
high-water mark. Installed fixture workers ended at **636 MiB RSS**. These
are process observations, limited to the recorded workloads and sampling times.

## Semantic and recovery evidence

- The current pinned neighborhood and cited bytes matched across the previous
  API, candidate, schema-compatible fallback, and activated UI proxy.
- The live sequence used three authoritative pins. Each pin returned identical
  neighborhood and citation bytes across repeated reads, and the unpinned route
  returned the same current head. Anonymous requests were rejected.
- Before migration, the retained restore was advanced to `0169` and compared
  with live application state. All 66 table contents, sequences, large objects,
  and extensions matched. The only two schema differences matched the verified
  equivalent check-constraint renderings. The comparison was repeated at the
  switch boundary. The migration preserved the previously existing data.
- The post-migration fallback is Buddy `47c3b616652b291fb2350adce826ea911d825093`
  with Core `1331f24bd7976a96619dfd6e6565750827e680e0`. The older `0169`
  serving build rejects `0170`. On the isolated `0170` restore, the exact
  release, fallback, and restarted release replayed the same durable receipt
  and reopened the same citation. Revision, head-event and receipt counts
  remained unchanged. The same switch passed through the rebuilt UI proxy.
- The 569-test Buddy cohort covered source withdrawal, visibility, exact source
  and hosted access. The isolated HTTP fixture verified ordered results and
  citation-byte parity on the final installed dependency.

## Current and historical authority boundary

The Buddy shared neighborhood, search, object, evidence and anchor routes
dispatch to native readers. The exact serving build passed 28 targeted
regressions for retired projections, graph-attached live query and fresh
classic Agent turns. These tests trap legacy storage or provider dispatch and
require the typed retirement response.

The Agent retains a classic resolver for frozen historical Graph capabilities.
Fresh Plan, governed Build and Play select the native query resolver. A missing
native resolver on those fresh paths is an error. Historical recap projection
requires an exact extraction run and adopted historical source. These
compatibility readers and their stored contracts must remain readable.

Core's service exposes explicit retirement boundaries for fresh classic Mind
Turn execution and classic campaign ingest context. Historical completed-turn
and publication receipt lookup remain available. The separate fictional-time
shadow host requires an authorized revision pin and serves the shadow contract.

The native application and contract facades export none of
`WorldGraphRevision`, `WorldGraphHead`, `WorldGraphProjectionRequestV2`, or
`ScopeModeV2`. Importing both facades in a fresh process loaded none of the
classic graph, projection, retrieval, or compatibility modules. Explicit
legacy leaf imports remain for historical codecs, frozen Buddy receipts,
and legacy tooling. The Core historical boundary, codec parity, and retired
campaign entry-point cohort passed 68 tests. Existing historical storage and
migrations remain in place.

## Successor handoff

The comparable first read and eviction improved against the accepted V8
measurements. First access to a freshly published fixture revision increased
from **505–514 ms** in V8 to **674–688 ms** on this release. Live alternating
pin reads still reach **990 ms**. Investigate proof and parsed-index rebuild
work first, including release of retired revision data. Preserve exact
source verification, visibility, citation bytes and historical reconstruction.

The V8 50k full-input primary JSONB insertion limit, unattempted 100k rung,
and unmatched Rules comparison carry forward as evidence debt. This baseline
covers the accepted Elderwyld release and its comparable fixture. It does not
establish a universal latency or capacity bound. Follow the
[post-vNext performance roadmap](../Roadmaps/ROADMAP-post-vnext-performance.md)
for any subsequent implementation.
