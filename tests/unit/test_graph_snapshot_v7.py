"""Strict v7 discriminator, global proof identity and legacy compatibility."""

import copy

import pytest

from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V6,
)
from dungeonmind.application.graph_snapshot_v6 import UnionGraphV6SnapshotReader
from dungeonmind.application.graph_snapshot_v7 import (
    GRAPH_SCHEMA_V7,
    GraphObjectV7View,
    UnionGraphV7SnapshotReader,
    VersionedUnionGraphSnapshotReaderV7,
)
from dungeonmind.domain.errors import PersistenceIntegrityError
from tests.unit.test_graph_scope_v6 import _payload, _registry
from tests.unit.test_graph_scope_v7 import payload


@pytest.mark.parametrize(
    "change",
    [
        "missing_marker",
        "wrong_marker",
        "kind",
        "blank_label",
        "noncanonical",
        "dangling",
        "duplicate",
        "collision_aspect",
        "collision_relationship",
        "extra",
    ],
)
def test_malformed_or_ambiguous_independent_proofs_fail(change):
    value = payload()
    proof = value["objects"][0]["independent_existence_assertions"][0]
    if change == "missing_marker":
        del value["object_existence_support_schema"]
    elif change == "wrong_marker":
        value["object_existence_support_schema"] = "anything"
    elif change == "kind":
        proof["kind"] = "test:person"
    elif change == "blank_label":
        proof["label"] = " "
    elif change == "noncanonical":
        proof["assertion_metadata"]["canon_state"] = "proposed"
    elif change == "dangling":
        proof["assertion_metadata"]["evidence_ref_ids"] = ["missing"]
    elif change == "duplicate":
        value["objects"][0]["independent_existence_assertions"].append(copy.deepcopy(proof))
    elif change == "collision_aspect":
        proof["assertion_metadata"]["assertion_id"] = "asrt:college-org"
    elif change == "collision_relationship":
        proof["assertion_metadata"]["assertion_id"] = "asrt:leads"
    else:
        proof["unvetted_authority"] = True
    with pytest.raises(PersistenceIntegrityError):
        UnionGraphV7SnapshotReader(_registry()).parse(
            graph_schema=GRAPH_SCHEMA_V7,
            graph_payload=value,
        )


def test_v6_never_silently_accepts_independent_support():
    with pytest.raises(PersistenceIntegrityError):
        UnionGraphV6SnapshotReader(_registry()).parse(
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload=payload(),
        )


def test_versioned_dispatch_accepts_v7_and_retains_legacy_v6_views():
    reader = VersionedUnionGraphSnapshotReaderV7(_registry())
    old = reader.parse(graph_schema=GRAPH_SCHEMA_V6, graph_payload=_payload())
    expected = UnionGraphV6SnapshotReader(_registry()).parse(
        graph_schema=GRAPH_SCHEMA_V6,
        graph_payload=_payload(),
    )
    assert old == expected
    value = reader.parse(graph_schema=GRAPH_SCHEMA_V7, graph_payload=payload())
    assert value.graph_schema == GRAPH_SCHEMA_V7
    assert isinstance(value.objects["obj:college"], GraphObjectV7View)
    assert len(value.objects["obj:college"].independent_existence_assertions) == 1
    assert "ev:other" in value.objects["obj:college"].evidence_ref_ids


@pytest.mark.parametrize("family", ["existence", "alias", "summary", "property"])
def test_proof_identity_cannot_collide_with_any_legacy_object_claim(family):
    value = payload()
    obj = value["objects"][0]
    metadata = copy.deepcopy(obj["assertion_metadata"])
    metadata["assertion_id"] = "asrt:legacy-collision"
    if family == "existence":
        obj["assertion_metadata"] = metadata
    elif family == "alias":
        obj["aliases"] = [{"value": "Alternative", "assertion_metadata": metadata}]
    elif family == "summary":
        obj["summary"] = {"value": "Summary", "assertion_metadata": metadata}
    else:
        obj["properties"] = [
            {
                "property_term": "test:description",
                "value": "Property",
                "assertion_metadata": metadata,
            }
        ]
    obj["independent_existence_assertions"][0]["assertion_metadata"]["assertion_id"] = metadata[
        "assertion_id"
    ]
    with pytest.raises(PersistenceIntegrityError):
        UnionGraphV7SnapshotReader(_registry()).parse(
            graph_schema=GRAPH_SCHEMA_V7,
            graph_payload=value,
        )


def test_historical_dispatcher_remains_closed_to_new_capability():
    from dungeonmind.application.graph_snapshot import VersionedUnionGraphSnapshotReader

    with pytest.raises(PersistenceIntegrityError):
        VersionedUnionGraphSnapshotReader(_registry()).parse(
            graph_schema=GRAPH_SCHEMA_V7,
            graph_payload=payload(),
        )
