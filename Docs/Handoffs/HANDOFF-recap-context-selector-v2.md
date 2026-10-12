# HANDOFF — CORE: opt-in recap context selector V2

**Status:** ACTIVE implementation; independent PRIME review and merge pending.
**Topology:** serial Core-first capability, followed by a separately activated
Buddy reader pinned to the accepted Core merge.
**Base:** fetched `main@d8798a5d5d6b46efa3e485e5b493a8fc3d4a94f7`.
**Branch:** `codex/recap-context-selector-v2`.
**Isolated checkout:** `/tmp/core-selector-v2.HGxlV4`.

PRIME assigned implementation of its accepted decision at
`/tmp/recap-selector-v2-contract-decision.json`, SHA-256
`138821ba3b37251dcb0eee0d52d69c0f08befc2c17b5483e31105d0af81fcfd4`.
The private dispatch is `/tmp/HANDOFF-CORE-recap-selector-v2.md`. These files
describe authority; no runtime imports them. Open Core PR inventory was empty
at re-anchor. MIND's private data preparation holds no tracked code lease here.

PRIME's review of implementation head `1c4ef13b621dfb991817142b826ea2a01abb40f9`
held the public V2 marker-search boundary: the original C1S16 has
`## Major Beats:` and `## Next Beats :` before `**Recap**:`. The amended decision
at the same private path is SHA-256
`f2a56ca31252ff9707f8b93c7f8d6a671c29d57954f6bc1e66189cb99eb52504`.
It replaces only that policy clarification; metadata payload fields and Core
implementation/test bytes remain unchanged.

## One capability

Core can explicitly discover and resolve a distinct V2 recap selector derived
from admitted source session metadata. Its canonical H1 and narrow legacy
Session H2/Recap-marker alternatives are metadata policy, not body parsing.
Default V1 IDs/descriptors/preimages remain unchanged. A saved ID reconstructs
its encoded policy even when the caller can discover V2.

## Exact write lease

- `src/dungeonmind/application/world_graph_retrieval.py`
- `tests/unit/test_world_graph_retrieval_service.py`
- `Docs/Contracts/CONTRACT-recap-source-context-v1.md`
- `Docs/Contracts/CONTRACT-recap-source-context-v2.md`
- this handoff

No source body/classification, Graph, persistence/schema, migration, dependency,
provider, retained database, runtime or Buddy code is changed. Source standing,
scope, focus, GM admission, provenance and overflow rules remain the existing
ones. A broader Markdown family or extra path needs steward rebrief.

## Consumer API

V2 index requests use `selector_policy="markdown-session-recap-v2"`; omission
is V1. Resolution enables V2 using `allow_selector_v2=True`, default false.
Known V1 IDs always reconstruct V1; V2 IDs require capability and derive a
different preimage/namespace. Unknown versions and mismatched identity tuples
miss. The public V2 contract specifies the later Buddy byte/ambiguity/paging
obligations without implementing them in Core.

For the legacy form, marker discovery extends from the exact Session H2 until
the next H1, numbered Session H2 or EOF, permitting non-session prelude H2s.
After the unique marker is found, the returned body ends at the next H1/H2 or
EOF. The public contract includes a synthetic exact Major/Next Beats prelude
vector: session heading line 1, marker line 6, body line 7 only; an Afterword H2
ends the body and Session 17's marker cannot substitute for a missing one.
Canonical selection and all duplicate/mixed/wrong-session/fenced/quoted-fake
exclusions remain unchanged. Buddy owns the parser and this vector's tests.

## Focused verification

Owning-service synthetic tests cover a frozen pre-change V1 descriptor/ID,
default/explicit V1 equivalence after V2 discovery, V2 deterministic literals,
saved V1 resolution with V2 capability, unsupported policies/capabilities and
versions, context-versus-evidence identity, scope/GM/revision/openability,
ordering/empty overflow, current source standing and full identity bindings.
Source-body reads are forbidden in the V2 service witness. There is no private
corpus/provider/DB test in this Core slice.

Author verification: 106 owning retrieval-service cases passed (73 existing
cases and 33 new selector/capability/identity cases). Ruff passed both changed
Python paths. Pyright reported zero errors/warnings on the changed runtime
module using the existing dependency interpreter. Diff whitespace checks passed.
An AST source comparison also confirmed the V1 selector class, descriptor class
and `_derive_context_anchor_id` definitions are byte-identical to the base.

Implementation handback records exact head, focused tests and lint/static/diff
evidence in the PR. The implementation author does not independently review or
merge this PR. After independent acceptance and merge, PRIME can activate the
Buddy reader at the exact merge pin; Agent/APP/UI adoption remains separate.

No code merge or synthetic metadata test establishes C1S16 full-recap reading.
The later Buddy reader must prove that using the unchanged original bytes and
an explicitly negotiated V2 Core descriptor in a private read-only witness.
