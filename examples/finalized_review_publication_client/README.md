# Finalized-review publication client

This standard-library-only example calls the separately deployed finalized-review
publication service. It sends only the versioned `world_id` and `review_id`;
publication time, operation identity, graph materialization, and durable replay
remain server/kernel authority.

```bash
export DUNGEONMIND_PUBLICATION_BEARER_TOKEN='local-secret-from-operator'
uv run python examples/finalized_review_publication_client/client.py \
  --base-url http://127.0.0.1:8001 \
  --world-id world:synthetic-gatewatch \
  --review-id review:cff0162637b428e634e8cccaa9958dc2 \
  --verify-replay
```

The token is read only from `DUNGEONMIND_PUBLICATION_BEARER_TOKEN`; it is not a
command-line argument or part of `request.json`. An outcome-unknown `503` with
`retry_safe=true` is reported as a temporary failure without changing the
request.
