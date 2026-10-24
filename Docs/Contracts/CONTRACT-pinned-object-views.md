# Pinned object read views

`WorldGraphRetrievalService.get_object_views(request, *, object_id, bounds)` returns
frozen `ObjectReadViews(bounded: ObjectLookupResult, complete: CompleteObjectLookupResult)`.
Callers must supply an exact nonblank `revision_pin` and nonblank `object_id`.
Invalid identity is rejected before IO or logical view execution. The synchronous
operation captures its request and bounds, opens one coherent projection context,
and discards that context when it returns or raises. Nothing is cached across calls.

The bounded member equals `get_object` under the supplied bounds; the complete
member equals `get_complete_object` for the same captured request. Product bounds
do not reduce completeness. Source provenance, visibility, exclusions, reviewed
observations, assertion kinds, anchors, locator qualifications and coverage retain
the existing operations' meanings. Both members identify the same snapshot/object.
Either view failing raises the failure without returning a partial pair.

Observability retains the two logical `get_object`/`get_complete_object` terminal
observations and the projection service's existing physical observation. Physical
projection establishment occurs inside the first logical view's projection phase;
the second view's projection phase measures reuse only. A first-view failure emits
its owning error observation and never executes the second view. A second-view
failure retains the truthful first-view observation but returns no pair. Observer
sink failure remains fail-open as in the existing reads.

The existing independent operations remain public and unchanged. Consumers needing
both views must call this API directly; no private-context inspection or fallback
to two independent reads. No persistence, migration, transport schema, source-body
access, deferred session or service-wide cache is introduced.
