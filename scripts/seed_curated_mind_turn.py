#!/usr/bin/env python3
"""Explicit idempotent seed for the curated Mind Turn fixture."""

from __future__ import annotations

import os
import sys

from dungeonmind.domain.errors import PersistenceUnavailableError
from dungeonmind.infrastructure.fixtures.curated_mind_turn import (
    load_curated_mind_turn_fixture,
    seed_curated_mind_turn,
)
from dungeonmind.infrastructure.postgres import PostgresDatabase, PostgresRepositoryBundle


def main() -> int:
    url = os.environ.get("DUNGEONMIND_DATABASE_URL")
    if not url:
        raise PersistenceUnavailableError("DUNGEONMIND_DATABASE_URL is required")
    fixture = load_curated_mind_turn_fixture()
    database = PostgresDatabase(url)
    bundle = PostgresRepositoryBundle(database)
    result = seed_curated_mind_turn(
        world_graph=bundle.world_graph,
        sources=bundle.sources,
        embedding_runs=bundle.embedding_runs,
        semantic_documents=bundle.semantic_documents,
        threads=bundle.threads,
        fixture=fixture,
    )
    print(
        f"status={result.status} world_id={result.world_id} revision_id={result.revision_id} "
        f"embedding_run_id={result.embedding_run_id} thread_id={result.thread_id}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"seed_failed error={type(exc).__name__}", file=sys.stderr)
        raise
