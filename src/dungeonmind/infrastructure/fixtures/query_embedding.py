"""Deterministic fixture query embeddings — no network, no model download."""

from __future__ import annotations

from collections.abc import Mapping

FIXTURE_EMBEDDING_PROVIDER_ID = "fixture_embedding_provider"


class FixtureQueryEmbeddingProvider:
    """Eight-dimensional deterministic vectors for curated Mind Turn vocabulary."""

    def __init__(self, vectors: Mapping[str, list[float]] | None = None) -> None:
        self._vectors = {key: list(value) for key, value in (vectors or {}).items()}

    @property
    def provider_id(self) -> str:
        return FIXTURE_EMBEDDING_PROVIDER_ID

    def embed_query(self, text: str) -> list[float] | None:
        exact = self._vectors.get(text)
        if exact is not None:
            return list(exact)
        folded = text.casefold().strip()
        for key, value in self._vectors.items():
            if key.casefold().strip() == folded:
                return list(value)
        return None
