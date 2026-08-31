"""K0.2 semantic normalization policy and witness digests.

Fields are classified as SEMANTIC, OBSERVATION_ONLY, or FORBIDDEN_NONDETERMINISM.
Only SEMANTIC content participates in golden equality.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

WITNESS_SCHEMA = "dm_k0_semantic_witness_v1"
K0_INVENTORY_SCHEMA = "dm_k0_surface_inventory_v1"

# Absolute paths, DSNs, and wall-clock fields must never appear in semantic payloads.
FORBIDDEN_KEY_FRAGMENTS = (
    "projected_at",
    "wall_clock",
    "duration_ms",
    "elapsed_ms",
    "trace_id",
    "span_id",
    "process_id",
    "pid",
    "database_url",
    "connection_string",
    "dsn",
    "local_path",
    "absolute_path",
    "cwd",
    "hostname",
    "machine",
)

OBSERVATION_ONLY_KEYS = frozenset(
    {
        "projected_at",
        "created_at",
        "updated_at",
        "published_at",
        "adopted_at",
        "repaired_at",
        "initialized_at",
        "duration_ms",
        "elapsed_ms",
        "wall_clock_ms",
        "trace_id",
        "span_id",
        "cache_hit",
        "projection_count",
        "observation",
    }
)

ABS_PATH_RE = re.compile(r"(^|/)(home|Users|tmp|var/folders)/")
DSN_RE = re.compile(r"postgresql(\+psycopg)?://|sqlite:///", re.IGNORECASE)

REQUIRED_OPERATION_IDS: tuple[str, ...] = (
    "read.head_projection",
    "read.exact_historical_revision",
    "read.exact_object",
    "read.deterministic_search",
    "read.neighborhood.depth_1",
    "read.neighborhood.depth_2",
    "read.evidence",
    "read.source_anchor.emit",
    "read.source_anchor.revalidate",
    "scope.gm_campaign",
    "scope.player_campaign",
    "scope.world_owned",
    "scope.cross_campaign",
    "failure.missing_object",
    "failure.missing_revision",
    "failure.missing_head",
    "failure.provenance_invalid_fail_closed",
    "write.reviewed_first_world_initialization",
    "write.exact_parent_publication",
    "write.stale_parent_rejection",
    "write.exact_replay_idempotency",
    "write.outcome_unknown_recovery",
    "write.correction_or_retraction",
    "write.source_evidence_binding_integrity",
)

NORMALIZATION_POLICY: dict[str, Any] = {
    "id": "k0_semantic_normalization_v1",
    "classes": {
        "SEMANTIC": [
            "world_id",
            "campaign_id",
            "scope_mode",
            "admissibility",
            "revision_id",
            "parent_revision_id",
            "expected_parent_revision_id",
            "head_revision_id",
            "published_revision_id",
            "object_id",
            "object_ids",
            "relationship_ids",
            "assertion_ids",
            "evidence_ref_ids",
            "source_artifact_id",
            "source_revision_id",
            "anchor_id",
            "labels",
            "aliases",
            "predicates",
            "visibility",
            "coverage",
            "fail_closed",
            "status",
            "error_type",
            "error_code",
            "disposition",
            "graph_schema",
            "semantic_profile",
            "binding_integrity",
        ],
        "OBSERVATION_ONLY": sorted(OBSERVATION_ONLY_KEYS),
        "FORBIDDEN_NONDETERMINISM": [
            "absolute filesystem paths",
            "database DSNs / connection strings",
            "wall-clock timestamps in equality keys",
            "trace/span/process identifiers",
            "full exception message prose (unless declared semantic)",
        ],
    },
    "rules": [
        "Model dumps are converted to plain JSON-compatible structures.",
        "Observation-only keys are dropped recursively.",
        "Lists of mappings are sorted by a stable JSON dump of each item.",
        "Dict keys are sorted at dump time (canonical JSON).",
        "Error results keep error_type and selected identity fields only.",
        "Exception message text is omitted unless explicitly declared semantic.",
    ],
}


def dump_canonical_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_canonical(payload: Any) -> str:
    return sha256_text(dump_canonical_json(payload))


def normalization_policy_digest() -> str:
    return f"sha256:{sha256_canonical(NORMALIZATION_POLICY)}"


def file_digest(path: Path) -> str:
    return f"sha256:{sha256_bytes(path.read_bytes())}"


def _to_plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _to_plain(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(k): _to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(v) for v in value]
    if isinstance(value, set):
        return sorted(_to_plain(v) for v in value)
    if isinstance(value, Path):
        return value.as_posix()
    return value


def _is_observation_key(key: str) -> bool:
    lowered = key.lower()
    if lowered in OBSERVATION_ONLY_KEYS:
        return True
    return any(frag in lowered for frag in ("_at", "duration", "elapsed", "trace", "span"))


def strip_observation_only(value: Any) -> Any:
    plain = _to_plain(value)
    if isinstance(plain, dict):
        out: dict[str, Any] = {}
        for key, item in plain.items():
            if _is_observation_key(str(key)):
                continue
            out[str(key)] = strip_observation_only(item)
        return out
    if isinstance(plain, list):
        cleaned = [strip_observation_only(item) for item in plain]
        if cleaned and all(isinstance(item, dict) for item in cleaned):
            return sorted(cleaned, key=lambda item: dump_canonical_json(item))
        if cleaned and all(
            isinstance(item, (str, int, float, bool)) or item is None for item in cleaned
        ):
            return sorted(cleaned, key=lambda item: dump_canonical_json(item))
        return cleaned
    return plain


def normalize_semantic(value: Any) -> Any:
    """Public normalization entry point for witness semantic payloads."""
    return strip_observation_only(value)


def normalize_error(exc: BaseException, *, bound: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "error_type": type(exc).__name__,
    }
    details = getattr(exc, "details", None)
    if isinstance(details, dict):
        # Keep stable identity-bearing detail keys only.
        kept = {
            key: value
            for key, value in details.items()
            if key
            in {
                "reason",
                "world_id",
                "revision_id",
                "expected_parent_revision_id",
                "parent_revision_id",
                "object_id",
                "review_id",
                "publication_id",
                "initialization_id",
                "adoption_id",
            }
        }
        if kept:
            payload["details"] = normalize_semantic(kept)
    if bound:
        payload["bound"] = normalize_semantic(bound)
    return payload


def find_forbidden_nondeterminism(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_s = str(key)
            lowered = key_s.lower()
            child = f"{path}.{key_s}"
            if any(frag in lowered for frag in FORBIDDEN_KEY_FRAGMENTS):
                hits.append(child)
            hits.extend(find_forbidden_nondeterminism(item, child))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            hits.extend(find_forbidden_nondeterminism(item, f"{path}[{idx}]"))
    elif isinstance(value, str):
        if ABS_PATH_RE.search(value) or (value.startswith("/") and "/Projects/" in value):
            hits.append(path)
        if DSN_RE.search(value):
            hits.append(path)
    return hits


class WitnessValidationError(ValueError):
    """Raised when a witness ledger is unsafe as a K2.5 oracle."""


def validate_witness(witness: dict[str, Any]) -> None:
    errors: list[str] = []
    if witness.get("schema") != WITNESS_SCHEMA:
        errors.append(f"schema must be {WITNESS_SCHEMA}")
    for key in (
        "inputs",
        "normalization_policy",
        "fixture",
        "operations",
        "historical_compatibility",
        "aggregate_semantic_sha256",
    ):
        if key not in witness:
            errors.append(f"missing top-level key {key!r}")

    operations = list(witness.get("operations") or [])
    ids = [str(row.get("id") or "") for row in operations]
    if len(ids) != len(set(ids)):
        seen: set[str] = set()
        for ident in ids:
            if ident in seen:
                errors.append(f"duplicate operation id: {ident}")
            seen.add(ident)
    present = set(ids)
    for required in REQUIRED_OPERATION_IDS:
        if required not in present:
            errors.append(f"missing required operation id: {required}")

    for row in operations:
        ident = str(row.get("id") or "")
        semantic = row.get("semantic_result")
        expected = row.get("semantic_sha256")
        actual = sha256_canonical(semantic)
        if expected != actual:
            errors.append(f"mismatched per-operation digest for {ident}")
        for hit in find_forbidden_nondeterminism(semantic):
            errors.append(f"forbidden nondeterministic field in {ident}: {hit}")

    historical = list(witness.get("historical_compatibility") or [])
    for row in historical:
        if not row.get("stored_schema_version"):
            errors.append("historical entry missing stored_schema_version")
        if not row.get("reader_path"):
            errors.append("historical entry missing reader_path")
        if not row.get("semantic_sha256"):
            errors.append("historical entry missing semantic_sha256")
        expected = row.get("semantic_sha256")
        actual = sha256_canonical(row.get("semantic_result"))
        if expected != actual:
            errors.append(f"mismatched historical digest for {row.get('stored_schema_version')}")

    aggregate = aggregate_semantic_sha256(operations)
    if witness.get("aggregate_semantic_sha256") != aggregate:
        errors.append("mismatched aggregate_semantic_sha256")

    if errors:
        raise WitnessValidationError("\n".join(errors))


def aggregate_semantic_sha256(operations: list[dict[str, Any]]) -> str:
    ordered = sorted(operations, key=lambda row: str(row.get("id") or ""))
    records = [
        {
            "id": row["id"],
            "semantic_sha256": row["semantic_sha256"],
            "status": row.get("status"),
        }
        for row in ordered
    ]
    return f"sha256:{sha256_canonical(records)}"


def make_operation(
    *,
    operation_id: str,
    family: str,
    request_identity: dict[str, Any],
    status: str,
    semantic_result: Any,
) -> dict[str, Any]:
    normalized = normalize_semantic(semantic_result)
    return {
        "id": operation_id,
        "family": family,
        "request_identity": normalize_semantic(request_identity),
        "status": status,
        "semantic_result": normalized,
        "semantic_sha256": sha256_canonical(normalized),
    }
