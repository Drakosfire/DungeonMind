# DungeonMind — Post-vNext Performance Roadmap

**Status:** BLOCKED for the post-vNext successor — activates after V11 accepts the post-cutover baseline
**Predecessor exit:** `POST_CUTOVER_PERFORMANCE_BASELINE_ACCEPTED` and `VNEXT_ROADMAP_COMPLETE`  
**First phase:** O1 — Hot-path work elimination

This is the finite successor to the vNext migration roadmap. It does not
authorize its post-cutover phases before V11 establishes a semantic and
performance baseline. The separately authorized [current-route compute-efficiency
program](../Plans/PLAN-compute-efficiency-experiments.md) may measure and improve
the serving classic architecture now. Those results do not satisfy V11, activate
O1, or authorize a vNext/storage cutover. Every phase preserves accepted authority, privacy,
historical reconstruction, and semantic digests before claiming performance
credit.

## Phase sequence

```text
O1  redundant-work elimination
O2  resident immutable serving state
O3  serialization / hash / materialization
O4  write amplification
O5  physical storage experiments if evidence still justifies them
O6  production-scale concurrency / operational tuning
O7  performance lock-in
```

## Entry rule

The successor Steward activates O1 only after V11 records both predecessor exit
tokens and publishes the measured post-cutover baseline. O1 begins with work
elimination; it does not presume a storage redesign.

## Governing rule

Each optimization must identify the measured bottleneck, preserve semantic
results and privacy, quantify work removed, and retain a regression lock. Later
phases may not be pulled forward merely because their mechanisms are attractive.
