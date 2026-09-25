#!/usr/bin/env python3
"""Generate or verify the standalone V3 semantic-profile JSON schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dungeonmind.contracts.vnext.domain import SemanticProfileDescriptorV3

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "Docs/Contracts/vnext/dm_semantic_profile_v3.schema.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    payload = (
        json.dumps(
            SemanticProfileDescriptorV3.model_json_schema(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        + b"\n"
    )
    if args.write:
        SCHEMA_PATH.write_bytes(payload)
        return 0
    if not SCHEMA_PATH.exists() or SCHEMA_PATH.read_bytes() != payload:
        print(f"schema is stale: {SCHEMA_PATH}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
