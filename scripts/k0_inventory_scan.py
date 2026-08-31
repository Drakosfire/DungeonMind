"""Deterministic scanners for the K0.1 consumer/public-surface inventory."""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DM_MODULE_RE = re.compile(
    r"^(?:dungeonmind|dungeonmind_dnd)(?:\.[A-Za-z_][A-Za-z0-9_]*)*$"
)
SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}
CREATE_TABLE_RE = re.compile(
    r"CREATE TABLE\s+(?:IF NOT EXISTS\s+)?(?:\{SCHEMA\}|dungeonmind)\.([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)
PIN_RE = re.compile(
    r"dungeonmind(?:\[[^\]]+\])?\s*@\s*git\+https://github\.com/Drakosfire/DungeonMind\.git@([0-9a-f]{40})",
    re.IGNORECASE,
)
LOCK_PIN_RE = re.compile(
    r"Drakosfire/DungeonMind\.git\?rev=([0-9a-f]{40})",
)


class AnchorMismatchError(SystemExit):
    """Exact-anchor rule failed; do not scan a different tree."""


def _sorted_unique(values: Iterable[str]) -> list[str]:
    return sorted(set(values))


def iter_python_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in SKIP_DIR_NAMES)
        for name in sorted(filenames):
            if name.endswith(".py"):
                files.append(Path(dirpath) / name)
    return files


