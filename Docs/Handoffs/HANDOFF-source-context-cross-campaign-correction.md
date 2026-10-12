# Source-context cross-campaign correction

**Status:** implementation PR pending review. **Base:** DungeonMind `main` at `b883034fbb4a8ae2b1da894d7ff7d6ee34dc4491` (Core #113 merge).

## Why this slice exists

Core #113 added a pinned GM recap context index but admitted only `WORLD` and `CAMPAIGN` requests. Current Buddy ordinary World chat already maps to Core `WORLD_CROSS_CAMPAIGN`, so the index rejected the very scope that can see admitted recap provenance from multiple campaigns. This is a request-vocabulary omission, not permission to redefine `WORLD`.

## Exact ruling

- `WORLD` remains world-owned only; campaign-owned recap descriptors do not appear there.
- `CAMPAIGN` remains bound to its requested campaign.
- `WORLD_CROSS_CAMPAIGN` can enumerate only same-World recap artifact/revision pairs actually referenced by admitted provenance in one exact pinned GM projection. It does not scan the source catalog.
- The existing source standing, revision, URI/digest, session, openability, and context-token revalidation gates remain unchanged. Tokens already bind scope mode and therefore differ between campaign and cross-campaign requests.
- No graph/source data, migration, provider, publication, or Buddy runtime change belongs in this slice. S28 publication remains held.

## Proof and follow-on

Synthetic tests show C1 and C2 together under cross-campaign, world-owned-only `WORLD`, exact campaign isolation, wrong-scope and stale-revision misses, absence of catalog-only, foreign-World, and rejected source rows, and source-campaign binding in the context identity.

Read-only native witness on the restored authority database at head `rev:62820bcd7eca116af9d889e128fabf4e`: the candidate Core service returned a complete cross-campaign index of 19 admitted descriptors. S22 was `corpus:eldyrwild:session-22-recap` at source revision/full digest `06c978131f31e6ec85ff6286fe550f07bd2a3c5972c86bf29533079aebbf7083`; S23 was `corpus:eldyrwild:session-23-recap` at revision/full digest `77ba5030b5c89e8888e8a3d900fe3fc07b94313af81a7ad5f888eb663d4c7782`. Both belonged to `longmont-c2`. The connection enforced `default_transaction_read_only=on`, and the World head was unchanged before and after. No body bytes were opened or written.

Independent ARCH review and required CI are merge gates. Buddy's bounded digest-verified source reader and ordinary-chat dogfood are separate follow-on proof; this Core correction alone does not complete the user experience.
