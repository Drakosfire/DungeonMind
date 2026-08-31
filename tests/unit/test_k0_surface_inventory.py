"""Unit tests for the K0.1 observational surface inventory."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from k0_inventory_scan import (  # noqa: E402
    AnchorMismatchError,
    dump_json,
    read_buddy_dungeonmind_pin,
    verify_buddy_anchor,
)
from k0_inventory_validate import (  # noqa: E402
    NAMED_SUBSYSTEM_IDS,
    LedgerValidationError,
    validate_ledger,
)


def _minimal_ledger(**overrides: Any) -> dict[str, Any]:
    subsystems = [
        {
            "id": ident,
            "disposition": "USED",
            "evidence": ["src/dungeonmind/__init__.py"],
        }
        for ident in NAMED_SUBSYSTEM_IDS
    ]
    ledger: dict[str, Any] = {
        "schema": "dm_k0_surface_inventory_v1",
        "inputs": {
            "dungeonmind_runtime_anchor": "a" * 40,
            "dungeonmind_steward_base": "b" * 40,
            "runtime_tree_digest": "sha256:" + ("0" * 64),
            "buddy_anchor": "c" * 40,
            "buddy_dungeonmind_pin": "a" * 40,
            "dispositions_digest": "sha256:" + ("1" * 64),
            "scanner_version": "k0.1.1",
        },
        "external_consumer_imports": [],
        "explicit_exports": [],
        "internal_import_evidence": {},
        "repository_ledger": [{"id": "WorldGraphRepository"}],
        "table_ledger": [{"id": "worlds"}],
        "import_boundary_exceptions": [],
        "optional_dependency_probe": {"ok": True, "probes": []},
        "subsystem_dispositions": subsystems,
        "module_string_consumer_evidence": {"buddy": [], "dungeonmind": []},
        "known_red_baselines": [],
        "unresolved_questions": [],
        "derived_alembic_tables": ["worlds"],
        "derived_repository_ids": ["WorldGraphRepository"],
    }
    ledger.update(overrides)
    return ledger


def test_validate_rejects_unknown_disposition() -> None:
    ledger = _minimal_ledger()
    ledger["subsystem_dispositions"][0]["disposition"] = "MAYBE"
    with pytest.raises(LedgerValidationError, match="unknown disposition"):
        validate_ledger(ledger)


def test_validate_rejects_duplicate_ids() -> None:
    ledger = _minimal_ledger()
    ledger["table_ledger"] = [{"id": "worlds"}, {"id": "worlds"}]
    with pytest.raises(LedgerValidationError, match="duplicate table"):
        validate_ledger(ledger)


def test_validate_rejects_missing_evidence() -> None:
    ledger = _minimal_ledger()
    ledger["subsystem_dispositions"][0]["evidence"] = []
    with pytest.raises(LedgerValidationError, match="missing evidence"):
        validate_ledger(ledger)


def test_validate_rejects_unknown_without_blocking_question() -> None:
    ledger = _minimal_ledger()
    ledger["subsystem_dispositions"][0]["disposition"] = "UNKNOWN"
    ledger["subsystem_dispositions"][0].pop("blocking_question", None)
    with pytest.raises(LedgerValidationError, match="blocking_question"):
        validate_ledger(ledger)


def test_validate_rejects_unused_covering_buddy_import() -> None:
    ledger = _minimal_ledger()
    ledger["external_consumer_imports"] = [
        {
            "consumer_file": "apps/live_control_server/x.py",
            "imported_module": "dungeonmind.application.world_graph_projection",
            "imported_symbols": ["WorldGraphProjectionService"],
            "resolves_against_code_anchor": True,
        }
    ]
    ledger["subsystem_dispositions"][0].update(
        {
            "id": "mind_turn_contracts_and_service",
            "disposition": "UNUSED",
            "covers": ["dungeonmind.application.world_graph_projection"],
            "evidence": ["src/dungeonmind/application/mind_turn.py"],
            "falsification_note": "would be wrong",
        }
    )
    with pytest.raises(LedgerValidationError, match="Buddy-imported"):
        validate_ledger(ledger)


def test_validate_rejects_omitted_alembic_table() -> None:
    ledger = _minimal_ledger()
    ledger["derived_alembic_tables"] = ["worlds", "campaigns"]
    with pytest.raises(LedgerValidationError, match="omitted from table ledger"):
        validate_ledger(ledger)


def test_validate_rejects_unresolved_buddy_import() -> None:
    ledger = _minimal_ledger()
    ledger["external_consumer_imports"] = [
        {
            "consumer_file": "apps/x.py",
            "imported_module": "dungeonmind.missing",
            "imported_symbols": ["Nope"],
            "resolves_against_code_anchor": False,
        }
    ]
    with pytest.raises(LedgerValidationError, match="unresolved imported Buddy"):
        validate_ledger(ledger)


def test_validate_accepts_minimal_valid_ledger() -> None:
    validate_ledger(_minimal_ledger())


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    _git(path, "config", "user.email", "k0@example.test")
    _git(path, "config", "user.name", "K0 Inventory")
    (path / "README").write_text("x\n", encoding="utf-8")
    _git(path, "add", "README")
    _git(path, "commit", "-m", "init")


def test_buddy_anchor_mismatch(tmp_path: Path) -> None:
    repo = tmp_path / "buddy"
    _init_repo(repo)
    (repo / "pyproject.toml").write_text(
        'dependencies = [\n'
        '  "dungeonmind[postgres] @ git+https://github.com/Drakosfire/DungeonMind.git@'
        + ("a" * 40)
        + '",\n]\n',
        encoding="utf-8",
    )
    _git(repo, "add", "pyproject.toml")
    _git(repo, "commit", "-m", "pin")
    with pytest.raises(AnchorMismatchError, match="expected"):
        verify_buddy_anchor(repo, expected_anchor="b" * 40, expected_pin="a" * 40)


def test_buddy_pin_reader_and_match(tmp_path: Path) -> None:
    repo = tmp_path / "buddy"
    _init_repo(repo)
    pin = "5ca5d688612349034f8ca490d465af166d883e6e"
    (repo / "pyproject.toml").write_text(
        'dependencies = [\n'
        f'  "dungeonmind[postgres] @ git+https://github.com/Drakosfire/DungeonMind.git@{pin}",\n'
        "]\n",
        encoding="utf-8",
    )
    _git(repo, "add", "pyproject.toml")
    _git(repo, "commit", "-m", "pin")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert read_buddy_dungeonmind_pin(repo) == pin
    assert verify_buddy_anchor(repo, expected_anchor=head, expected_pin=pin) == pin


def test_dump_json_is_deterministic() -> None:
    payload = {"b": 1, "a": {"z": True, "m": [2, 1]}}
    assert dump_json(payload) == dump_json(payload)
    assert dump_json(payload).startswith('{\n  "a":')


def test_generator_module_loads() -> None:
    path = SCRIPTS / "k0_surface_inventory.py"
    spec = importlib.util.spec_from_file_location("k0_surface_inventory", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.DEFAULT_CODE_ANCHOR == "5ca5d688612349034f8ca490d465af166d883e6e"
    parsed = json.loads(dump_json({"schema": "dm_k0_surface_inventory_v1"}))
    assert parsed["schema"] == "dm_k0_surface_inventory_v1"


def test_export_rows_match_origin_symbol_imports() -> None:
    from k0_inventory_scan import ExportRecord
    from k0_surface_inventory import _export_rows

    exports = [
        ExportRecord(
            package="dungeonmind",
            module="dungeonmind.application",
            name="WorldGraphProjectionService",
            origin="dungeonmind.application.world_graph_projection",
            in_all=True,
        )
    ]
    buddy_imports = [
        {
            "imported_module": "dungeonmind.application.world_graph_projection",
            "imported_symbols": ["WorldGraphProjectionService"],
        }
    ]
    rows = _export_rows(exports, buddy_imports)
    assert rows[0]["buddy_origin_symbol_import"] is True
    assert rows[0]["buddy_direct_reexport_import"] is False
    assert rows[0]["known_external_consumer"] == "YES"
    assert rows[0]["external_consumer_paths"] == ["origin_module"]


def test_dispositions_digest_is_stable() -> None:
    from k0_inventory_dispositions import (
        DEFAULT_DISPOSITIONS_PATH,
        dispositions_digest,
    )

    first = dispositions_digest(DEFAULT_DISPOSITIONS_PATH)
    second = dispositions_digest(DEFAULT_DISPOSITIONS_PATH)
    assert first == second
    assert first.startswith("sha256:")
