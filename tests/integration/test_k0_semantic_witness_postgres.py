"""PostgreSQL parity checks for the K0.2 semantic witness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.witness.k0_semantic_fixture import stores_from_postgres_bundle
from tests.witness.k0_semantic_normalize import (
    REQUIRED_OPERATION_IDS,
    aggregate_semantic_sha256,
)
from tests.witness.k0_semantic_run import run_witness

pytestmark = pytest.mark.integration

ADAPTER_NEUTRAL_OPERATION_IDS = frozenset(REQUIRED_OPERATION_IDS)
GOLDEN_PATH = (
    Path(__file__).resolve().parents[2] / "Docs/Reports/K0-golden-semantic-witness-v1.json"
)


def test_postgres_matches_checked_in_semantic_golden(pg) -> None:
    if not GOLDEN_PATH.exists():
        pytest.fail(f"checked-in golden witness missing: {GOLDEN_PATH.name}")
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    actual = run_witness(
        adapter="postgres",
        stores=stores_from_postgres_bundle(pg),
    )
    actual_operations = [
        row for row in actual["operations"] if row["id"] in ADAPTER_NEUTRAL_OPERATION_IDS
    ]
    golden_operations = [
        row for row in golden["operations"] if row["id"] in ADAPTER_NEUTRAL_OPERATION_IDS
    ]
    assert aggregate_semantic_sha256(actual_operations) == aggregate_semantic_sha256(
        golden_operations
    )
