"""Deterministic validation matrix for D&D Threat candidate packets."""

from __future__ import annotations

import copy
import json
import traceback
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from dungeonmind_dnd.application.threat_candidates import (
    _validate_against_catalog,
    load_builtin_threat_vocabulary,
    parse_threat_candidate_packet,
    validate_threat_candidate_packet,
    vocabulary_sha256,
)
from dungeonmind_dnd.contracts.candidates import DndThreatCandidatePacket
from dungeonmind_dnd.contracts.vocabulary import DndSemanticVocabulary
from dungeonmind_dnd.domain.errors import (
    DndCandidateValidationError,
    DndVocabularyIntegrityError,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "dungeonmind_dnd"
    / "tripod-null-calf-threat-candidates-v1.json"
)

TRIPOD = "cand:tripod-null-calf"
BREACH = "cand:north-gate-breach"
NORTH_GATE = "obj:north-gate"


def _fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _mutate(mutator) -> dict[str, Any]:
    payload = _fixture()
    mutator(payload)
    return payload


def _model_rejects(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        DndThreatCandidatePacket.model_validate(payload)


def _catalog_rejects(payload: dict[str, Any], *needles: str) -> None:
    packet = DndThreatCandidatePacket.model_validate(payload)
    with pytest.raises(DndCandidateValidationError) as exc_info:
        validate_threat_candidate_packet(packet)
    assert exc_info.value.code == "dnd_candidate_validation_error"
    blob = str(exc_info.value) + str(exc_info.value.details)
    for needle in needles:
        assert needle in blob


def test_valid_fixture_is_accepted_unchanged() -> None:
    packet = DndThreatCandidatePacket.model_validate(_fixture())
    validated = validate_threat_candidate_packet(packet)
    assert validated.model_dump(mode="json") == packet.model_dump(mode="json")


def test_fixture_serializes_without_forbidden_fields_or_terms() -> None:
    blob = json.dumps(_fixture())
    for forbidden in (
        '"properties"',
        '"confidence"',
        '"object_id"',
        '"graph_revision_id"',
        '"contribution_id"',
        '"canon_state"',
        '"visibility"',
        '"dnd5e:threat"',
        "armor class",
        "hit points",
        "challenge rating",
    ):
        assert forbidden not in blob


def test_minimal_threatens_packet_is_accepted() -> None:
    payload = _fixture()
    # Keep exactly one creature candidate and one threatens relationship.
    payload["nodes"] = [node for node in payload["nodes"] if node["candidate_id"] == TRIPOD]
    payload["relationships"] = [
        rel for rel in payload["relationships"] if rel["predicate"] == "dnd5e:threatens"
    ]
    used = {payload["relationships"][0]["evidence_ref_ids"][0]}
    used.add(payload["nodes"][0]["evidence_ref_ids"][0])
    payload["evidence_refs"] = [
        ref for ref in payload["evidence_refs"] if ref["evidence_ref_id"] in used
    ]
    packet = DndThreatCandidatePacket.model_validate(payload)
    assert validate_threat_candidate_packet(packet) is packet


# --- Model-level rejections (strict shape / packet-internal invariants) ---


def test_threat_as_object_kind_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["nodes"][0]["kind"] = "dnd5e:threat"

    with pytest.raises(ValidationError, match="never an object kind"):
        DndThreatCandidatePacket.model_validate(_mutate(mutate))


def test_threat_as_surface_form_alias_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["nodes"][0]["surface_forms"].append("dnd5e:threat")

    _model_rejects(_mutate(mutate))


def test_dangling_candidate_endpoint_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["relationships"][0]["subject"] = {"candidate_id": "cand:missing"}

    _model_rejects(_mutate(mutate))


def test_existing_endpoint_without_expected_kind_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["relationships"][0]["object"] = {"existing_object_id": NORTH_GATE}

    _model_rejects(_mutate(mutate))


def test_candidate_endpoint_with_expected_kind_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["relationships"][1]["subject"] = {
            "candidate_id": TRIPOD,
            "expected_kind": "dnd5e:creature",
        }

    _model_rejects(_mutate(mutate))


def test_duplicate_candidate_id_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        dupe = copy.deepcopy(payload["nodes"][1])
        dupe["candidate_id"] = TRIPOD
        payload["nodes"].append(dupe)

    _model_rejects(_mutate(mutate))


def test_relationship_id_colliding_with_node_id_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["relationships"][2]["candidate_id"] = TRIPOD

    _model_rejects(_mutate(mutate))


@pytest.mark.parametrize("bad_id", ["obj:tripod-null-calf", "rel:tripod-null-calf"])
def test_candidate_id_with_graph_prefix_is_rejected(bad_id: str) -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["nodes"][0]["candidate_id"] = bad_id
        for rel in payload["relationships"]:
            if rel["subject"].get("candidate_id") == TRIPOD:
                rel["subject"]["candidate_id"] = bad_id

    _model_rejects(_mutate(mutate))


def test_duplicate_normalized_surface_form_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["nodes"][0]["surface_forms"].append("  TRIPOD   null-calf ")

    _model_rejects(_mutate(mutate))


def test_node_without_evidence_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["nodes"][0]["evidence_ref_ids"] = []

    _model_rejects(_mutate(mutate))


def test_relationship_without_evidence_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["relationships"][0]["evidence_ref_ids"] = []

    _model_rejects(_mutate(mutate))


def test_dangling_evidence_id_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["nodes"][0]["evidence_ref_ids"] = ["ev:not-in-ledger"]

    _model_rejects(_mutate(mutate))


def test_unused_evidence_ref_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        extra = copy.deepcopy(payload["evidence_refs"][0])
        extra["evidence_ref_id"] = "ev:unused"
        payload["evidence_refs"].append(extra)

    _model_rejects(_mutate(mutate))


def test_packet_without_threatens_relationship_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["relationships"] = [
            rel
            for rel in payload["relationships"]
            if rel["predicate"] != "dnd5e:threatens"
        ]
        used = {
            evidence_id
            for rel in payload["relationships"]
            for evidence_id in rel["evidence_ref_ids"]
        }
        used.add("ev:tripod-null-calf-sighting")
        used.add("ev:north-gate-breach-plan")
        payload["evidence_refs"] = [
            ref for ref in payload["evidence_refs"] if ref["evidence_ref_id"] in used
        ]

    _model_rejects(_mutate(mutate))


def test_ungrounded_node_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        # The breach node joins no relationship after dropping participates_in
        # and holds no focus evidence.
        payload["relationships"] = [
            rel
            for rel in payload["relationships"]
            if rel["predicate"] != "dnd5e:participates_in"
        ]
        used = {
            evidence_id
            for rel in payload["relationships"]
            for evidence_id in rel["evidence_ref_ids"]
        }
        used.update(payload["focus_evidence_ref_ids"])
        used.add("ev:north-gate-breach-plan")
        payload["evidence_refs"] = [
            ref for ref in payload["evidence_refs"] if ref["evidence_ref_id"] in used
        ]

    _model_rejects(_mutate(mutate))


def test_focus_evidence_grounds_an_isolated_node() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["relationships"] = [
            rel
            for rel in payload["relationships"]
            if rel["predicate"] != "dnd5e:participates_in"
        ]
        payload["focus_evidence_ref_ids"].append("ev:north-gate-breach-plan")
        used = {
            evidence_id
            for rel in payload["relationships"]
            for evidence_id in rel["evidence_ref_ids"]
        }
        used.update(payload["focus_evidence_ref_ids"])
        payload["evidence_refs"] = [
            ref for ref in payload["evidence_refs"] if ref["evidence_ref_id"] in used
        ]

    packet = DndThreatCandidatePacket.model_validate(_mutate(mutate))
    assert validate_threat_candidate_packet(packet) is packet


def test_self_pointing_relationship_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["relationships"][2]["object"] = {"candidate_id": TRIPOD}

    _model_rejects(_mutate(mutate))


def test_evidence_anchor_disagreement_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["evidence_refs"][0]["source_artifact_id"] = "src:elsewhere"

    _model_rejects(_mutate(mutate))


def test_source_revision_without_artifact_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["source_artifact_id"] = None

    _model_rejects(_mutate(mutate))


@pytest.mark.parametrize(
    "extra",
    [
        {"properties": {"cr": "1/4"}},
        {"confidence": 0.9},
        {"object_id": "obj:tripod-null-calf"},
        {"graph_revision_id": "rev:abc"},
        {"canon_state": "canon"},
        {"visibility": "gm"},
    ],
)
def test_node_with_open_or_canon_fields_is_rejected(extra: dict[str, Any]) -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["nodes"][0].update(extra)

    _model_rejects(_mutate(mutate))


def test_packet_with_write_path_field_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["graph_revision_id"] = "rev:abc"

    _model_rejects(_mutate(mutate))


def test_relationship_with_provider_metadata_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["relationships"][0]["provider"] = "openai"

    _model_rejects(_mutate(mutate))


# --- Catalog-level rejections (profile-owned term and pin rules) ---


def test_foreign_namespace_kind_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["nodes"][0]["kind"] = "generic:creature"

    _catalog_rejects(_mutate(mutate), "namespace", "generic:creature")


def test_unknown_dnd_kind_term_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["nodes"][0]["kind"] = "dnd5e:dragon"

    _catalog_rejects(_mutate(mutate), "unknown object kind", "dnd5e:dragon")


def test_unknown_predicate_term_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["relationships"][0]["predicate"] = "dnd5e:attacks"

    _catalog_rejects(_mutate(mutate), "unknown predicate", "dnd5e:attacks")


def test_located_at_inverted_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["relationships"][0]["subject"] = {
            "existing_object_id": NORTH_GATE,
            "expected_kind": "dnd5e:location",
        }
        payload["relationships"][0]["object"] = {"candidate_id": TRIPOD}

    _catalog_rejects(_mutate(mutate), "domain", "dnd5e:location")


def test_member_of_pointing_to_location_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["relationships"][0]["predicate"] = "dnd5e:member_of"

    _catalog_rejects(_mutate(mutate), "range", "dnd5e:location")


def test_participates_in_pointing_to_faction_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["relationships"][1]["object"] = {
            "existing_object_id": "obj:ash-pact",
            "expected_kind": "dnd5e:faction",
        }
        # Keep the breach node grounded via focus evidence so the catalog
        # range check is what fires.
        payload["focus_evidence_ref_ids"].append("ev:north-gate-breach-plan")

    _catalog_rejects(_mutate(mutate), "range", "dnd5e:faction")


def test_existing_endpoint_with_unknown_expected_kind_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["relationships"][0]["object"] = {
            "existing_object_id": NORTH_GATE,
            "expected_kind": "dnd5e:dragon",
        }

    _catalog_rejects(_mutate(mutate), "unknown object kind", "dnd5e:dragon")


def test_profile_ref_differing_from_catalog_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["semantic_profile"]["profile_revision"] = "dnd5e-profile-v1"

    _catalog_rejects(_mutate(mutate), "profile", "dnd5e-profile-v1")


def test_catalog_digest_differing_from_packet_ref_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["vocabulary"]["catalog_sha256"] = "0" * 64

    _catalog_rejects(_mutate(mutate), "vocabulary", "catalog_sha256")


def test_vocabulary_id_differing_from_catalog_is_rejected() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["vocabulary"]["vocabulary_id"] = "dungeonmind.dnd5e.other"

    _catalog_rejects(_mutate(mutate), "vocabulary", "dungeonmind.dnd5e.other")


def test_validation_errors_do_not_echo_source_prose() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["nodes"][0]["kind"] = "dnd5e:dragon"
        payload["nodes"][0]["summary"] = "secret campaign prose must not leak"

    payload = _mutate(mutate)
    packet = DndThreatCandidatePacket.model_validate(payload)
    with pytest.raises(DndCandidateValidationError) as exc_info:
        validate_threat_candidate_packet(packet)
    blob = str(exc_info.value) + str(exc_info.value.details)
    assert "secret campaign prose" not in blob
    assert "Tripod" not in blob


# --- Ingestion boundary: sanitized packet parsing ---


def test_parse_boundary_accepts_valid_fixture() -> None:
    packet = parse_threat_candidate_packet(_fixture())
    expected = DndThreatCandidatePacket.model_validate(_fixture())
    assert packet.model_dump(mode="json") == expected.model_dump(mode="json")
    assert parse_threat_candidate_packet(packet) is packet


SENTINEL = "zqx9-sentinel-campaign-secret"


def _sentinel_payload(mutator) -> dict[str, Any]:
    """Fixture carrying sentinel prose in label, summary, and evidence
    locator, then mutated into one packet-level contract failure."""

    def inject(payload: dict[str, Any]) -> None:
        payload["nodes"][0]["label"] = f"Tripod Null-Calf ({SENTINEL} label)"
        payload["nodes"][0]["summary"] = f"Summary carrying {SENTINEL} prose."
        payload["evidence_refs"][0]["locator"] = (
            f"fixture://synthetic-gatewatch-watchlog#{SENTINEL}"
        )
        mutator(payload)

    return _mutate(inject)


def _assert_sanitized(exc_info: pytest.ExceptionInfo[BaseException]) -> None:
    error = exc_info.value
    blob = (
        str(error)
        + repr(error)
        + "".join(traceback.format_exception(error))
        + str(getattr(error, "details", {}))
    )
    assert SENTINEL not in blob
    assert "Tripod" not in blob


def _drop_participates_in(payload: dict[str, Any]) -> None:
    payload["relationships"] = [
        rel
        for rel in payload["relationships"]
        if rel["predicate"] != "dnd5e:participates_in"
    ]
    used = {
        evidence_id
        for rel in payload["relationships"]
        for evidence_id in rel["evidence_ref_ids"]
    }
    used.update(payload["focus_evidence_ref_ids"])
    used.add("ev:north-gate-breach-plan")
    payload["evidence_refs"] = [
        ref for ref in payload["evidence_refs"] if ref["evidence_ref_id"] in used
    ]


def _drop_threatens(payload: dict[str, Any]) -> None:
    payload["relationships"] = [
        rel
        for rel in payload["relationships"]
        if rel["predicate"] != "dnd5e:threatens"
    ]
    used = {
        evidence_id
        for rel in payload["relationships"]
        for evidence_id in rel["evidence_ref_ids"]
    }
    used.add("ev:tripod-null-calf-sighting")
    used.add("ev:north-gate-breach-plan")
    payload["evidence_refs"] = [
        ref for ref in payload["evidence_refs"] if ref["evidence_ref_id"] in used
    ]


_PACKET_LEVEL_MUTATORS = {
    "dangling_endpoint": lambda payload: payload["relationships"][0].update(
        subject={"candidate_id": "cand:missing"}
    ),
    "unused_evidence": lambda payload: payload["evidence_refs"].append(
        {**copy.deepcopy(payload["evidence_refs"][1]), "evidence_ref_id": "ev:unused"}
    ),
    "source_anchor_mismatch": lambda payload: payload["evidence_refs"][1].update(
        source_artifact_id="src:elsewhere"
    ),
    "ungrounded_node": _drop_participates_in,
    "duplicate_candidate_identity": lambda payload: payload["nodes"].append(
        {**copy.deepcopy(payload["nodes"][1]), "candidate_id": TRIPOD}
    ),
    "missing_threatens": _drop_threatens,
}


@pytest.mark.parametrize("failure", sorted(_PACKET_LEVEL_MUTATORS))
def test_parse_boundary_never_echoes_rejected_packet(failure: str) -> None:
    payload = _sentinel_payload(_PACKET_LEVEL_MUTATORS[failure])
    with pytest.raises(DndCandidateValidationError) as exc_info:
        parse_threat_candidate_packet(payload)
    assert exc_info.value.code == "dnd_candidate_validation_error"
    _assert_sanitized(exc_info)


def test_raw_model_error_hides_rejected_input_as_defense_in_depth() -> None:
    payload = _sentinel_payload(_PACKET_LEVEL_MUTATORS["dangling_endpoint"])
    with pytest.raises(ValidationError) as exc_info:
        DndThreatCandidatePacket.model_validate(payload)
    # ``hide_input_in_errors`` keeps rejected payloads out of the formatted
    # error. Raw ``errors()`` records still carry input values; the ingestion
    # boundary never copies them into the package-owned error.
    blob = (
        str(exc_info.value)
        + repr(exc_info.value)
        + "".join(traceback.format_exception(exc_info.value))
    )
    assert SENTINEL not in blob
    assert "Tripod" not in blob


# --- Authoritative catalog: injected vocabularies cannot widen terms ---


def _alternate_catalog(
    object_kinds: list[dict[str, Any]],
    predicates: list[dict[str, Any]],
) -> DndSemanticVocabulary:
    """Internally consistent catalog that is NOT the bundled Threat catalog."""
    return DndSemanticVocabulary.model_validate(
        {
            "schema_version": "dmdnd_semantic_vocabulary_v1",
            "vocabulary_id": "dungeonmind.dnd5e.threat",
            "vocabulary_revision": "threat-v1",
            "semantic_profile": _fixture()["semantic_profile"],
            "object_kinds": object_kinds,
            "predicates": predicates,
        }
    )


def _adversarial_packet(
    catalog: DndSemanticVocabulary,
    kind_term: str,
    extra_predicate: str | None = None,
) -> DndThreatCandidatePacket:
    """Fixture trimmed to two candidate nodes plus threatens (and optional
    extra) relationships, using only terms the alternate catalog admits, with
    a vocabulary ref matching the alternate catalog digest."""
    payload = _fixture()
    for node in payload["nodes"]:
        node["kind"] = kind_term
    threatens = payload["relationships"][2]
    threatens["object"] = {"candidate_id": BREACH}
    kept = [threatens]
    if extra_predicate is not None:
        extra = copy.deepcopy(payload["relationships"][0])
        extra["candidate_id"] = "candrel:tripod-extra-predicate-breach"
        extra["predicate"] = extra_predicate
        extra["object"] = {"candidate_id": BREACH}
        kept.append(extra)
    payload["relationships"] = kept
    used = set(payload["focus_evidence_ref_ids"])
    for node in payload["nodes"]:
        used.update(node["evidence_ref_ids"])
    for rel in kept:
        used.update(rel["evidence_ref_ids"])
    payload["evidence_refs"] = [
        ref for ref in payload["evidence_refs"] if ref["evidence_ref_id"] in used
    ]
    payload["vocabulary"]["catalog_sha256"] = vocabulary_sha256(catalog)
    return DndThreatCandidatePacket.model_validate(payload)


def _predicate(term: str, kind: str) -> dict[str, Any]:
    return {
        "term": term,
        "label": term.split(":", 1)[1].replace("_", " ").title(),
        "description": f"Adversarial {term} predicate.",
        "subject_kinds": [kind],
        "object_kinds": [kind],
    }


@pytest.mark.parametrize(
    ("kind_term", "extra_predicate"),
    [
        ("generic:creature", None),
        ("dnd5e:dragon", None),
        ("dnd5e:creature", "dnd5e:attacks"),
    ],
    ids=["foreign-namespace", "unknown-dnd-kind", "extra-predicate"],
)
def test_adversarial_catalog_is_rejected_by_public_validator(
    kind_term: str, extra_predicate: str | None
) -> None:
    predicates = [_predicate("dnd5e:threatens", kind_term)]
    if extra_predicate is not None:
        predicates.append(_predicate(extra_predicate, kind_term))
    catalog = _alternate_catalog(
        object_kinds=[
            {
                "term": kind_term,
                "label": kind_term.split(":", 1)[1].title(),
                "description": f"Adversarial {kind_term} kind.",
            }
        ],
        predicates=predicates,
    )
    packet = _adversarial_packet(catalog, kind_term, extra_predicate)
    # The alternate catalog is internally consistent: the private seam —
    # which exists for unit-test injection — accepts the matching packet.
    assert _validate_against_catalog(packet, catalog) is packet
    # The public B.2c validator must reject any non-bundled catalog even
    # when the packet's vocabulary ref matches its digest.
    with pytest.raises(DndVocabularyIntegrityError) as exc_info:
        validate_threat_candidate_packet(packet, vocabulary=catalog)
    assert exc_info.value.code == "dnd_vocabulary_integrity_error"


def test_injected_catalog_with_bundled_terms_but_wrong_revision_is_rejected() -> None:
    data = load_builtin_threat_vocabulary().model_dump(mode="json")
    data["vocabulary_revision"] = "threat-v2"
    catalog = DndSemanticVocabulary.model_validate(data)
    packet = DndThreatCandidatePacket.model_validate(_fixture())
    with pytest.raises(DndVocabularyIntegrityError):
        validate_threat_candidate_packet(packet, vocabulary=catalog)


def test_injected_catalog_identical_to_bundled_is_accepted() -> None:
    packet = DndThreatCandidatePacket.model_validate(_fixture())
    injected = load_builtin_threat_vocabulary()
    assert validate_threat_candidate_packet(packet, vocabulary=injected) is packet
