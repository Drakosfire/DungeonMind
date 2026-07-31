"""Application port for query-time embedding providers."""

from typing import Protocol


class QueryEmbeddingProvider(Protocol):
    """Produces query vectors for dense retrieval. Adapters never embed."""

    @property
    def provider_id(self) -> str: ...

    def embed_query(self, text: str) -> list[float] | None: ...
