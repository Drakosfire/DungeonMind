"""Stub reviewed-init repository for projection tests that do not exercise genesis."""

from __future__ import annotations

from typing import Any

from dungeonmind.contracts.reviewed_world_initialization import (
    ReviewedWorldInitializationReceiptV1,
)


class NullReviewedWorldInitializationRepository:
    """Required projection dependency whose absence of a receipt is ``None``."""

    def get_for_world(self, world_id: str) -> ReviewedWorldInitializationReceiptV1 | None:
        return None

    def get(
        self, world_id: str, initialization_id: str
    ) -> ReviewedWorldInitializationReceiptV1 | None:
        return None

    def initialize(self, *args: Any, **kwargs: Any) -> ReviewedWorldInitializationReceiptV1:
        raise AssertionError("reviewed-world initialize is not used by this projection test")
