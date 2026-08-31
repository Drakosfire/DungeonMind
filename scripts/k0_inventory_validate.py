"""Validation for the K0.1 consumer/public-surface inventory ledger."""

from __future__ import annotations

from typing import Any

SCHEMA = "dm_k0_surface_inventory_v1"
DISPOSITIONS = frozenset({"USED", "UNUSED", "HISTORICAL-COMPAT", "UNKNOWN"})
REQUIRED_TOP_LEVEL = (
    "schema",
    "inputs",
    "external_consumer_imports",
    "explicit_exports",
    "internal_import_evidence",
    "repository_ledger",
    "table_ledger",
    "import_boundary_exceptions",
    "optional_dependency_probe",
    "subsystem_dispositions",
    "module_string_consumer_evidence",
    "known_red_baselines",
    "unresolved_questions",
)
NAMED_SUBSYSTEM_IDS = (
    "mind_turn_contracts_and_service",
    "agents_protocol_and_fixture",
    "capability_policy_agent_visible_tool_authority",
    "capability_policy_contribution_review_authorization",
    "context_assembly_mind_turn_budgeting",
    "claim_answer_validation_mind_turn_retrieval",
    "mind_thread_persistence_runtime",
    "retrieval_session_persistence_runtime",
    "semantic_document_persistence_runtime",
    "embedding_run_persistence_runtime",
    "semantic_search_pgvector_runtime",
    "demo_access_curated_mind_turn_host",
    "world_graph_projection_retrieval",
    "source_evidence_repositories",
    "contribution_review_publication",
    "reviewed_first_world_initialization",
    "existing_world_adoption_receipt_read",
    "existing_world_adoption_write_command",
    "adoption_repair",
    "correspondence",
    "versioned_union_graph_snapshot_dispatch",
    "v1_v5_historical_graph_schema_codecs",
    "semantic_profile_registry",
    "dnd_profile_planning_mechanics_packages",
    "dnd_optional_fastapi_httpx_transport",
)


class LedgerValidationError(ValueError):
    """Raised when a K0.1 ledger violates the observational schema."""


def _require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _unique_ids(rows: list[dict[str, Any]], key: str, label: str, errors: list[str]) -> None:
    seen: set[str] = set()
    for row in rows:
        ident = str(row.get(key, ""))
        if not ident:
            errors.append(f"{label} entry missing {key!r}")
            continue
        if ident in seen:
            errors.append(f"duplicate {label} id: {ident}")
        seen.add(ident)


def _buddy_imported_modules(ledger: dict[str, Any]) -> set[str]:
    modules: set[str] = set()
    for row in ledger.get("external_consumer_imports", []):
        module = str(row.get("imported_module", ""))
        if module:
            modules.add(module)
    return modules


