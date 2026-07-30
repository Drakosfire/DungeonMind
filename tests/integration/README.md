# Integration tests (PR B)

Opt-in locally, active in CI. These run against a real PostgreSQL+pgvector
instance and pin the same invariants the in-memory adapters enforce
(revision immutability, CAS head publication, filter semantics).

Local run (once PR B lands):

```bash
uv sync --extra postgres
docker compose -f deploy/dev/docker-compose.yml up -d   # pinned pgvector image
DUNGEONMIND_DATABASE_URL=postgresql://dungeonmind:...@127.0.0.1:5432/dungeonmind \
  uv run pytest -m integration
```

Tests here must be marked `@pytest.mark.integration` and must skip cleanly
when `DUNGEONMIND_DATABASE_URL` is unset.
