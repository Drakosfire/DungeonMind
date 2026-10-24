# Selected object read session

`WorldGraphRetrievalService.object_read_session(request, *, object_ids)` is a
synchronous context manager. Its facade exposes `get_object_views(*, object_id,
bounds)` with the existing bounded/complete result semantics. Exact nonblank pin
and a distinct nonempty tuple of nonblank object IDs are required before IO.
Entering an unused lifetime performs no reads. Unknown targets fail before IO.

The first call captures a coherent projection; the first complete selected-object
read acquires verified publication ancestry. Both inputs are reused only within
this session. Selection, corrections/withdrawal, visibility, anchors and coverage
remain per object. Product bounds never reduce complete truth. Stable-authority
results equal independent public reads; later mutable authority/head/input changes
do not retarget the captured computation. The next session acquires fresh inputs.

Returned nested models are copied per logical result so caller mutation cannot
change retained context or later output. Copy work occurs before terminal owning
observations and is included in operation totals (result assembly may remain
outside named phases). First establishment/history work remains in actual logical
projection/selection phases; later calls measure reuse. Observer sink failures
remain fail-open; read authority failures remain fail-closed.

Any failed read poisons the facade. Further calls refuse without IO. Exit clears
request/context/history/service references, including exceptional exit; retained
facades refuse calls. Existing single-object `get_object_views` uses one such
session. No repository/service cache, provider/turn lifetime, body access, durable
state or migration is introduced. Product owners must close before source
acquisition, Rules work or provider authorization, and retain broker admission for
each requested object. This native API does not authorize speculative prefetch.
