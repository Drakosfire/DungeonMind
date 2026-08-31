"""Load human-authored K0.1 dispositions from TOML."""

from __future__ import annotations

import hashlib
import tomllib
from pathlib import Path
from typing import Any

DEFAULT_DISPOSITIONS_PATH = (
    Path(__file__).resolve().parents[1] / "Docs" / "Inventory" / "K0-dispositions.toml"
)


def _normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    out = dict(item)
    if "falsification" in out and "falsification_note" not in out:
        out["falsification_note"] = str(out.pop("falsification")).strip()
    return out


def load_dispositions(path: Path | None = None) -> dict[str, Any]:
    target = path or DEFAULT_DISPOSITIONS_PATH
    raw = tomllib.loads(target.read_text(encoding="utf-8"))
    meta = dict(raw.get("meta") or {})
    repositories = [_normalize_item(row) for row in raw.get("repository") or []]
    tables = [_normalize_item(row) for row in raw.get("table") or []]
    exceptions = [_normalize_item(row) for row in raw.get("import_boundary_exception") or []]
    subsystems = [_normalize_item(row) for row in raw.get("subsystem") or []]
    baselines = [_normalize_item(row) for row in raw.get("known_red_baseline") or []]
    return {
        "meta": meta,
        "repository_overlays": {str(row["id"]): row for row in repositories},
        "table_overlays": {str(row["id"]): row for row in tables},
        "exception_overlays": {str(row["id"]): row for row in exceptions},
        "subsystem_dispositions": subsystems,
        "known_red_baselines": baselines,
    }


def dispositions_digest(path: Path | None = None) -> str:
    target = path or DEFAULT_DISPOSITIONS_PATH
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    return f"sha256:{digest}"
