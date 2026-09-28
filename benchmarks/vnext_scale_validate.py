"""Strict structural and semantic validator for vNext characterization output."""

from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
import sys
from pathlib import Path
from typing import Any

HEX64 = re.compile(r"^[0-9a-f]{64}$")
SHAPES = ("world_like", "rules_like")
SIZES = (100, 1_000, 10_000, 50_000, 100_000)
REQUIRED_CORE = (
    "full_projection",
    "exact_entity",
    "complete_entity",
    "neighborhood_d1",
    "neighborhood_d2",
    "evidence",
    "source_anchor",
    "deterministic_search",
)
BASE_OPERATIONS = (
    "cold_parse",
    "full_projection",
    "exact_entity",
    "complete_entity",
    "neighborhood_d1",
    "neighborhood_d2",
    "evidence",
    "source_anchor",
    "deterministic_search",
    "source_snapshot",
    "tiny_delta_publication",
    "canonical_serialize_hash",
)
ACCEPTANCE_STATUSES = {
    "PARTIAL_MEMORY_BASELINE_THROUGH_10K_PENDING_PRIME_REVIEW",
    "MEASUREMENTS_COMPLETE_AWAITING_PRIME_REVIEW",
    "ACCEPTED",
}
POSTGRESQL_REASON = "No PostgreSQL target authorized by PR #91 activation."


def validate(document: dict[str, Any]) -> None:
    if document.get("schema") != "dungeonmind.vnext-scale-characterization.v1":
        raise ValueError("wrong or missing schema")
    rows = document.get("matrix")
    if not isinstance(rows, list):
        raise ValueError("matrix must be a list")
    if (
        not isinstance(document.get("acceptance_status"), str)
        or document["acceptance_status"] not in ACCEPTANCE_STATUSES
    ):
        raise ValueError("unknown acceptance status")
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("matrix rows must be objects")
    keys = [(r.get("shape"), r.get("size"), r.get("operation"), r.get("adapter")) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate matrix cells")
    required = {
        (s, n, op, adapter)
        for s in SHAPES
        for n in SIZES
        for op in BASE_OPERATIONS
        for adapter in ("memory", "postgresql")
    }
    present = set(keys)
    missing = required - present
    if missing:
        raise ValueError(f"missing matrix cells: {sorted(missing)[:5]}")
    if present - required:
        raise ValueError(f"unexpected matrix cells: {sorted(present - required)[:5]}")
    allowed = {"measured", "not_applicable", "not_measured", "resource_limited"}
    for row in rows:
        expected_family = (
            "inactive_postgresql"
            if row["adapter"] == "postgresql"
            else "native_vnext"
            if row["operation"] == "tiny_delta_publication"
            else "classic_v6_world_graph"
        )
        if row.get("api_family") != expected_family:
            raise ValueError("matrix API family does not match operation/adapter")
        disposition = row.get("disposition")
        if disposition not in allowed:
            raise ValueError(f"invalid disposition: {disposition}")
        if disposition != "measured" and not row.get("reason"):
            raise ValueError("non-measured row must state reason")
        if disposition == "measured":
            for field in ("input_sha256", "result_sha256"):
                if not HEX64.fullmatch(str(row.get(field, ""))):
                    raise ValueError(f"malformed {field}")
            if not isinstance(row.get("samples_seconds"), list) or not row["samples_seconds"]:
                raise ValueError("measured cell requires raw timing samples")
            samples = row["samples_seconds"]
            if any(
                type(value) not in (int, float) or not math.isfinite(value) or value < 0
                for value in samples
            ):
                raise ValueError("timing samples must be finite nonnegative numbers")
            median = row.get("median_seconds")
            if (
                type(median) not in (int, float)
                or not math.isfinite(median)
                or median != statistics.median(samples)
            ):
                raise ValueError("median_seconds must match timing samples")
            peak = row.get("peak_tracemalloc_bytes")
            if type(peak) is not int or peak < 0:
                raise ValueError("measured cell requires nonnegative peak memory observation")
    accepted = document.get("acceptance_status") == "ACCEPTED"
    for shape in SHAPES:
        for size in (50_000, 100_000):
            for operation in REQUIRED_CORE:
                row = next(
                    r
                    for r in rows
                    if (r["shape"], r["size"], r["operation"], r["adapter"])
                    == (shape, size, operation, "memory")
                )
                if accepted and row["disposition"] not in {"measured", "resource_limited"}:
                    raise ValueError(
                        "accepted artifact lacks attempted large-scale core cell: "
                        f"{shape}/{size}/{operation}"
                    )
                if row["disposition"] == "not_measured" and not row.get("reason"):
                    raise ValueError(
                        f"large-scale core cell has no explicit reason: {shape}/{size}/{operation}"
                    )
    if document.get("postgresql") != {
        "activated": False,
        "disposition": "not_measured",
        "reason": POSTGRESQL_REASON,
    }:
        raise ValueError("PostgreSQL disposition does not match activation")
    for row in rows:
        if row["adapter"] == "postgresql" and (
            row["disposition"] != "not_measured" or row.get("reason") != POSTGRESQL_REASON
        ):
            raise ValueError("PostgreSQL cells must retain the exhaustive inactive disposition")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    path = Path(
        sys.argv[1] if len(sys.argv) > 1 else "Docs/Reports/VNEXT-scale-characterization-v1.json"
    )
    document = json.loads(path.read_text())
    validate(document)
    print(f"VALID {path} sha256={file_sha256(path)}")


if __name__ == "__main__":
    main()
