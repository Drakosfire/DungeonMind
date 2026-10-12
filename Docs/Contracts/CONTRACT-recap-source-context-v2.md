# Recap source context selector V2

**Status:** additive Core metadata capability; Buddy section decoding is a
separate consumer implementation. This contract creates no source or Graph data.

## Explicit discovery and capability

`SourceContextIndexRequest(projection, selector_policy="markdown-session-recap-v2")`
requests V2 descriptors. Omission or explicit `markdown-session-recap-v1` returns
the existing V1 descriptors and identifiers. Unknown policy values are rejected.
One index contains only its requested descriptor version; ordering, provenance,
GM scope, exact revision pins, openability and empty-overflow behavior are shared
with V1. Core never reads source bodies or chooses a physical Markdown format.

`resolve_source_context(projection, context_anchor_id=id, allow_selector_v2=True)`
enables V2 resolution. The flag is a strict boolean, defaulting to `False`.
Resolution reconstructs the ID's own namespace and policy:

- A `dm-context-anchor:v1:` ID resolves through V1 whether or not V2 is enabled.
- A `dm-context-anchor:v2:` ID resolves through V2 only with explicit capability.
- A V2 ID without capability, an unknown version or a forged ID returns a miss.

New discovery preference cannot rebind a saved V1 ID to V2. Changing only an ID's
version prefix is insufficient: the two versions have distinct hash preimages.
Existing readers are never handed V2 by upgrading Core alone.

## Authorized metadata

`RecapContextSectionSelectorV2` has schema
`dm_recap_context_section_selector_v2`, kind `recap_section` and policy
`markdown-session-recap-v2`. It contains these identity fields, derived only from
the admitted source artifact's canonical `session-N` metadata:

- `expected_session_id`: `session-N`, with positive canonical decimal N.
- `canonical_heading`: exactly `# Session N Recap`.
- `legacy_session_heading`: exactly `## Session N:`.
- `legacy_recap_marker`: exactly `**Recap**:`.

The schema, kind, policy and all four fields participate in selector identity.
Alternate punctuation, session values, markers and policies are rejected.
These are authorized alternatives, not an observation that either exists in
the source. Core supplies no selected form, content or line range.

`RecapSourceContextV2` has schema `dm_recap_source_context_v2` and carries the
selector plus the same exact World, source campaign, Graph revision, artifact,
source revision, source URI and full byte SHA-256 metadata as V1. Its ID uses
`dm-context-anchor:v2:` and `dm_context_anchor_v2`. The V2 preimage binds World,
projection campaign/scope/focus/admissibility/revision, artifact/source revision,
source campaign, URI, full digest and selector identity. V1's preimage is retained
unchanged. Re-resolution reprojects the pinned scope and revalidates source
standing; an opaque ID is a lookup identity, never a credential.

## Product reader obligations

Before every page, the product re-resolves the ID with Core under the exact
projection, checks URI containment and source-opening policy, verifies the full
original byte digest, then decodes UTF-8. It must find exactly one permitted
section, ignoring fenced code and quoted/indented fake structural lines.

For the canonical form, require one literal `# Session N Recap` H1. Return the
section after it through the next H1 or EOF, with the same section bytes/ranges
as a valid V1 read.

For the legacy form, require one literal `## Session N:` H2. Search for exactly
one standalone `**Recap**:` marker after it, up to the next H1, numbered Session
H2 (`## Session <digits>:`), or EOF. Non-session H2 prelude headings do not end
this marker-search envelope. Fenced/quoted structural lines remain excluded.

The returned body starts after the marker and ends at the next H1/H2 or EOF.
This body boundary differs from the marker-search envelope: pre-recap metadata
and its headings are excluded, while subordinate H3+ recap content is retained.
Report both session-heading and marker lines and the actual body range.

The following synthetic vector pins the exact prelude form observed in C1S16;
its prose is synthetic, not a copy of the original body:

```markdown
## Session 16:
## Major Beats:
Synthetic prelude A.
## Next Beats :
Synthetic prelude B.
**Recap**:
Synthetic recap body.
## Afterword
Excluded afterword.
## Session 17:
**Recap**:
Other session body.
```

For `session-16`, the session heading is line 1 and the marker is line 6.
Return only line 7 (`Synthetic recap body.\n`). The non-session H2 headings
before the marker do not truncate its search; the H2 after the marker stops the
returned body. Removing the Session 16 marker must not borrow Session 17's
marker. A second marker within Session 16's search envelope is ambiguous.

A matching canonical and legacy heading in one revision, duplicate session
headings/markers, missing marker, wrong session or invalid bounds fails closed.
Do not choose a preferred match, infer a filename, normalize a new body, read a
neighboring session or fall back to the whole document.

V2 pages are bounded under the product's existing character caps. A V2 cursor
binds the V2 context ID, source and selected-section digests, observed form and
boundaries, and character offset. Every page revalidates the same bytes/section
and contiguous offsets; truncation is explicit. V1 cursors and decoding remain
unchanged, including saved V1 IDs opened by a V2-capable reader. Cursor versions
cannot cross identities or sections. Core does not mint product cursors.

## Consumer sequence

The intended Buddy reader has explicit V2 index/read routes and versioned
request/result models. V2 discovery requests V2; historical reads choose the
ID's version and preserve the matching V1/V2 descriptor and continuation policy.
Existing routes and Agent/APP/UI consumers continue using V1 until separately
adopted; V2 must not be put into their V1-only receipt fields.

Both versions are related recap context. Neither supplies evidence/support
identity, `source_read_id`, claim `source_opened` or quotation proof. Existing
evidence-anchor reads and source classifications remain unchanged.
