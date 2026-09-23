"""Pinned native knowledge revision identity."""

from __future__ import annotations

from dungeonmind.application.vnext.revision_ids import (
    IDENTITY_SCHEMA,
    compute_knowledge_revision_id,
)
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext.domain import DomainContractRef
from dungeonmind.contracts.vnext.knowledge import MigrationOriginRef

PINNED_REVISION_ID = "rev:5adc0a3cedf219fe5222c02e295adb30"
PINNED_WITH_ORIGIN_ID = "rev:d02346acad3aef96ddb2ebff261f229c"


def _contract() -> DomainContractRef:
    return DomainContractRef(
        domain_id="lab.domain",
        domain_revision="1",
        descriptor_sha256="ab" * 32,
    )


def _profile() -> SemanticProfileRef:
    return SemanticProfileRef(
        profile_id="lab.profile",
        profile_revision="1",
        descriptor_sha256="cd" * 32,
    )


def _origin(**updates: str) -> MigrationOriginRef:
    payload = {
        "source_system": "legacy",
        "source_root_id": "root:1",
        "source_revision_id": "rev:legacy",
        "source_payload_sha256": "11" * 32,
        "migration_manifest_sha256": "22" * 32,
    }
    payload.update(updates)
    return MigrationOriginRef.model_validate(payload)


def _identity(**overrides: object) -> str:
    material: dict[str, object] = {
        "space_id": "space:lab",
        "parent_revision_id": "rev:parent",
        "operation_ids": ["op:b", "op:a"],
        "graph_schema": "dm_vnext_graph_v1",
        "graph_payload_sha256": "33" * 32,
        "domain_contract_ref": _contract(),
        "semantic_profile_ref": _profile(),
        "migration_origin_ref": None,
    }
    material.update(overrides)
    return compute_knowledge_revision_id(**material)  # type: ignore[arg-type]


def test_identity_schema_name_is_native() -> None:
    assert IDENTITY_SCHEMA == "dm_knowledge_revision_identity_v1"


def test_same_authority_identity_is_pinned() -> None:
    assert _identity() == PINNED_REVISION_ID
    assert _identity() == _identity()


def test_changed_payload_changes_revision_id() -> None:
    assert _identity(graph_payload_sha256="44" * 32) != PINNED_REVISION_ID


def test_changed_operation_order_changes_revision_id() -> None:
    assert _identity(operation_ids=["op:a", "op:b"]) != PINNED_REVISION_ID


def test_changed_domain_contract_changes_revision_id() -> None:
    changed = _contract().model_copy(update={"domain_revision": "2"})
    assert _identity(domain_contract_ref=changed) != PINNED_REVISION_ID


def test_changed_semantic_profile_changes_revision_id() -> None:
    changed = _profile().model_copy(update={"profile_revision": "2"})
    assert _identity(semantic_profile_ref=changed) != PINNED_REVISION_ID


def test_changed_migration_origin_changes_revision_id() -> None:
    with_origin = _identity(migration_origin_ref=_origin())
    assert with_origin == PINNED_WITH_ORIGIN_ID
    assert with_origin != PINNED_REVISION_ID
    moved = _identity(migration_origin_ref=_origin(source_revision_id="rev:other"))
    assert moved != with_origin


def test_created_at_is_not_an_identity_input() -> None:
    assert "created_at" not in compute_knowledge_revision_id.__code__.co_varnames
    assert _identity() == PINNED_REVISION_ID
