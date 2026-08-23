# Baseline: direct World Graph reads (R.2a)

**Status:** characterization record for the landed R.1/R.2 direct read seam.
**This baseline is not an SLO, a performance budget, or a merge threshold.**
It records how the native read path behaved on one machine at one commit so
that future changes can be compared against something stable. CI runs only an
informational smoke benchmark (no absolute gates).

- **Benchmark commit:** `b188758e601466845f46f45fb4573f01a2db8f75`
- **Lane:** `r2a` (handoff:
  `Docs/Handoffs/HANDOFF-cutover-world-graph-read-observability-benchmark.md`)
- **Artifacts:** `benchmarks/baselines/world_graph_reads-r2a-latency.json`,
  `benchmarks/baselines/world_graph_reads-r2a-memory.json` (pyperf suites,
  34 cases each, per-case semantic digests included)

## Corpus

Deterministic synthetic `dm_union_graph_v6` graphs under the bundled D&D v3
semantic profile (`dungeonmind.dnd5e@dnd5e-profile-v3`), generator seed
`20260822`. No database, Buddy checkout, network, or private campaign content.
Scope split 20% world-owned / 40% campaign-alpha / 40% campaign-beta; anchor-
capable locator evidence on every 7th object / 5th relationship evidence row.
Reference size ladder: 100 / 1k / 5k / 10k objects. Eight operation cases per
size (projection head + pinned, lookup, search, depth-1/2 neighborhood,
evidence, anchor resolution) plus PLAYER-scope campaign projection/search at
1k. `resolve_source_anchor` is exercised with a deliberately late anchor so
whole-projection/whole-anchor rederivation cost is measured honestly.

## Reproduce

```bash
uv sync --locked
uv run python benchmarks/world_graph_reads.py -o /tmp/latency.json                       # full latency ladder
uv run python benchmarks/world_graph_reads.py --tracemalloc -o /tmp/memory.json          # full memory ladder
uv run python benchmarks/world_graph_reads.py --sizes 100 --fast -o /tmp/smoke.json      # quick smoke
```

Notes on sampling:

- Latency was recorded on an otherwise quiet machine with pyperf defaults.
- The traced-memory metric is deterministic for this harness (observed ±0
  bytes std dev, identical across independent runs), so the 5k/10k memory
  lanes were sampled at reduced pyperf process counts (`--processes 3` / `2`)
  and merged from parallel lanes; every case was cross-validated against the
  lane logs and per-case digests match the latency baseline exactly.
- **Do not compare timing values inside the memory artifact against the
  latency baseline** — they are inflated by tracemalloc overhead.

## Environment (recorded in artifact metadata)

- Machine: `drakosfire-code-laptop`, 12th Gen Intel Core i3-1215U (8 CPUs),
  powersave governor, full ASLR
- OS: Linux 7.0.0-28-generic (glibc 2.39); Python: CPython 3.13.1
- Result bounds: harness defaults (bounded result sizes while the graph grows)

## Results (median latency / peak traced memory)

| Case | 100 | 1k | 5k | 10k |
|---|---|---|---|---|
| project_head | 46ms / 3.2 MiB | 516ms / 32.4 MiB | 3.16s / 160 MiB | 6.74s / 318 MiB |
| project_pinned | 54ms / 3.2 MiB | 519ms / 32.4 MiB | 3.15s / 160 MiB | 6.66s / 318 MiB |
| get_object | 51ms / 3.2 MiB | 516ms / 32.4 MiB | 3.13s / 160 MiB | 6.97s / 318 MiB |
| search | 53ms / 3.3 MiB | 802ms / 32.7 MiB | 4.53s / 160 MiB | 9.95s / 318 MiB |
| neighborhood_d1 | 49ms / 3.2 MiB | 540ms / 32.4 MiB | 3.25s / 160 MiB | 7.07s / 318 MiB |
| neighborhood_d2 | 50ms / 3.2 MiB | 539ms / 32.4 MiB | 3.18s / 160 MiB | 7.27s / 318 MiB |
| get_evidence | 47ms / 3.2 MiB | 523ms / 32.4 MiB | 3.19s / 160 MiB | 6.90s / 318 MiB |
| resolve_source_anchor | 66ms / 3.6 MiB | 702ms / 36.7 MiB | 4.44s / 184 MiB | 9.51s / 368 MiB |
| project_player_campaign | — | 347ms / 32.4 MiB | — | — |
| search_player_campaign | — | 470ms / 32.7 MiB | — | — |

pyperf emitted "result may be unstable" warnings on some large-size cases
(few samples at multi-second durations); medians are reported, and the
per-run values in the artifacts should be consulted before reading anything
finer than two significant figures into these numbers.

## Interpretation (characterization, not optimization)

1. **Full projection is the structural cost floor of every read.** Each
   retrieval operation composes the R.1 v2 projection exactly once per call
   with no cross-call reuse. At 10k, the raw projection median (6.74s) is
   ~97% of the independently measured `get_object` median (6.97s), strongly
   indicating projection as the dominant cost floor for single-object reads.
2. **Search and anchor resolution add significant graph-size-dependent
   secondary costs** on top of projection — over this measured ladder the
   deltas grow approximately in proportion to graph size (search: +7ms →
   +286ms → +1.37s → +3.2s; anchor derivation: +20ms → +186ms → +1.28s →
   +2.8s across 100/1k/5k/10k). Four points per case do not establish a
   complexity class; they do establish that these phases scale with the
   graph, not with the bounded result.
3. **Peak traced memory is linear in admitted graph size** at ~32 KiB per
   admitted object (3.2 → 32.4 → 160 → 318 MiB), with anchor resolution
   carrying an additional ~50 MiB at 10k for supporter rederivation.
4. **PLAYER-campaign reads measured lower than GM cross-campaign reads at
   1k** (347ms vs 516ms projection) — but the two cases vary scope mode
   (`campaign` vs `world_cross_campaign`) *and* admissibility (`player` vs
   `gm`) together, so this ladder cannot attribute the difference to either
   axis. Isolating the admissibility effect would require a same-scope pair
   varying only admissibility; that is a successor experiment, not a finding
   of this baseline.

## What this baseline is for

- A named parity/performance witness shape for the R.3 cutover: compare
  Buddy-hydrated reads against these direct-DungeonMind numbers.
- A regression reference for future read-path changes: rerun the same
  commands on the same machine class and compare per-case medians and
  digests (digests must match exactly; semantic drift is a correctness
  failure, not benchmark noise).
- Input to eventual SLO definition — SLOs are a successor decision, and
  this document deliberately does not set them.
