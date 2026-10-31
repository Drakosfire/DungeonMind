# Native entity listing

`EntityReadService.list_entities(context)` enumerates the finite native revision
already pinned by a `KnowledgeReadContext`. This is the unseeded browse entry point;
search, selected entity inspection, neighborhood traversal and evidence opening
retain their existing owners.

Core evaluates all revision-local assertions once through the existing candidate
admission boundary. The result contains the sorted, deduplicated entities named
as subjects or entity-ref endpoints of admitted assertions, plus those admitted
assertion IDs. An incoming-only endpoint can therefore appear without admitted
subject facts. An isolated known identity, hidden fact, denied relationship,
source record or alias does not independently establish catalogue membership.
Missing admitted assertions/endpoints fail integrity.

The immutable `EntityListResult` reuses the parsed revision identity and entity
records, commits to the exact request, and carries existing entity completeness.
Its deterministic digest covers the exact revision/domain/profile/request and
admitted output. It does not include exclusion IDs/reasons or admission work
counters. Detailed facts and qualifications are read through `get_entity` or
`get_complete_entity` under that same context; evidence/source inspection remains
separate. Endpoint presence never authorizes its other facts or aliases.

There is no search string, ranker, result cap, pagination cursor, source-body IO,
repository selection, writer, fallback or additional provenance decision here.
`complete` means every assertion in this finite revision was evaluated under the
context's existing scope, audience, standing, source and domain rules. Empty is a
valid complete result. Neither status proves corpus completeness, ingestion success,
identity nonexistence or equivalence to a different Graph authority.

The intended consumer is Buddy's native Build/Explorer browse boundary. This Core
capability alone does not switch Buddy's classic readers/writers, migrate retained
references, publish a World or restore the full corpus. Those require explicit,
separately verified product adoption. Retained old revision IDs must never be
reinterpreted as native IDs merely because their text formats match.
