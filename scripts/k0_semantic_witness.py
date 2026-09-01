"""Generate or validate the deterministic K0.2 semantic witness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

from tests.witness.k0_semantic_normalize import (  # noqa: E402
    dump_canonical_json,
    validate_witness,
)
from tests.witness.k0_semantic_run import run_witness  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", choices=("memory", "postgres"), default="memory")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--validate-only",
        type=Path,
        metavar="PATH",
        help="validate an existing witness without running operations",
    )
    args = parser.parse_args()

    if args.validate_only is not None:
        witness = json.loads(args.validate_only.read_text(encoding="utf-8"))
        validate_witness(witness)
        print(f"validated {args.validate_only}")
        return 0
    if args.output is None:
        parser.error("--output is required unless --validate-only is used")

    witness = run_witness(adapter=args.adapter)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(dump_canonical_json(witness), encoding="utf-8")
    print(f"wrote {args.output}")
    print(witness["aggregate_semantic_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
