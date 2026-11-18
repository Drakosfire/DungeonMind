# Remove per-value JSON validator closure cycles

Status: ACTIVE compute slice. Owner: Elderwyld pre-cutover performance lane.
Base: accepted #219 merge371930d307be0dbaf946df06a7438b23ee3dd521.

Outcome: reuse a static recursive JSON checker rather than allocate a self-cycling
recursive closure per value. Existing `_json_value` entry point, validation order,
accepted/rejected values, original-value identity, errors, frozen schemas and
contract digests must stay unchanged. No new wire fields/coercions or weaker
validation. No production GC configuration changes.

Evidence: three staged native SQL candidate cold reads at verificationcb779c1
measured546/547/560ms; full collections consumed89–99ms each. The shared JSON
validator defines a recursive local function referencing its own closure cell.
An isolated process observed1000 such callable cycles after1000 scalar checks.
The frozen baseline is retained and must not be rerun.

Scope: contracts/vnext/common.py private recursion helper, owning value/schema/
allocation regressions and this handoff. Settle accepted #219 bookkeeping in the
first control-plane commit. Public model/validator signatures and bundle artifacts
stay fixed. This slice does not own hash, PostgreSQL, Buddy, admission or cutover.

Serial compute parent is accepted #219. After review/CI, merge this PR, then
rebase storage #218 onto accepted compute main and verify the actual SQL route
and write costs. A local verification branch may combine pinned heads before
acceptance. #218 is code-reviewed/CI-green but its performance goal remains open.

Required proof: exhaustive representative JSON values, scalar representation,
nested finite/nonfinite values and invalid types/keys, return identity, exact
validation errors and frozen schema/bundle equality. Keep a regression preventing
per-value cyclic callables. Compare real primary-model validation and the complete
native parsed result. Measure the combined current candidate, including cold/warm,
GC and generation costs, with ordered DTO and exact citation parity. Repeated
candidate results remain separate from current-deployment/V8 acceptance.

Reuse the existing task-owned Projects checkout/environment. Scratch diagnostic
json-validator-cycle-preflight.json and the existing local verification branch
remain owned by this performance lane for review/integration. Record subsequent
paths/refs; retain for delivery and remove only under explicit cleanup scope after
active-process/mount/dirty-data/unique-commit checks. No removals authorized here.
