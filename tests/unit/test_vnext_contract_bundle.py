import subprocess
import sys
from pathlib import Path


def test_checked_in_vnext_bundle_is_reproducible() -> None:
    root = Path(__file__).parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "scripts/generate_vnext_contract_bundle.py",
            "--check",
            "Docs/Contracts/vnext/dm_vnext_contract_v1.json",
        ],
        cwd=root,
        check=False,
    )
    assert result.returncode == 0
