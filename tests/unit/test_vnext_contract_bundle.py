import subprocess
import sys
from pathlib import Path

from scripts.generate_vnext_contract_bundle import make_bundle

from dungeonmind.contracts import vnext


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


def test_bundle_inventory_matches_public_contract_models() -> None:
    bundle_names = {item["public_name"] for item in make_bundle()["contracts"]}
    model_names = {model.__name__ for model in vnext.PUBLIC_CONTRACT_MODELS}
    assert bundle_names == model_names
    assert model_names <= set(vnext.__all__)
