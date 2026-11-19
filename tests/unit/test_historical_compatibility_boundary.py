"""The current native facade must not silently activate historical reconstruction."""

from __future__ import annotations

import subprocess
import sys

import pytest

HISTORICAL_EXPORTS = (
    "COMPATIBILITY_DOMAIN_CONTRACT_ID",
    "COMPATIBILITY_DOMAIN_CONTRACT_REVISION",
    "COMPATIBILITY_MANIFEST_SHA256",
    "COMPATIBILITY_MAPPING_REVISION",
    "LegacyCompatibilityIntegrityError",
    "LegacyCompatibilityManifest",
    "build_historical_semantic_witness",
    "build_parsed_revision_semantic_witness",
    "compute_legacy_compatibility_key",
    "compute_mapping_implementation_digest",
    "decode_legacy_graph_revision",
    "decode_legacy_stored_graph_revision",
    "load_legacy_world_compat_manifest",
    "validate_stored_legacy_graph_revision",
    "verify_historical_semantic_parity",
    "verify_legacy_compatibility_manifest",
)


def test_native_facade_does_not_load_or_export_historical_codec() -> None:
    code = f"""
import importlib.util
import sys
import dungeonmind.application.vnext as native
assert not any(n.startswith('dungeonmind.application.compatibility') for n in sys.modules)
for name in {HISTORICAL_EXPORTS!r}:
    assert name not in native.__all__ and not hasattr(native, name), name
assert importlib.util.find_spec('dungeonmind.application.vnext.legacy_compat') is None
assert importlib.util.find_spec('dungeonmind.application.vnext.data') is None
"""
    subprocess.run([sys.executable, "-c", code], check=True)


@pytest.mark.parametrize("compatibility_first", [False, True])
def test_explicit_historical_api_works_in_either_import_order(compatibility_first: bool) -> None:
    code = f"""
import importlib
order = ['dungeonmind.application.compatibility', 'dungeonmind.application.vnext']
if not {compatibility_first!r}:
    order.reverse()
for name in order:
    importlib.import_module(name)
from dungeonmind.application import compatibility
from dungeonmind.application.compatibility import legacy_graph
from dungeonmind.application.vnext.errors import LegacyCompatibilityIntegrityError
for name in {HISTORICAL_EXPORTS!r}:
    assert name in compatibility.__all__
assert compatibility.LegacyCompatibilityIntegrityError is LegacyCompatibilityIntegrityError
assert compatibility.decode_legacy_graph_revision is legacy_graph.decode_legacy_graph_revision
manifest = compatibility.load_legacy_world_compat_manifest()
assert manifest.manifest_sha256 == compatibility.COMPATIBILITY_MANIFEST_SHA256
# Actual callable dispatch through the new public facade, not only export inventory.
import scripts.generate_legacy_compatibility_parity_artifact as generator
assert generator.decode_legacy_graph_revision is compatibility.decode_legacy_graph_revision
artifact = generator.generate_parity_artifact_data()
assert artifact['records_count'] == 6
assert all(record['parity'] == 'PASS' for record in artifact['records'])
"""
    subprocess.run([sys.executable, "-c", code], check=True)
