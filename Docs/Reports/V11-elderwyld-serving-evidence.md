# V11 Elderwyld serving evidence

**Disposition:** Native serving switch verified. V11 roadmap acceptance remains open.

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
| Live port 5202, current head and two historical pins | Warm neighborhood | 108–114 |
| Live port 5202, same pin sequence | Opens and returns during cache turnover | 356–990 |
| Live port 5202, same pin sequence | Exact citation reopening | 84–96 |

The retained classic reference is 540 ms on the comparable fixture. The direct
live observation and live pin sequence use the real Elderwyld authority and are
a separate workload. A reproducible live cold-process distribution and the
first request after a new live publication remain open. The published-revision
measurement above used a disposable fixture.

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

## Remaining closeout

Confirm the remaining V10 public/current authority boundary and record the
disposition of retained classic compatibility. Complete or explicitly dispose
of the remaining live performance cells before recording
`POST_CUTOVER_PERFORMANCE_BASELINE_ACCEPTED` and `VNEXT_ROADMAP_COMPLETE`.
The measured successor investigation is the cost of proof and parsed rebuilds
when alternating among live pins, plus first access after a new publication.
The successor roadmap remains gated on the V11 acceptance record.