def git_rev_parse(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AnchorMismatchError(
            f"not a git checkout: {root}\n{result.stderr.strip()}"
        )
    return result.stdout.strip()


def git_diff_names(root: Path, commit: str, paths: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "diff", "--name-only", commit, "--", *paths],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AnchorMismatchError(
            f"unable to diff {root} against {commit}: {result.stderr.strip()}"
        )
    return [line for line in result.stdout.splitlines() if line.strip()]


def read_buddy_dungeonmind_pin(buddy_root: Path) -> str:
    pyproject = (buddy_root / "pyproject.toml").read_text(encoding="utf-8")
    match = PIN_RE.search(pyproject)
    if match is None:
        raise AnchorMismatchError(
            "Buddy pyproject.toml does not pin DungeonMind to an exact git SHA. "
            "Check out a9d4c61d04f2a4a5f92cb6947442d8173079454c in a detached worktree."
        )
    pin = match.group(1)
    lock = buddy_root / "uv.lock"
    if lock.is_file():
        lock_match = LOCK_PIN_RE.search(lock.read_text(encoding="utf-8"))
        if lock_match is None or lock_match.group(1) != pin:
            raise AnchorMismatchError(
                "Buddy uv.lock DungeonMind pin does not match pyproject.toml. "
                "Use a detached worktree at the exact K0.1 Buddy anchor."
            )
    return pin


def read_buddy_dungeonmind_pin_at_ref(buddy_root: Path, ref: str) -> str:
    """Read Buddy's DungeonMind pin from an exact git tree, not the worktree."""
    py_result = subprocess.run(
        ["git", "-C", str(buddy_root), "show", f"{ref}:pyproject.toml"],
        check=False,
        capture_output=True,
        text=True,
    )
    if py_result.returncode != 0:
        raise AnchorMismatchError(
            f"Buddy ref {ref} has no readable pyproject.toml: {py_result.stderr.strip()}"
        )
    match = PIN_RE.search(py_result.stdout)
    if match is None:
        raise AnchorMismatchError(
            f"Buddy pyproject.toml at {ref} does not pin DungeonMind to an exact git SHA."
        )
    pin = match.group(1)
    lock_result = subprocess.run(
        ["git", "-C", str(buddy_root), "show", f"{ref}:uv.lock"],
        check=False,
        capture_output=True,
        text=True,
    )
    if lock_result.returncode == 0:
        lock_match = LOCK_PIN_RE.search(lock_result.stdout)
        if lock_match is None or lock_match.group(1) != pin:
            raise AnchorMismatchError(
                f"Buddy uv.lock at {ref} DungeonMind pin does not match pyproject.toml."
            )
    return pin


def verify_dungeonmind_code_anchor(root: Path, expected: str) -> None:
    changed = git_diff_names(
        root,
        expected,
        ["src", "migrations", "alembic", "alembic.ini", "pyproject.toml", "uv.lock"],
    )
    if changed:
        raise AnchorMismatchError(
            "DungeonMind source/schema/dependency files differ from code anchor "
            f"{expected}. Changed:\n" + "\n".join(changed) + "\n"
            "K0.1 must inventory that exact tree; do not scan a drifted checkout."
        )


def verify_buddy_anchor(
    buddy_root: Path,
    expected_anchor: str,
    expected_pin: str,
) -> str:
    # Evidence is scanned from the exact git tree at expected_anchor; only require
    # that object to exist (do not trust a dirty or wrong HEAD checkout).
    result = subprocess.run(
        [
            "git",
            "-C",
            str(buddy_root),
            "rev-parse",
            "--verify",
            f"{expected_anchor}^{{commit}}",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AnchorMismatchError(
            f"Buddy repo does not contain required anchor {expected_anchor}. "
            f"{result.stderr.strip()}"
        )
    pin = read_buddy_dungeonmind_pin_at_ref(buddy_root, expected_anchor)
    if pin != expected_pin:
        raise AnchorMismatchError(
            f"Buddy at {expected_anchor} pins DungeonMind {pin}, expected {expected_pin}."
        )
    return pin


RUNTIME_TREE_PATHS = ("src", "migrations", "alembic.ini", "pyproject.toml", "uv.lock")

# Paths used for export/graph/repo/table/exception/optional-probe facts.
# Must be read from the exact runtime-anchor tree, never the mutable worktree.
DUNGEONMIND_FACT_SCAN_PATHS = (
    "src",
    "migrations",
    "tests/unit/test_import_boundaries.py",
)


def runtime_tree_digest(root: Path, anchor: str) -> str:
    """Stable digest of the audited runtime tree at the exact code anchor."""

    import hashlib

    hasher = hashlib.sha256()
    for rel in RUNTIME_TREE_PATHS:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", f"{anchor}:{rel}"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise AnchorMismatchError(
                f"unable to resolve runtime tree path {rel} at anchor {anchor}: "
                f"{result.stderr.strip()}"
            )
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(result.stdout.strip().encode("utf-8"))
        hasher.update(b"\n")
    return f"sha256:{hasher.hexdigest()}"


def dungeonmind_fact_corpus_digest(root: Path, ref: str) -> str:
    """Digest of DungeonMind fact-scan paths (src/migrations/boundary test) at ref."""

    import hashlib

    hasher = hashlib.sha256()
    for rel in DUNGEONMIND_FACT_SCAN_PATHS:
        oid = git_blob_oid(root, ref, rel)
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(oid.encode("utf-8"))
        hasher.update(b"\n")
    return f"sha256:{hasher.hexdigest()}"


@contextmanager
def materialize_git_tree(
    root: Path,
    ref: str,
    paths: tuple[str, ...] = DUNGEONMIND_FACT_SCAN_PATHS,
) -> Iterator[Path]:
    """Extract an exact git tree into a temporary directory for path-based scanners.

    Untracked or dirty worktree files under ``root`` cannot appear in the result.
    """
    tmp = Path(tempfile.mkdtemp(prefix="k0-dm-fact-tree-"))
    try:
        archive = subprocess.run(
            ["git", "-C", str(root), "archive", "--format=tar", ref, "--", *paths],
            check=False,
            capture_output=True,
        )
        if archive.returncode != 0:
            raise AnchorMismatchError(
                f"unable to archive {ref} paths {paths}: "
                f"{archive.stderr.decode('utf-8', errors='replace').strip()}"
            )
        extract = subprocess.run(
            ["tar", "-x", "-C", str(tmp)],
            check=False,
            input=archive.stdout,
            capture_output=True,
        )
        if extract.returncode != 0:
            raise AnchorMismatchError(
                f"unable to extract archived tree at {ref}: "
                f"{extract.stderr.decode('utf-8', errors='replace').strip()}"
            )
        yield tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _is_dm_module(name: str) -> bool:
    return bool(DM_MODULE_RE.fullmatch(name))


def _call_func_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _constant_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


@dataclass(frozen=True)
class ImportRecord:
    consumer_file: str
    imported_module: str
    imported_symbols: list[str]
    import_form: str
    in_type_checking: bool
    dynamic: bool
    line: int


def _type_checking_scopes(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        names: list[str] = []
        if isinstance(test, ast.Name):
            names.append(test.id)
        elif isinstance(test, ast.Attribute):
            names.append(test.attr)
        if "TYPE_CHECKING" in names:
            for child in node.body:
                ids.add(id(child))
                for walked in ast.walk(child):
                    ids.add(id(walked))
    return ids


def scan_source_imports(
    relative: str,
    source: str,
) -> tuple[list[ImportRecord], list[dict[str, Any]]]:
    try:
        tree = ast.parse(source, filename=relative)
    except SyntaxError as exc:
        return [], [
            {
                "consumer_file": relative,
                "kind": "syntax_error",
                "detail": str(exc),
            }
        ]
    type_checking = _type_checking_scopes(tree)
    records: list[ImportRecord] = []
    dynamic_findings: list[dict[str, Any]] = []

    for node in ast.walk(tree):
        in_tc = id(node) in type_checking
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_dm_module(alias.name):
                    records.append(
                        ImportRecord(
                            consumer_file=relative,
                            imported_module=alias.name,
                            imported_symbols=[],
                            import_form="import",
                            in_type_checking=in_tc,
                            dynamic=False,
                            line=node.lineno,
                        )
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level == 0 and _is_dm_module(module):
                symbols = sorted(alias.name for alias in node.names)
                records.append(
                    ImportRecord(
                        consumer_file=relative,
                        imported_module=module,
                        imported_symbols=symbols,
                        import_form="from",
                        in_type_checking=in_tc,
                        dynamic=False,
                        line=node.lineno,
                    )
                )
        elif isinstance(node, ast.Call):
            func_name = _call_func_name(node.func)
            if func_name not in {"import_module", "__import__", "run_module"}:
                continue
            if not node.args:
                continue
            value = _constant_str(node.args[0])
            if value and _is_dm_module(value):
                records.append(
                    ImportRecord(
                        consumer_file=relative,
                        imported_module=value,
                        imported_symbols=[],
                        import_form="dynamic",
                        in_type_checking=in_tc,
                        dynamic=True,
                        line=node.lineno,
                    )
                )
                dynamic_findings.append(
                    {
                        "consumer_file": relative,
                        "kind": "dynamic_import_call",
                        "function": func_name,
                        "imported_module": value,
                        "line": node.lineno,
                    }
                )
    return records, dynamic_findings


def scan_file_imports(
    path: Path, repo_root: Path
) -> tuple[list[ImportRecord], list[dict[str, Any]]]:
    source = path.read_text(encoding="utf-8")
    relative = path.relative_to(repo_root).as_posix()
    return scan_source_imports(relative, source)


def git_ls_tree_paths(root: Path, ref: str) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-tree", "-r", "--name-only", ref],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AnchorMismatchError(
            f"unable to list tree at {ref}: {result.stderr.strip()}"
        )
    return [line for line in result.stdout.splitlines() if line.strip()]


def git_show_text(root: Path, ref: str, relative: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(root), "show", f"{ref}:{relative}"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return None


def git_blob_oid(root: Path, ref: str, relative: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", f"{ref}:{relative}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AnchorMismatchError(
            f"unable to resolve {relative} at {ref}: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def scan_buddy_imports_at_git_ref(
    root: Path,
    ref: str,
) -> tuple[list[ImportRecord], list[dict[str, Any]], str]:
    """Scan Buddy Python imports from an exact git tree, not the worktree."""
    import hashlib

    paths = [
        p
        for p in git_ls_tree_paths(root, ref)
        if p.endswith(".py")
        and not any(part in SKIP_DIR_NAMES for part in p.split("/")[:-1])
    ]
    hasher = hashlib.sha256()
    records: list[ImportRecord] = []
    dynamic_findings: list[dict[str, Any]] = []
    for relative in paths:
        oid = git_blob_oid(root, ref, relative)
        hasher.update(relative.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(oid.encode("utf-8"))
        hasher.update(b"\n")
        text = git_show_text(root, ref, relative)
        if text is None:
            continue
        file_records, extras = scan_source_imports(relative, text)
        records.extend(file_records)
        dynamic_findings.extend(extras)
    return records, dynamic_findings, f"sha256:{hasher.hexdigest()}"


def consumer_kind(path: str) -> str:
    if path.startswith("tests/") or "/tests/" in path or Path(path).name.startswith("test_"):
        return "test"
    if path.startswith("apps/"):
        return "production"
    if path.startswith(("scripts/", "tools/", "evals/")):
        return "tooling"
    return "other"


def module_file(src_root: Path, module: str) -> Path | None:
    rel = Path(*module.split("."))
    candidate = src_root / rel.with_suffix(".py")
    if candidate.is_file():
        return candidate
    init = src_root / rel / "__init__.py"
    if init.is_file():
        return init
    return None


def defined_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
                    if target.id == "__all__" and isinstance(node.value, (ast.List, ast.Tuple)):
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                names.add(elt.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


def resolve_import(src_root: Path, module: str, symbols: list[str]) -> bool:
    path = module_file(src_root, module)
    if path is None:
        return False
    if not symbols or symbols == ["*"]:
        return True
    names = defined_names(path)
    for symbol in symbols:
        if symbol in names:
            continue
        if path.name == "__init__.py":
            submodule = module_file(src_root, f"{module}.{symbol}")
            if submodule is not None:
                continue
        return False
    return True


@dataclass
class ExportRecord:
    package: str
    module: str
    name: str
    origin: str
    in_all: bool


def inventory_explicit_exports(src_root: Path) -> list[ExportRecord]:
    records: list[ExportRecord] = []
    for package in ("dungeonmind", "dungeonmind_dnd"):
        pkg_root = src_root / package
        if not pkg_root.is_dir():
            continue
        for init in sorted(pkg_root.rglob("__init__.py")):
            module_parts = init.relative_to(src_root).with_suffix("").parts
            if module_parts[-1] == "__init__":
                module_parts = module_parts[:-1]
            module = ".".join(module_parts)
            tree = ast.parse(init.read_text(encoding="utf-8"), filename=str(init))
            exported_all: set[str] | None = None
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if (
                            isinstance(target, ast.Name)
                            and target.id == "__all__"
                            and isinstance(node.value, (ast.List, ast.Tuple))
                        ):
                            exported_all = {
                                elt.value
                                for elt in node.value.elts
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                            }
            reexports: list[tuple[str, str]] = []
            for node in tree.body:
                if isinstance(node, ast.ImportFrom) and node.module:
                    origin_module = node.module
                    if node.level:
                        pkg = module.split(".")
                        base = pkg[: len(pkg) - (node.level - 1)]
                        origin_module = ".".join([*base, *node.module.split(".")])
                    elif not node.module.startswith(("dungeonmind", "dungeonmind_dnd")):
                        if node.module.startswith("."):
                            origin_module = f"{module}{node.module}"
                        else:
                            origin_module = f"{module}.{node.module}"
                    for alias in node.names:
                        name = alias.asname or alias.name
                        if name == "*":
                            continue
                        reexports.append((name, origin_module))
            cheap_root = module in {"dungeonmind", "dungeonmind_dnd"}
            if exported_all is None and not reexports and cheap_root:
                # Cheap root packages export only __version__ if present.
                names = defined_names(init)
                if "__version__" in names:
                    records.append(
                        ExportRecord(
                            package=package,
                            module=module,
                            name="__version__",
                            origin=module,
                            in_all=False,
                        )
                    )
                continue
            for name, origin in reexports:
                if exported_all is not None and name not in exported_all:
                    # Still an explicit re-export at package import time.
                    pass
                records.append(
                    ExportRecord(
                        package=package,
                        module=module,
                        name=name,
                        origin=origin,
                        in_all=exported_all is None or name in exported_all,
                    )
                )
            if exported_all is not None:
                present = {row.name for row in records if row.module == module}
                for name in sorted(exported_all - present):
                    records.append(
                        ExportRecord(
                            package=package,
                            module=module,
                            name=name,
                            origin=module,
                            in_all=True,
                        )
                    )
    records.sort(key=lambda row: (row.package, row.module, row.name))
    return records


def parse_imports_of_module(path: Path, module_name: str) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    is_init = path.name == "__init__.py"
    package_parts = module_name.split(".") if is_init else module_name.split(".")[:-1]
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    modules.append(node.module)
                continue
            base = package_parts[: len(package_parts) - (node.level - 1)]
            if node.module:
                base = [*base, *node.module.split(".")]
            if base:
                modules.append(".".join(base))
    return _sorted_unique(modules)


def source_module_name(src_root: Path, path: Path) -> str:
    rel = path.relative_to(src_root).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def internal_import_graph(src_root: Path) -> dict[str, list[str]]:
    graph: dict[str, list[str]] = {}
    for path in iter_python_files(src_root):
        try:
            module = source_module_name(src_root, path)
        except ValueError:
            continue
        imports = [
            item
            for item in parse_imports_of_module(path, module)
            if _is_dm_module(item)
        ]
        graph[module] = imports
    return dict(sorted((key, value) for key, value in graph.items()))


def reachable(graph: dict[str, list[str]], seeds: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    stack = list(seeds)
    while stack:
        module = stack.pop()
        if module in seen:
            continue
        seen.add(module)
        for imported in graph.get(module, []):
            if imported not in seen:
                stack.append(imported)
    return sorted(seen)


def inventory_repository_protocols(src_root: Path) -> list[dict[str, Any]]:
    path = src_root / "dungeonmind" / "application" / "repositories.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    rows: list[dict[str, Any]] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        base_names = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_names.append(base.id)
            elif isinstance(base, ast.Attribute):
                base_names.append(base.attr)
        if "Protocol" not in base_names:
            continue
        rows.append(
            {
                "id": node.name,
                "kind": "protocol",
                "defining_symbol": node.name,
                "defining_path": "src/dungeonmind/application/repositories.py",
            }
        )
    postgres_init = src_root / "dungeonmind" / "infrastructure" / "postgres" / "__init__.py"
    postgres_tree = ast.parse(postgres_init.read_text(encoding="utf-8"))
    for node in postgres_tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "PostgresRepositoryBundle":
            members: list[str] = []
            for item in node.body:
                if not isinstance(item, ast.FunctionDef) or item.name != "__init__":
                    continue
                for stmt in item.body:
                    if not isinstance(stmt, ast.Assign):
                        continue
                    for target in stmt.targets:
                        if (
                            isinstance(target, ast.Attribute)
                            and isinstance(target.value, ast.Name)
                            and target.value.id == "self"
                        ):
                            members.append(target.attr)
            rows.append(
                {
                    "id": "PostgresRepositoryBundle",
                    "kind": "bundle",
                    "defining_symbol": "PostgresRepositoryBundle",
                    "defining_path": "src/dungeonmind/infrastructure/postgres/__init__.py",
                    "members": members,
                }
            )
    rows.sort(key=lambda row: str(row["id"]))
    return rows


def inventory_alembic_tables(migrations_root: Path) -> list[dict[str, str]]:
    versions = migrations_root / "versions"
    found: dict[str, str] = {}
    for path in sorted(versions.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for match in CREATE_TABLE_RE.finditer(text):
            table = match.group(1)
            found.setdefault(table, path.name)
    return [
        {"id": name, "creation_migration": found[name]}
        for name in sorted(found)
    ]


def parse_assign_set(tree: ast.AST, name: str) -> list[str]:
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            continue
        values: list[str] = []
        target_value = node.value
        elts: list[ast.expr] = []
        if isinstance(target_value, ast.Set):
            elts = list(target_value.elts)
        elif (
            isinstance(target_value, ast.Call)
            and isinstance(target_value.func, ast.Name)
            and target_value.func.id == "frozenset"
            and target_value.args
            and isinstance(target_value.args[0], (ast.Set, ast.List))
        ):
            elts = list(target_value.args[0].elts)
        elif isinstance(target_value, ast.BinOp) and isinstance(target_value.op, ast.BitOr):
            # DND_*_ALLOWED = BASE | { ... } handled elsewhere.
            continue
        for elt in elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                values.append(elt.value)
        return sorted(values)
    return []


def inventory_import_boundary_exceptions(test_path: Path) -> list[dict[str, Any]]:
    tree = ast.parse(test_path.read_text(encoding="utf-8"), filename=str(test_path))
    constants = {
        "FORBIDDEN_ROOTS": parse_assign_set(tree, "FORBIDDEN_ROOTS"),
        "POSTGRES_ONLY_ROOTS": parse_assign_set(tree, "POSTGRES_ONLY_ROOTS"),
        "API_ONLY_ROOTS": parse_assign_set(tree, "API_ONLY_ROOTS"),
        "DND_PLANNING_MODULES": parse_assign_set(tree, "DND_PLANNING_MODULES"),
        "DND_REVIEW_MODULES": parse_assign_set(tree, "DND_REVIEW_MODULES"),
        "DND_MECHANICS_MODULES": parse_assign_set(tree, "DND_MECHANICS_MODULES"),
        "DND_TRANSPORT_MODULES": parse_assign_set(tree, "DND_TRANSPORT_MODULES"),
        "DND_RESOURCE_MODULES": parse_assign_set(tree, "DND_RESOURCE_MODULES"),
    }
    layer_allows_agents = False
    for node in tree.body:
        if not isinstance(node, ast.AnnAssign):
            continue
        if not (isinstance(node.target, ast.Name) and node.target.id == "LAYER_RULES"):
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        for key, value in zip(node.value.keys, node.value.values, strict=True):
            key_s = _constant_str(key) if key is not None else None
            if key_s == "dungeonmind.application" and isinstance(value, ast.Set):
                layer_allows_agents = any(
                    _constant_str(elt) == "dungeonmind.agents" for elt in value.elts
                )
    rows = [
        {
            "id": "application_agents_mutual_allowance",
            "source": "tests/unit/test_import_boundaries.py",
            "kind": "layer_rule",
            "detail": "dungeonmind.application may import dungeonmind.agents",
            "present": layer_allows_agents,
        },
        {
            "id": "postgres_only_roots",
            "source": "tests/unit/test_import_boundaries.py",
            "kind": "optional_root_allowlist",
            "members": constants["POSTGRES_ONLY_ROOTS"],
        },
        {
            "id": "api_only_roots",
            "source": "tests/unit/test_import_boundaries.py",
            "kind": "optional_root_allowlist",
            "members": constants["API_ONLY_ROOTS"],
        },
        {
            "id": "forbidden_roots",
            "source": "tests/unit/test_import_boundaries.py",
            "kind": "forbidden_roots",
            "members": constants["FORBIDDEN_ROOTS"],
        },
        {
            "id": "dnd_planning_allowlist",
            "source": "tests/unit/test_import_boundaries.py",
            "kind": "dnd_path_exception",
            "members": constants["DND_PLANNING_MODULES"],
        },
        {
            "id": "dnd_review_allowlist",
            "source": "tests/unit/test_import_boundaries.py",
            "kind": "dnd_path_exception",
            "members": constants["DND_REVIEW_MODULES"],
        },
        {
            "id": "dnd_mechanics_allowlist",
            "source": "tests/unit/test_import_boundaries.py",
            "kind": "dnd_path_exception",
            "members": constants["DND_MECHANICS_MODULES"],
        },
        {
            "id": "dnd_transport_allowlist",
            "source": "tests/unit/test_import_boundaries.py",
            "kind": "dnd_path_exception",
            "members": constants["DND_TRANSPORT_MODULES"],
        },
        {
            "id": "dnd_resource_allowlist",
            "source": "tests/unit/test_import_boundaries.py",
            "kind": "dnd_path_exception",
            "members": constants["DND_RESOURCE_MODULES"],
        },
    ]
    return rows


def probe_optional_dependency_loads(dungeonmind_root: Path) -> dict[str, Any]:
    src = dungeonmind_root / "src"
    code = r"""
import json, sys
forbidden = (
    "psycopg", "pgvector", "fastapi", "uvicorn", "starlette", "httpx",
    "torch", "sentence_transformers", "openai", "alembic", "sqlalchemy",
    "dungeonmind.infrastructure.postgres", "dungeonmind.service.api",
    "dungeonmind.service.bootstrap",
)
def snap(label):
    loaded = [name for name in forbidden if name in sys.modules]
    dnd = "dungeonmind_dnd" in sys.modules
    return {"label": label, "loaded_heavy_or_optional": loaded, "dungeonmind_dnd_loaded": dnd}
out = []
import dungeonmind
out.append(snap("import dungeonmind"))
import dungeonmind_dnd
out.append(snap("import dungeonmind_dnd"))
print(json.dumps(out))
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(src) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(dungeonmind_root),
        env=env,
    )
    if result.returncode != 0:
        return {
            "ok": False,
            "stderr": result.stderr.strip(),
            "probes": [],
        }
    probes = json.loads(result.stdout)
    return {"ok": True, "probes": probes}


def dump_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
