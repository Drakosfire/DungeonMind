# AGENTS.md — Operating agreements for agentic work in this repo

Agent-facing companion to `CONTRIBUTING.md`. The toolchain and engineering
rules live there; this file records how an agent should *behave* while
executing them.

## Long-running operations: estimate before you start

Before launching any operation expected to exceed ~10 minutes of wall time —
benchmark suites, full test matrices, database migrations, large fixture or
corpus generation, multi-size characterization runs:

1. **State the expected duration up front.** Estimate from a checked-in
   baseline, a small probe, or a prior run, and say the number before
   starting (e.g. "full ladder ≈ 2 hours on this machine") — not after.
2. **Offer the cheaper path when one exists.** Reduced sampling, a smaller
   size ladder, subset filters — name what each trades away and let the
   caller choose.
3. **Report progress against the estimate.** Give elapsed/remaining at
   natural checkpoints; if the operation will materially exceed the
   estimate, say so early rather than at the end.
4. **Prefer resumable, incremental execution.** Write partial artifacts as
   the run proceeds so an interrupted run is not a total loss.

Rationale: long operations are sometimes necessary, but they must never be a
surprise. An operation that could have been recognized as long-running and
wasn't flagged is a process failure, even when its result is correct.
