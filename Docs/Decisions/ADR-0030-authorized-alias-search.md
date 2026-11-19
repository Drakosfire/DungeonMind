# ADR-0030 — indexed authorized alias search

Status: accepted for implementation by MIND under explicit operator lane authority;
implementation acceptance requires this slice's independent review and merge.
Owning bounded contract: HANDOFF-MIND-authorized-alias-search.md.

Alias candidate discovery is structural; only existing standing/evidence/source
admission can produce an alias witness. Add a separate public alias-search read,
leaving SearchReadService, frozen contracts, alias scope and source writes intact.
Expose authorized aliases and exact generic match witnesses. Compute authorized
ambiguity before truncation; partial results cannot claim uniqueness. Excluded
aliases cannot suppress otherwise-admitted results or affect public digest/rank.
Buddy owns labels, scoped entity presence and presentation ranking.

Build separately versioned immutable character-gram postings only on alias search.
An explicitly injected bounded cache keys complete revision/parse-meaning identity
and stores structural IDs/postings only. It never stores whole parsed revisions,
read contexts, sources, admission or provenance. Every read reauthorizes against
its own coherent context. Common queries may intrinsically match many aliases;
limits apply after authorization, with explicit partial status on result truncation.

Keep ParsedKnowledgeRevision, builder, parsed-format/compatibility identity and
verified primary source-wire artifacts unchanged. No ordinary or artifact decode
constructs the new index. This avoids invalidating accepted artifacts or adding
alias-index work to cold neighborhood preparation. First alias search still pays
index build cost; cache reuse, retention and invalidation require owning proofs.

The matching policy is casefolded exact/ASCII-boundary phrase plus ASCII token
plural tolerance, with Unicode/punctuation phrase candidate coverage. It has no
product/domain vocabulary or numeric Buddy score weights. Complete native assertion
and alias streams can be composed before a consumer cap; this does not itself
prove classic label matching or ranking equivalence. No activation of native
SubjectSearch/defaults, post-vNext performance phases or deployment follows here.