def _buddy_imported_symbols(ledger: dict[str, Any]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for row in ledger.get("external_consumer_imports", []):
        module = str(row.get("imported_module", ""))
        for symbol in row.get("imported_symbols") or []:
            if symbol and symbol != "*":
                pairs.add((module, str(symbol)))
    return pairs


def _covers_buddy_import(
    covers: list[str],
    buddy_modules: set[str],
    buddy_symbols: set[tuple[str, str]],
) -> list[str]:
    hits: list[str] = []
    for cover in covers:
        if ":" in cover:
            module, name = cover.split(":", 1)
            if (module, name) in buddy_symbols:
                hits.append(cover)
            continue
        for module in buddy_modules:
            if module == cover or module.startswith(f"{cover}."):
                hits.append(f"{cover} ← {module}")
    return hits


def validate_ledger(ledger: dict[str, Any]) -> None:
    """Reject an inventory that is unsafe to treat as K0.1 evidence."""

    errors: list[str] = []
    _require(ledger.get("schema") == SCHEMA, f"schema must be {SCHEMA}", errors)
    for key in REQUIRED_TOP_LEVEL:
        _require(key in ledger, f"missing top-level key {key!r}", errors)

    if isinstance(ledger.get("external_consumer_imports"), list):
        missing_resolve = [
            row
            for row in ledger["external_consumer_imports"]
            if not row.get("resolves_against_code_anchor", False)
        ]
        for row in missing_resolve:
            errors.append(
                "unresolved imported Buddy symbol/module: "
                f"{row.get('consumer_file')}: {row.get('imported_module')} "
                f"{row.get('imported_symbols')}"
            )

    repos = list(ledger.get("repository_ledger") or [])
    tables = list(ledger.get("table_ledger") or [])
    subsystems = list(ledger.get("subsystem_dispositions") or [])
    _unique_ids(repos, "id", "repository", errors)
    _unique_ids(tables, "id", "table", errors)
    _unique_ids(subsystems, "id", "subsystem", errors)

    present_ids = {str(row.get("id")) for row in subsystems}
    for required_id in NAMED_SUBSYSTEM_IDS:
        if required_id not in present_ids:
            errors.append(f"missing named subsystem disposition: {required_id}")

    buddy_modules = _buddy_imported_modules(ledger)
    buddy_symbols = _buddy_imported_symbols(ledger)

    for row in subsystems:
        ident = str(row.get("id", ""))
        disposition = str(row.get("disposition", ""))
        if disposition not in DISPOSITIONS:
            errors.append(f"unknown disposition vocabulary for {ident}: {disposition!r}")
            continue
        evidence = row.get("evidence") or []
        if disposition in {"USED", "UNUSED", "HISTORICAL-COMPAT"} and not evidence:
            errors.append(f"missing evidence for {disposition} subsystem {ident}")
        if disposition == "UNKNOWN" and not str(row.get("blocking_question") or "").strip():
            errors.append(f"UNKNOWN subsystem {ident} missing blocking_question")
        if disposition == "UNUSED":
            covers = [str(item) for item in (row.get("covers") or [])]
            hits = _covers_buddy_import(covers, buddy_modules, buddy_symbols)
            for hit in hits:
                errors.append(
                    f"Buddy-imported current symbol classified UNUSED on {ident}: {hit}"
                )
            if not str(row.get("falsification_note") or "").strip():
                errors.append(f"UNUSED subsystem {ident} missing falsification_note")

    expected_tables = set(ledger.get("derived_alembic_tables") or [])
    listed_tables = {str(row.get("id")) for row in tables}
    if expected_tables:
        missing = sorted(expected_tables - listed_tables)
        extra_check = sorted(listed_tables - expected_tables)
        for name in missing:
            errors.append(f"Alembic-created table omitted from table ledger: {name}")
        # Extra curated aliases are forbidden; the ledger must be exact.
        for name in extra_check:
            errors.append(f"table ledger contains name not created by Alembic: {name}")

    expected_repos = set(ledger.get("derived_repository_ids") or [])
    listed_repos = {str(row.get("id")) for row in repos}
    if expected_repos:
        for name in sorted(expected_repos - listed_repos):
            errors.append(
                f"repository protocol/bundle entry omitted from repository ledger: {name}"
            )

    inputs = ledger.get("inputs") or {}
    for key in (
        "dungeonmind_runtime_anchor",
        "dungeonmind_steward_base",
        "runtime_tree_digest",
        "dungeonmind_module_string_scan_ref",
        "dungeonmind_module_string_corpus_digest",
        "dungeonmind_fact_scan_ref",
        "dungeonmind_fact_corpus_digest",
        "buddy_anchor",
        "buddy_dungeonmind_pin",
        "buddy_import_scan_ref",
        "buddy_import_corpus_digest",
        "buddy_module_string_scan_ref",
        "buddy_module_string_corpus_digest",
        "dispositions_digest",
        "scanner_version",
    ):
        if not str(inputs.get(key) or ""):
            errors.append(f"inputs.{key} missing")

    runtime_anchor = str(inputs.get("dungeonmind_runtime_anchor") or "")
    for key in (
        "dungeonmind_module_string_scan_ref",
        "dungeonmind_fact_scan_ref",
    ):
        value = str(inputs.get(key) or "")
        if runtime_anchor and value and runtime_anchor != value:
            errors.append(f"inputs.{key} must equal inputs.dungeonmind_runtime_anchor")

    buddy_anchor = str(inputs.get("buddy_anchor") or "")
    for key in ("buddy_import_scan_ref", "buddy_module_string_scan_ref"):
        value = str(inputs.get(key) or "")
        if buddy_anchor and value and buddy_anchor != value:
            errors.append(f"inputs.{key} must equal inputs.buddy_anchor")

    if "dungeonmind_scanned_head" in ledger.get("anchors", {}):
        errors.append(
            "anchors.dungeonmind_scanned_head is forbidden; use inputs.runtime_tree_digest"
        )

    if errors:
        raise LedgerValidationError("\n".join(errors))
