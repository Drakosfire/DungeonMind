"""K0.1 current consumer and public-surface inventory generator.

Observational only: no DungeonMind runtime behavior change. Exact anchors are
required; a mismatched Buddy or DungeonMind tree is a hard failure.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from k0_inventory_curated import (  # noqa: E402
    EXCEPTION_OVERLAY,
    REPOSITORY_OVERLAY,
    TABLE_OVERLAY,
    subsystem_dispositions,
)
from k0_inventory_scan import (  # noqa: E402
    AnchorMismatchError,
    consumer_kind,
    dump_json,
    git_rev_parse,
    internal_import_graph,
    inventory_alembic_tables,
    inventory_explicit_exports,
    inventory_import_boundary_exceptions,
    inventory_repository_protocols,
    iter_python_files,
    probe_optional_dependency_loads,
    reachable,
    resolve_import,
    scan_file_imports,
    verify_buddy_anchor,
    verify_dungeonmind_code_anchor,
)
from k0_inventory_validate import SCHEMA, validate_ledger  # noqa: E402

DEFAULT_CODE_ANCHOR = "5ca5d688612349034f8ca490d465af166d883e6e"
DEFAULT_STEWARD_BASE = "84a4479494a37d8b5bd550465d17ff29f0e359ec"
DEFAULT_BUDDY_ANCHOR = "a9d4c61d04f2a4a5f92cb6947442d8173079454c"

READ_SEEDS = (
    "dungeonmind.application.world_graph_projection",
    "dungeonmind.application.world_graph_retrieval",
    "dungeonmind.application.world_graph_read_context",
)
WRITE_SEEDS = (
    "dungeonmind.application.review_publication",
    "dungeonmind.application.contribution_review_v2",
    "dungeonmind.application.contribution_review",
    "dungeonmind.application.review_materialization_v6",
)
SOURCE_SEEDS = (
    "dungeonmind.application.source_provenance_snapshot",
)
INIT_SEEDS = (
    "dungeonmind.application.reviewed_world_initialization",
)
FOUNDING_SEEDS = (
    "dungeonmind.application.mind_turn",
    "dungeonmind.application.context_assembly",
    "dungeonmind.agents.protocol",
    "dungeonmind.agents.fixture",
    "dungeonmind.service.demo_access",
    "dungeonmind.service.api",
    "dungeonmind.service.bootstrap",
)
COMPAT_SEEDS = (
    "dungeonmind.application.existing_world_adoption",
    "dungeonmind.application.existing_world_adoption_repair",
    "dungeonmind.application.existing_world_correspondence",
    "dungeonmind.application.graph_snapshot_v4",
    "dungeonmind.application.graph_snapshot_v5",
)


def _import_rows(
    records: list[Any],
    src_root: Path,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        resolves = resolve_import(src_root, record.imported_module, record.imported_symbols)
        rows.append(
            {
                "consumer_file": record.consumer_file,
                "consumer_kind": consumer_kind(record.consumer_file),
                "imported_module": record.imported_module,
                "imported_symbols": record.imported_symbols,
                "import_form": record.import_form,
                "in_type_checking": record.in_type_checking,
                "dynamic": record.dynamic,
                "line": record.line,
                "resolves_against_code_anchor": resolves,
            }
        )
    rows.sort(
        key=lambda row: (
            str(row["consumer_file"]),
            int(row["line"]),
            str(row["imported_module"]),
            tuple(row["imported_symbols"]),
        )
    )
    return rows


def _export_rows(
    exports: list[Any],
    buddy_imports: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    imported: set[tuple[str, str]] = set()
    imported_modules: set[str] = set()
    for row in buddy_imports:
        imported_modules.add(str(row["imported_module"]))
        for symbol in row["imported_symbols"]:
            imported.add((str(row["imported_module"]), str(symbol)))
    rows: list[dict[str, Any]] = []
    for export in exports:
        direct = (export.module, export.name) in imported
        module_imported = export.module in imported_modules
        rows.append(
            {
                "package": export.package,
                "module": export.module,
                "name": export.name,
                "origin": export.origin,
                "in_all": export.in_all,
                "buddy_direct_import": direct,
                "buddy_imports_module": module_imported,
                "known_external_consumer": "YES" if direct else "NO_KNOWN_EXTERNAL_CONSUMER",
            }
        )
    return rows


def _merge_repository_ledger(derived: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for row in derived:
        ident = str(row["id"])
        overlay = REPOSITORY_OVERLAY.get(ident, {})
        merged.append({**row, **overlay})
        if ident not in REPOSITORY_OVERLAY:
            merged[-1]["disposition"] = "UNKNOWN"
            merged[-1]["blocking_question"] = (
                f"No curated overlay for repository protocol/bundle {ident}."
            )
            merged[-1]["evidence"] = [row.get("defining_path")]
    merged.sort(key=lambda item: str(item["id"]))
    return merged


def _merge_table_ledger(derived: list[dict[str, str]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for row in derived:
        ident = str(row["id"])
        overlay = TABLE_OVERLAY.get(ident, {})
        item = {**row, **overlay}
        if ident not in TABLE_OVERLAY:
            item["disposition"] = "UNKNOWN"
            item["blocking_question"] = f"No curated overlay for table {ident}."
            item["k1_code_demolition_while_table_remains"] = False
            item["evidence"] = [f"migrations/versions/{row['creation_migration']}"]
        merged.append(item)
    merged.sort(key=lambda item: str(item["id"]))
    return merged


def _merge_exceptions(derived: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for row in derived:
        ident = str(row["id"])
        overlay = EXCEPTION_OVERLAY.get(ident, {})
        item = {**row, **overlay}
        if "protects" not in item:
            item["protects"] = "UNKNOWN"
            item["blocking_question"] = f"No classification for import-boundary exception {ident}."
        merged.append(item)
    merged.sort(key=lambda item: str(item["id"]))
    return merged


def build_ledger(
    *,
    dungeonmind_root: Path,
    buddy_root: Path,
    code_anchor: str,
    steward_base: str,
    buddy_anchor: str,
    expected_pin: str,
    skip_probe: bool = False,
) -> dict[str, Any]:
    verify_dungeonmind_code_anchor(dungeonmind_root, code_anchor)
    pin = verify_buddy_anchor(buddy_root, buddy_anchor, expected_pin)
    src_root = dungeonmind_root / "src"

    buddy_records = []
    dynamic_findings: list[dict[str, Any]] = []
    for path in iter_python_files(buddy_root):
        records, extra = scan_file_imports(path, buddy_root)
        buddy_records.extend(records)
        dynamic_findings.extend(extra)
    imports = _import_rows(buddy_records, src_root)

    exports = _export_rows(inventory_explicit_exports(src_root), imports)
    graph = internal_import_graph(src_root)
    repos = inventory_repository_protocols(src_root)
    tables = inventory_alembic_tables(dungeonmind_root / "migrations")
    exceptions = inventory_import_boundary_exceptions(
        dungeonmind_root / "tests" / "unit" / "test_import_boundaries.py"
    )
    probe = (
        {"ok": True, "probes": [], "skipped": True}
        if skip_probe
        else probe_optional_dependency_loads(dungeonmind_root)
    )

    subsystems = subsystem_dispositions()
    subsystems.sort(key=lambda row: str(row["id"]))

    production_files = sorted(
        {
            str(row["consumer_file"])
            for row in imports
            if row["consumer_kind"] == "production"
        }
    )

    ledger: dict[str, Any] = {
        "schema": SCHEMA,
        "anchors": {
            "dungeonmind_code_anchor": code_anchor,
            "dungeonmind_steward_base": steward_base,
            "dungeonmind_scanned_head": git_rev_parse(dungeonmind_root),
            "buddy_anchor": buddy_anchor,
            "buddy_dungeonmind_pin": pin,
        },
        "reproduction": {
            "command": [
                "uv",
                "run",
                "python",
                "scripts/k0_surface_inventory.py",
                "--dungeonmind-root",
                ".",
                "--dungeonmind-code-anchor",
                code_anchor,
                "--buddy-root",
                "../DungeonMindBuddy",
                "--buddy-anchor",
                buddy_anchor,
                "--expected-buddy-dungeonmind-pin",
                expected_pin,
                "--output",
                "Docs/Reports/K0-current-consumer-public-surface-v1.json",
            ]
        },
        "headline_counts": {},
        "external_consumer_imports": imports,
        "explicit_exports": exports,
        "internal_import_evidence": {
            "world_read_path_modules": reachable(graph, READ_SEEDS),
            "world_write_publication_path_modules": reachable(graph, WRITE_SEEDS),
            "source_evidence_path_modules": reachable(graph, SOURCE_SEEDS),
            "initialization_path_modules": reachable(graph, INIT_SEEDS),
            "founding_runtime_path_modules": reachable(graph, FOUNDING_SEEDS),
            "compatibility_path_modules": reachable(graph, COMPAT_SEEDS),
        },
        "repository_ledger": _merge_repository_ledger(repos),
        "table_ledger": _merge_table_ledger(tables),
        "import_boundary_exceptions": _merge_exceptions(exceptions),
        "optional_dependency_probe": probe,
        "subsystem_dispositions": subsystems,
        "dynamic_import_findings": sorted(
            dynamic_findings,
            key=lambda row: (str(row.get("consumer_file")), int(row.get("line") or 0)),
        ),
        "derived_alembic_tables": [row["id"] for row in tables],
        "derived_repository_ids": [row["id"] for row in repos],
        "unresolved_questions": [
            row["blocking_question"]
            for row in subsystems
            if row.get("disposition") == "UNKNOWN" and row.get("blocking_question")
        ]
        + [
            row["blocking_question"]
            for row in _merge_exceptions(exceptions)
            if row.get("protects") == "UNKNOWN" and row.get("blocking_question")
        ],
        "production_consumer_files": production_files,
        "observation_notice": (
            "NO_KNOWN_EXTERNAL_CONSUMER is not permission to delete. This ledger "
            "describes the exact anchors above and does not promote observed exports "
            "into a permanent public API."
        ),
    }

    by_disp: dict[str, int] = defaultdict(int)
    for row in subsystems:
        by_disp[str(row["disposition"])] += 1
    distinct_modules = sorted({str(row["imported_module"]) for row in imports})
    distinct_symbols = sorted(
        {
            f"{row['imported_module']}:{symbol}"
            for row in imports
            for symbol in row["imported_symbols"]
            if symbol != "*"
        }
    )
    ledger["headline_counts"] = {
        "buddy_files_importing_dungeonmind": len(
            {str(row["consumer_file"]) for row in imports}
        ),
        "distinct_imported_dungeonmind_modules": len(distinct_modules),
        "distinct_imported_dungeonmind_symbols": len(distinct_symbols),
        "explicit_exported_symbols": len(exports),
        "repository_protocol_bundle_entries": len(ledger["repository_ledger"]),
        "postgresql_tables": len(ledger["table_ledger"]),
        "subsystem_dispositions": {
            "USED": by_disp["USED"],
            "UNUSED": by_disp["UNUSED"],
            "HISTORICAL-COMPAT": by_disp["HISTORICAL-COMPAT"],
            "UNKNOWN": by_disp["UNKNOWN"],
        },
        "import_boundary_exceptions": len(ledger["import_boundary_exceptions"]),
        "dynamic_import_findings": len(ledger["dynamic_import_findings"]),
    }
    validate_ledger(ledger)
    return ledger


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dungeonmind-root", type=Path, default=Path("."))
    parser.add_argument("--dungeonmind-code-anchor", default=DEFAULT_CODE_ANCHOR)
    parser.add_argument("--dungeonmind-steward-base", default=DEFAULT_STEWARD_BASE)
    parser.add_argument("--buddy-root", type=Path, required=True)
    parser.add_argument("--buddy-anchor", default=DEFAULT_BUDDY_ANCHOR)
    parser.add_argument(
        "--expected-buddy-dungeonmind-pin",
        default=DEFAULT_CODE_ANCHOR,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("Docs/Reports/K0-current-consumer-public-surface-v1.json"),
    )
    parser.add_argument("--skip-optional-probe", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dungeonmind_root = args.dungeonmind_root.resolve()
    buddy_root = args.buddy_root.resolve()
    try:
        ledger = build_ledger(
            dungeonmind_root=dungeonmind_root,
            buddy_root=buddy_root,
            code_anchor=args.dungeonmind_code_anchor,
            steward_base=args.dungeonmind_steward_base,
            buddy_anchor=args.buddy_anchor,
            expected_pin=args.expected_buddy_dungeonmind_pin,
            skip_probe=args.skip_optional_probe,
        )
    except AnchorMismatchError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    output = args.output
    if not output.is_absolute():
        output = dungeonmind_root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    text = dump_json(ledger)
    output.write_text(text, encoding="utf-8")
    sys.stdout.write(f"wrote {output.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
