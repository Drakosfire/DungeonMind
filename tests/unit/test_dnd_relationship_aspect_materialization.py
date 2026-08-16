"""#588 dual-sense package → D&D v6 materialization plan proofs."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from typing import Any

import pytest

from dungeonmind_dnd.application.relationship_aspect_materialization import (
    DndRelationshipAspectMaterializationError,
    materialize_relationship_aspect_plan_v1,
    plan_canonical_bytes,
    recompute_package_canonical_payload_sha256,
    sha256_bytes,
)
from dungeonmind_dnd.application.world_object_vocabulary import (
    load_builtin_world_object_v4_vocabulary,
    load_builtin_world_object_v5_vocabulary,
)
from dungeonmind_dnd.contracts.relationship_aspect_materialization import (
    BuddyDualSenseDecompositionPackageV1,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "dungeonmind_dnd"
    / "eldyrwild_relationship_dual_sense_decomposition_v1.json"
)
FIXTURE_SHA256 = "53986158ec9ad326481755f7baef9f425d973f34a65b789f96e92e3f55208ef8"
CANONICAL_PAYLOAD_SHA256 = (
    "d71453926b0475ca686b9c94452688d5a6b285afab304c35d48035c252240207"
)
DISPATCH_BASE = "be76acc997c5fbcb8ceaa090969ec051afa6051d"
ADAPTER_PATH = (
    REPO_ROOT
    / "src"
    / "dungeonmind_dnd"
    / "application"
    / "relationship_aspect_materialization.py"
)
CONTRACT_PATH = (
    REPO_ROOT
    / "src"
    / "dungeonmind_dnd"
    / "contracts"
    / "relationship_aspect_materialization.py"
)

EXPECTED_ASPECTS = {
    ("loc:wizard_college", "organization", "dnd5e:faction"),
    (
        "node:meat_distribution_network_session9",
        "site",
        "dnd5e:location",
    ),
    ("node:hempholm_folk_revelry", "event", "dnd5e:event"),
}
EXPECTED_ENDPOINTS = {
    (
        "edge:loc:central-office:located_in:node:meat_distribution_network_session9:site-of",
        "target",
        "dnd5e:located_in",
        "dnd5e:location",
        "dnd5e:location",
    ),
    (
        "edge:loc:packing-loading-area:part_of:node:meat_distribution_network_session9",
        "target",
        "dnd5e:part_of",
        "dnd5e:location",
        "dnd5e:location",
    ),
    (
        "edge:node:headmaster_tinkerbright:leads:loc:wizard_college",
        "target",
        "dnd5e:leads",
        "dnd5e:npc",
        "dnd5e:faction",
    ),
    (
        "edge:node:hempholm_townsfolk:participates_in:node:hempholm_folk_revelry",
        "target",
        "dnd5e:participates_in",
        "dnd5e:group",
        "dnd5e:event",
    ),
    (
        "edge:pc:caelynn:participates_in:node:hempholm_folk_revelry",
        "target",
        "dnd5e:participates_in",
        "dnd5e:player_character",
        "dnd5e:event",
    ),
}


def _raw() -> bytes:
    return FIXTURE_PATH.read_bytes()


def _payload() -> dict[str, Any]:
    return json.loads(_raw().decode("utf-8"))


def _resealed_bytes(payload: dict[str, Any]) -> bytes:
    working = copy.deepcopy(payload)
    working["canonical_payload_sha256"] = ""
    package = BuddyDualSenseDecompositionPackageV1.model_validate(working)
    digest = recompute_package_canonical_payload_sha256(package)
    dumped = package.model_dump(mode="json", by_alias=True)
    dumped["canonical_payload_sha256"] = digest
    return json.dumps(
        dumped,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _plan(raw: bytes | None = None):
    return materialize_relationship_aspect_plan_v1(
        raw if raw is not None else _raw(),
        world_object_vocabulary=load_builtin_world_object_v5_vocabulary(),
    )


def test_fixture_file_sha256() -> None:
    assert sha256_bytes(_raw()) == FIXTURE_SHA256


def test_canonical_payload_self_hash() -> None:
    package = BuddyDualSenseDecompositionPackageV1.model_validate(_payload())
    assert package.canonical_payload_sha256 == CANONICAL_PAYLOAD_SHA256
    assert recompute_package_canonical_payload_sha256(package) == CANONICAL_PAYLOAD_SHA256


def test_plan_has_three_aspects_and_five_endpoints() -> None:
    plan = _plan()
    assert len(plan.aspect_directives) == 3
    assert len(plan.endpoint_directives) == 5


def test_exact_hash588_mapping() -> None:
    plan = _plan()
    aspects = {
        (row.source_object_id, row.aspect_key, row.projected_kind)
        for row in plan.aspect_directives
    }
    endpoints = {
        (
            row.source_edge_id,
            row.assigned_endpoint,
            row.dm_predicate,
            row.source_dm_kind,
            row.target_dm_kind,
        )
        for row in plan.endpoint_directives
    }
    assert aspects == EXPECTED_ASPECTS
    assert endpoints == EXPECTED_ENDPOINTS


def test_assigned_relationships_locally_admitted() -> None:
    plan = _plan()
    catalog = load_builtin_world_object_v5_vocabulary()
    predicates = {item.term: item for item in catalog.predicates}
    for row in plan.endpoint_directives:
        predicate = predicates[row.dm_predicate]
        assert row.source_dm_kind in predicate.subject_kinds
        assert row.target_dm_kind in predicate.object_kinds


def test_retained_primary_senses_locally_admitted() -> None:
    catalog = load_builtin_world_object_v5_vocabulary()
    predicates = {item.term: item for item in catalog.predicates}
    retained = {
        "edge:node:thalia:travels_to:loc:wizard_college": (
            "dnd5e:travels_to",
            "dnd5e:npc",
            "dnd5e:location",
        ),
        "edge:node:torbin:travels_to:loc:wizard_college": (
            "dnd5e:travels_to",
            "dnd5e:npc",
            "dnd5e:location",
        ),
        "edge:node:captain_blart:leads:node:meat_distribution_network_session9:coordinates": (
            "dnd5e:leads",
            "dnd5e:npc",
            "dnd5e:party",
        ),
        "edge:node:lyra:leads:node:meat_distribution_network_session9": (
            "dnd5e:leads",
            "dnd5e:npc",
            "dnd5e:party",
        ),
        "edge:node:hempholm_folk_revelry:within:loc:hempholm": (
            "dnd5e:located_in",
            "dnd5e:group",
            "dnd5e:location",
        ),
    }
    package = BuddyDualSenseDecompositionPackageV1.model_validate(_payload())
    claimed = {row.edge_id: row for row in package.package_projection.retained_admissions}
    for edge_id, (predicate, source_kind, target_kind) in retained.items():
        admission = claimed[edge_id]
        assert admission.admitted is True
        spec = predicates[predicate]
        assert source_kind in spec.subject_kinds
        assert target_kind in spec.object_kinds
        _plan()


def test_plan_contains_no_new_object_identities() -> None:
    plan = _plan()
    package = BuddyDualSenseDecompositionPackageV1.model_validate(_payload())
    known = {row.source_node_id for row in package.decomposition_rows}
    for assignment in package.endpoint_assignments:
        known.add(assignment.source_node_id)
        known.add(assignment.target_node_id)
    for row in plan.aspect_directives:
        assert row.source_object_id in known
        assert not row.source_object_id.startswith("node:aspect:")
        assert "synthetic" not in row.source_object_id
    for row in plan.endpoint_directives:
        assert row.source_object_id in known
        assert row.target_object_id in known


def test_plan_does_not_mint_durable_aspect_assertion_ids() -> None:
    dumped = json.dumps(_plan().model_dump(mode="json"), sort_keys=True)
    assert "assertion_id" not in dumped
    assert "asrt:" not in dumped
    for row in _plan().aspect_directives:
        assert not hasattr(row, "aspect_assertion_id")


def test_permuting_source_arrays_yields_identical_plan() -> None:
    payload = _payload()
    payload["decomposition_rows"] = list(reversed(payload["decomposition_rows"]))
    payload["endpoint_assignments"] = list(reversed(payload["endpoint_assignments"]))
    payload["package_projection"]["assigned_admissions"] = list(
        reversed(payload["package_projection"]["assigned_admissions"])
    )
    payload["package_projection"]["retained_admissions"] = list(
        reversed(payload["package_projection"]["retained_admissions"])
    )
    original = _plan()
    permuted = _plan(_resealed_bytes(payload))
    assert original.aspect_directives == permuted.aspect_directives
    assert original.endpoint_directives == permuted.endpoint_directives
    original_payload = json.loads(plan_canonical_bytes(original))
    permuted_payload = json.loads(plan_canonical_bytes(permuted))
    for key in (
        "source_package_sha256",
        "source_package_canonical_payload_sha256",
        "plan_sha256",
    ):
        original_payload.pop(key)
        permuted_payload.pop(key)
    assert original_payload == permuted_payload


@pytest.mark.parametrize(
    ("mutator", "reason"),
    [
        (
            lambda p: p["endpoint_assignments"].append(copy.deepcopy(p["endpoint_assignments"][0])),
            "duplicate_assignment",
        ),
        (
            lambda p: p["endpoint_assignments"].pop(),
            "assignment_admission_mismatch",
        ),
        (
            lambda p: p["endpoint_assignments"].append(
                {
                    **copy.deepcopy(p["endpoint_assignments"][0]),
                    "edge_id": "edge:extra:assignment",
                }
            ),
            "assignment_admission_mismatch",
        ),
    ],
)
def test_duplicate_missing_extra_assignment_refuses(mutator, reason: str) -> None:
    payload = _payload()
    mutator(payload)
    with pytest.raises(DndRelationshipAspectMaterializationError) as exc:
        _plan(_resealed_bytes(payload))
    assert exc.value.details["reason"] == reason


def test_aspect_source_endpoint_mismatch_refuses() -> None:
    payload = _payload()
    payload["endpoint_assignments"][0]["aspect_ref"]["source_node_id"] = "loc:central-office"
    with pytest.raises(DndRelationshipAspectMaterializationError) as exc:
        _plan(_resealed_bytes(payload))
    assert exc.value.details["reason"] == "aspect_endpoint_mismatch"


def test_projected_kind_absent_from_v5_refuses() -> None:
    payload = _payload()
    payload["decomposition_rows"][0]["projected_dm_kind"] = "dnd5e:not_a_kind"
    with pytest.raises(DndRelationshipAspectMaterializationError) as exc:
        _plan(_resealed_bytes(payload))
    assert exc.value.details["reason"] == "projected_kind_absent"


def test_locally_invalid_endpoint_kinds_refuse() -> None:
    payload = _payload()
    leads = next(
        row
        for row in payload["endpoint_assignments"]
        if row["edge_id"] == "edge:node:headmaster_tinkerbright:leads:loc:wizard_college"
    )
    leads["aspect_ref"]["projected_dm_kind"] = "dnd5e:location"
    row = next(
        item
        for item in payload["decomposition_rows"]
        if item["source_node_id"] == "loc:wizard_college"
    )
    row["projected_dm_kind"] = "dnd5e:location"
    admission = next(
        item
        for item in payload["package_projection"]["assigned_admissions"]
        if item["edge_id"] == leads["edge_id"]
    )
    admission["target_dm_kind"] = "dnd5e:location"
    with pytest.raises(DndRelationshipAspectMaterializationError) as exc:
        _plan(_resealed_bytes(payload))
    assert exc.value.details["reason"] == "local_predicate_rejected"


def test_foreign_admitted_true_lie_refuses() -> None:
    payload = _payload()
    admission = next(
        item
        for item in payload["package_projection"]["assigned_admissions"]
        if item["edge_id"].endswith("site-of")
    )
    admission["source_dm_kind"] = "dnd5e:event"
    admission["admitted"] = True
    with pytest.raises(DndRelationshipAspectMaterializationError) as exc:
        _plan(_resealed_bytes(payload))
    assert exc.value.details["reason"] == "local_predicate_rejected"
    assert "foreign admitted=true" in str(exc.value)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda p: p["package_projection"].__setitem__("passed", False),
        lambda p: p["package_projection"]["retained_regressions"].append("edge:x"),
        lambda p: p["package_projection"]["uncovered_current_residual_edge_ids"].append(
            "edge:x"
        ),
        lambda p: p["package_projection"]["extra_package_edge_assignments"].append("edge:x"),
    ],
)
def test_package_residual_or_failed_projection_refuses(mutator) -> None:
    payload = _payload()
    mutator(payload)
    with pytest.raises(DndRelationshipAspectMaterializationError) as exc:
        _plan(_resealed_bytes(payload))
    assert exc.value.details["reason"] == "package_projection_failed"


def test_canonical_payload_tamper_refuses() -> None:
    payload = _payload()
    payload["canonical_payload_sha256"] = "00" * 32
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    with pytest.raises(DndRelationshipAspectMaterializationError) as exc:
        _plan(raw)
    assert exc.value.details["reason"] == "package_canonical_tampered"


def test_source_dependency_pin_is_provenance_not_git(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan()
    assert plan.source_dungeonmind_dependency_ref == DISPATCH_BASE

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("adapter must not call git")

    monkeypatch.setattr("subprocess.run", _boom)
    monkeypatch.setattr("subprocess.check_output", _boom)
    monkeypatch.setattr("os.system", _boom)
    again = _plan()
    assert again.source_dungeonmind_dependency_ref == DISPATCH_BASE
    source = ADAPTER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
    }
    assert "subprocess" not in imported
    assert "git" not in imported


def test_production_sources_do_not_import_buddy() -> None:
    forbidden = ("graph_memory", "apps.", "DungeonMindBuddy", "/DungeonMindBuddy/")
    for path in (ADAPTER_PATH, CONTRACT_PATH):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text
    tree = ast.parse(ADAPTER_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("apps")
                assert not alias.name.startswith("graph_memory")
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("apps")
            assert not node.module.startswith("graph_memory")


def test_explicit_v5_vocabulary_required() -> None:
    with pytest.raises(DndRelationshipAspectMaterializationError) as exc:
        materialize_relationship_aspect_plan_v1(
            _raw(),
            world_object_vocabulary=load_builtin_world_object_v4_vocabulary(),
        )
    assert exc.value.details["reason"] == "vocabulary_revision_mismatch"


def test_adapter_hashes_raw_bytes_itself() -> None:
    plan = _plan()
    assert plan.source_package_sha256 == FIXTURE_SHA256
    with pytest.raises(DndRelationshipAspectMaterializationError) as exc:
        materialize_relationship_aspect_plan_v1(  # type: ignore[arg-type]
            json.loads(_raw().decode("utf-8")),
            world_object_vocabulary=load_builtin_world_object_v5_vocabulary(),
        )
    assert exc.value.details["reason"] == "package_unattested"
