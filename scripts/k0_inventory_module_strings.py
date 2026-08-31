"""Conservative module-string and deployment-entry scanning for K0.1."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

from k0_inventory_scan import (
    SKIP_DIR_NAMES,
    _is_dm_module,
    git_blob_oid,
    git_ls_tree_paths,
    git_show_text,
)

SCAN_SUFFIXES = {
    ".py",
    ".toml",
    ".yml",
    ".yaml",
    ".sh",
    ".json",
    ".md",
}
SCAN_BASENAMES = {
    "Dockerfile",
    "docker-compose.yml",
    "compose.postgres.yml",
    "compose.yml",
}
MODULE_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_])(dungeonmind(?:_dnd)?(?:\.[A-Za-z_][A-Za-z0-9_]*)*)(?![A-Za-z0-9_])"
)
UVICORN_TARGET_RE = re.compile(
    r"uvicorn[^\n#;]*?\b([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+:[A-Za-z0-9_]+)"
)
PYTHON_DASH_M_RE = re.compile(r"python(?:3)?\s+-m\s+([A-Za-z0-9_.]+)")
PYPROJECT_SCRIPT_RE = re.compile(
    r"^\s*([A-Za-z0-9_-]+)\s*=\s*\"([^\"]+)\"",
    re.MULTILINE,
)


SKIP_RELATIVE_PATHS = {
    "Docs/Reports/K0-surface-inventory.json",
    "Docs/Reports/K0-current-consumer-public-surface-v1.json",
}


def should_scan_relative(relative: str) -> bool:
    if relative in SKIP_RELATIVE_PATHS:
        return False
    if relative.startswith("Docs/Reports/") and relative.endswith(".json"):
        return False
    parts = relative.split("/")
    if any(part in SKIP_DIR_NAMES for part in parts[:-1]):
        return False
    name = parts[-1]
    if name in SCAN_BASENAMES or name.startswith("Dockerfile"):
        return True
    return Path(relative).suffix in SCAN_SUFFIXES


def iter_scan_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in SKIP_DIR_NAMES)
        for name in sorted(filenames):
            path = Path(dirpath) / name
            relative = path.relative_to(root).as_posix()
            if should_scan_relative(relative):
                files.append(path)
    return files


def _consumer_kind(relative: str) -> str:
    if relative.startswith("scripts/k0_"):
        return "inventory_tooling"
    if relative.startswith((".github/", "benchmarks/", "scripts/")):
        return "deployment_or_tooling"
    if relative.startswith("Docs/Runbooks/"):
        return "documented_deployment"
    if relative.startswith(("Docs/Reports/", "Docs/Handoffs/", "Docs/Architecture/")):
        return "documentation"
    if relative.startswith("tests/") or "/tests/" in relative:
        return "test"
    if relative.startswith("apps/"):
        return "production"
    return "other"


def _findings_from_text(relative: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    kind = _consumer_kind(relative)
    name = relative.rsplit("/", 1)[-1]
    for line_no, line in enumerate(text.splitlines(), start=1):
        for match in MODULE_TOKEN_RE.finditer(line):
            module = match.group(1)
            if not _is_dm_module(module):
                continue
            findings.append(
                {
                    "consumer_file": relative,
                    "consumer_kind": kind,
                    "kind": "module_string_reference",
                    "imported_module": module,
                    "line": line_no,
                    "context": line.strip()[:240],
                }
            )
        for match in UVICORN_TARGET_RE.finditer(line):
            target = match.group(1)
            module = target.split(":", 1)[0]
            if not _is_dm_module(module):
                continue
            findings.append(
                {
                    "consumer_file": relative,
                    "consumer_kind": kind,
                    "kind": "uvicorn_factory_target",
                    "imported_module": module,
                    "target": target,
                    "line": line_no,
                    "context": line.strip()[:240],
                }
            )
        for match in PYTHON_DASH_M_RE.finditer(line):
            module = match.group(1)
            if not _is_dm_module(module):
                continue
            findings.append(
                {
                    "consumer_file": relative,
                    "consumer_kind": kind,
                    "kind": "python_dash_m",
                    "imported_module": module,
                    "line": line_no,
                    "context": line.strip()[:240],
                }
            )
    if name == "pyproject.toml":
        for match in PYPROJECT_SCRIPT_RE.finditer(text):
            script_name, value = match.group(1), match.group(2)
            module_hit = MODULE_TOKEN_RE.search(value)
            if module_hit is None:
                continue
            module = module_hit.group(1)
            if not _is_dm_module(module):
                continue
            findings.append(
                {
                    "consumer_file": relative,
                    "consumer_kind": kind,
                    "kind": "pyproject_script",
                    "script_name": script_name,
                    "imported_module": module,
                    "line": text[: match.start()].count("\n") + 1,
                    "context": value.strip()[:240],
                }
            )
    return findings


def _sort_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings.sort(
        key=lambda row: (
            str(row.get("consumer_file")),
            int(row.get("line") or 0),
            str(row.get("kind")),
            str(row.get("imported_module")),
        )
    )
    return findings


def scan_module_string_references(root: Path) -> list[dict[str, Any]]:
    """Scan a filesystem tree (Buddy exact checkout)."""
    findings: list[dict[str, Any]] = []
    for path in iter_scan_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        relative = path.relative_to(root).as_posix()
        findings.extend(_findings_from_text(relative, text))
    return _sort_findings(findings)


def scan_module_string_references_at_git_ref(
    root: Path,
    ref: str,
) -> tuple[list[dict[str, Any]], str]:
    """Scan module-string evidence from an exact git tree, not the worktree.

    Returns (findings, corpus_digest) where corpus_digest is a stable digest of
    the scanned path list + blob OIDs at ``ref``. Declared ledger inputs must
    include this digest so report/runbook edits on the PR branch cannot mutate
    the evidence without changing inputs.
    """
    paths = [p for p in git_ls_tree_paths(root, ref) if should_scan_relative(p)]
    hasher = hashlib.sha256()
    findings: list[dict[str, Any]] = []
    for relative in paths:
        oid = git_blob_oid(root, ref, relative)
        hasher.update(relative.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(oid.encode("utf-8"))
        hasher.update(b"\n")
        text = git_show_text(root, ref, relative)
        if text is None:
            continue
        findings.extend(_findings_from_text(relative, text))
    return _sort_findings(findings), f"sha256:{hasher.hexdigest()}"


def module_string_hits_cover(cover: str, module: str) -> bool:
    if ":" in cover:
        mod, _symbol = cover.split(":", 1)
        return module == mod or module.startswith(f"{mod}.")
    return module == cover or module.startswith(f"{cover}.")


def _is_actionable_module_string_hit(row: dict[str, Any]) -> bool:
    return row.get("consumer_kind") in {
        "production",
        "deployment_or_tooling",
        "documented_deployment",
    }


def downgrade_unused_for_module_strings(
    subsystems: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Downgrade UNUSED rows when deployment/module-string evidence references their cover."""
    notes: list[str] = []
    actionable = [row for row in findings if _is_actionable_module_string_hit(row)]
    updated: list[dict[str, Any]] = []
    for row in subsystems:
        item = dict(row)
        if item.get("disposition") != "UNUSED":
            updated.append(item)
            continue
        covers = [str(x) for x in item.get("covers") or []]
        hits = [
            f"{hit['consumer_file']}:{hit['imported_module']}"
            for hit in actionable
            for cover in covers
            if module_string_hits_cover(cover, str(hit.get("imported_module") or ""))
        ]
        if hits:
            ident = str(item.get("id"))
            item["disposition"] = "UNKNOWN"
            item["blocking_question"] = (
                "Non-static deployment/module-string evidence references this cover at "
                f"{sorted(set(hits))[0]}. Expand consumer proof or reclassify before K1."
            )
            item.pop("falsification_note", None)
            notes.append(f"downgraded {ident} to UNKNOWN due to module-string hit(s)")
        updated.append(item)
    return updated, notes
