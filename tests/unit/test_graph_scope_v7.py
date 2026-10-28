"""Independent proof admission must not weaken joint evidence or field secrecy."""

import copy

import pytest

from dungeonmind.application.graph_scope_v7 import (
    project_scoped_snapshot_v7 as project_scoped_snapshot,
)
from dungeonmind.application.graph_snapshot_v7 import (
    EXISTENCE_SUPPORT_SCHEMA,
    GRAPH_SCHEMA_V7,
    UnionGraphV7SnapshotReader,
)
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.projection_v2 import ScopeModeV2
from tests.unit.test_graph_scope_v6 import (
    CAMPAIGN_ID,
    OTHER_CAMPAIGN_ID,
    WORLD_ID,
    _meta,
    _payload,
    _registry,
    _seed_sources,
)


def payload():
    value = _payload()
    value["object_existence_support_schema"] = EXISTENCE_SUPPORT_SCHEMA
    old = copy.deepcopy(value["evidence_refs"][0])
    old.update(
        evidence_ref_id="ev:other", source_artifact_id="src:other", source_revision_id="rev:other"
    )
    value["evidence_refs"].append(old)
    value["objects"][0]["independent_existence_assertions"] = [
        {
            "label": "Other Campaign Academy",
            "kind": "test:location",
            "assertion_metadata": _meta(
                "asrt:other-existence", evidence=("ev:other",), campaign_scope=OTHER_CAMPAIGN_ID
            ),
        }
    ]
    return value


def sources():
    value = _seed_sources()
    artifact = value.get_artifact("src:v6-notes")
    revision = value.get_revision("srcrev:v6-notes-v1")
    value.put_artifact(
        artifact.model_copy(
            update={
                "source_artifact_id": "src:other",
                "campaign_id": OTHER_CAMPAIGN_ID,
                "current_revision_id": "rev:other",
            }
        )
    )
    value.put_revision(
        revision.model_copy(
            update={
                "source_revision_id": "rev:other",
                "source_artifact_id": "src:other",
            }
        )
    )
    return value


def project(value, campaign=CAMPAIGN_ID, *, audience=Admissibility.PLAYER, source=None):
    parsed = UnionGraphV7SnapshotReader(_registry()).parse(
        graph_schema=GRAPH_SCHEMA_V7,
        graph_payload=value,
    )
    return project_scoped_snapshot(
        parsed,
        sources=source or sources(),
        world_id=WORLD_ID,
        campaign_id=campaign,
        scope_mode=ScopeModeV2.CAMPAIGN if campaign else ScopeModeV2.WORLD_CROSS_CAMPAIGN,
        admissibility=audience,
    )


@pytest.mark.parametrize(
    "campaign,label,evidence",
    [
        (CAMPAIGN_ID, "Wizard College", ["ev:v6"]),
        (OTHER_CAMPAIGN_ID, "Other Campaign Academy", ["ev:other"]),
    ],
)
def test_independent_campaign_proofs_keep_identity_without_label_or_evidence_leak(
    campaign,
    label,
    evidence,
):
    scoped = project(payload(), campaign).snapshot
    obj = scoped.objects["obj:college"]
    assert obj.label == label
    assert obj.core_evidence_ref_ids == evidence
    hidden = "Other Campaign Academy" if campaign == CAMPAIGN_ID else "Wizard College"
    assert hidden not in str(obj.model_dump())
    assert hidden.casefold() not in scoped.label_index
    assert hidden.casefold() not in scoped.alias_index
    assert "independent_existence_assertions" not in obj.model_dump()


def test_cross_campaign_admits_all_supported_labels_with_original_preferred():
    obj = project(payload(), None).snapshot.objects["obj:college"]
    assert obj.label == "Wizard College"
    assert "Other Campaign Academy" in obj.aliases
    assert obj.core_evidence_ref_ids == ["ev:v6", "ev:other"]


@pytest.mark.parametrize("campaign", [CAMPAIGN_ID, OTHER_CAMPAIGN_ID])
def test_joint_evidence_stays_conjunctive(campaign):
    value = payload()
    obj = value["objects"][0]
    obj["independent_existence_assertions"] = []
    obj["assertion_metadata"]["campaign_scope"] = None
    obj["assertion_metadata"]["evidence_ref_ids"] = ["ev:v6", "ev:other"]
    assert "obj:college" not in project(value, campaign).snapshot.objects


def test_mixed_evidence_inside_alternative_is_not_treated_as_disjunction():
    value = payload()
    proof = value["objects"][0]["independent_existence_assertions"][0]
    proof["assertion_metadata"]["evidence_ref_ids"].append("ev:v6")
    assert "obj:college" not in project(value, OTHER_CAMPAIGN_ID).snapshot.objects


def test_private_alternative_does_not_admit_player_but_gm_can_read():
    value = payload()
    value["objects"][0]["independent_existence_assertions"][0]["assertion_metadata"][
        "visibility"
    ] = "gm"
    assert "obj:college" not in project(value, OTHER_CAMPAIGN_ID).snapshot.objects
    assert (
        "obj:college"
        in project(
            value,
            OTHER_CAMPAIGN_ID,
            audience=Admissibility.GM,
        ).snapshot.objects
    )


def test_alternative_does_not_admit_other_campaign_fields_or_relationships():
    value = payload()
    value["objects"][0]["aliases"] = [
        {
            "value": "Secret C1 alias",
            "assertion_metadata": _meta("asrt:secret-alias", visibility="gm"),
        }
    ]
    value["objects"][0]["summary"] = {
        "value": "Secret C1 summary",
        "assertion_metadata": _meta("asrt:secret-summary", visibility="gm"),
    }
    value["objects"][0]["properties"] = [
        {
            "property_term": "test:secret",
            "value": "C1 private property",
            "assertion_metadata": _meta("asrt:secret-property", visibility="gm"),
        }
    ]
    obj = project(value, OTHER_CAMPAIGN_ID).snapshot.objects["obj:college"]
    assert obj.aliases == [] and obj.summary is None and obj.admitted_aspect_assertions == []
    assert obj.admitted_property_assertions == []
    assert project(value, OTHER_CAMPAIGN_ID).snapshot.relationships == {}


def test_missing_alternative_source_fails_closed_without_revealing_label():
    value = sources()
    del value._artifacts["src:other"]
    scoped = project(payload(), OTHER_CAMPAIGN_ID, source=value)
    assert "obj:college" not in scoped.snapshot.objects
    assert "Other Campaign Academy" not in str(scoped.snapshot.label_index)


def test_reprojection_preserves_only_already_admitted_proofs():
    for campaign in [CAMPAIGN_ID, OTHER_CAMPAIGN_ID, None]:
        first = project(payload(), campaign).snapshot
        second = project_scoped_snapshot(
            first,
            sources=sources(),
            world_id=WORLD_ID,
            campaign_id=campaign,
            scope_mode=ScopeModeV2.CAMPAIGN if campaign else ScopeModeV2.WORLD_CROSS_CAMPAIGN,
            admissibility=Admissibility.PLAYER,
        ).snapshot
        assert second.objects == first.objects
        assert second.relationships == first.relationships
        assert second.label_index == first.label_index
        assert second.alias_index == first.alias_index


def test_alternative_selection_is_assertion_order_not_payload_order():
    value = payload()
    a = value["objects"][0]["independent_existence_assertions"][0]
    b = copy.deepcopy(a)
    b["label"] = "Earlier proof label"
    b["assertion_metadata"]["assertion_id"] = "asrt:a-earlier-proof"
    value["objects"][0]["independent_existence_assertions"].append(b)
    first = project(value, OTHER_CAMPAIGN_ID).snapshot.objects["obj:college"]
    value["objects"][0]["independent_existence_assertions"].reverse()
    second = project(value, OTHER_CAMPAIGN_ID).snapshot.objects["obj:college"]
    assert first == second and first.label == "Earlier proof label"


def test_selected_assertion_rows_expose_only_admitted_labeled_proofs():
    from dungeonmind.application.world_graph_retrieval import _selected_object_assertion_rows

    for campaign, count in [(CAMPAIGN_ID, 1), (OTHER_CAMPAIGN_ID, 1), (None, 2)]:
        obj = project(payload(), campaign).snapshot.objects["obj:college"]
        rows = [r for r in _selected_object_assertion_rows(obj) if r.assertion_kind == "existence"]
        assert len(rows) == count
        assert {r.existence_kind for r in rows} == {"test:location"}
        assert all(r.existence_label and r.assertion_metadata and r.evidence_ref_ids for r in rows)
        if campaign == OTHER_CAMPAIGN_ID:
            assert rows[0].existence_label == "Other Campaign Academy"
            assert rows[0].evidence_ref_ids == ("ev:other",)


def test_retracted_source_does_not_admit_independent_proof():
    from dungeonmind.contracts.evidence import SourceStatus

    source = sources()
    artifact = source.get_artifact("src:other")
    source._artifacts["src:other"] = artifact.model_copy(update={"status": SourceStatus.RETRACTED})
    assert (
        "obj:college" not in project(payload(), OTHER_CAMPAIGN_ID, source=source).snapshot.objects
    )


def test_explicit_projector_delegates_legacy_snapshots_without_behavior_change():
    from dungeonmind.application.graph_scope import project_scoped_snapshot as historical
    from dungeonmind.application.graph_snapshot import GRAPH_SCHEMA_V6
    from dungeonmind.application.graph_snapshot_v6 import UnionGraphV6SnapshotReader

    parsed = UnionGraphV6SnapshotReader(_registry()).parse(
        graph_schema=GRAPH_SCHEMA_V6,
        graph_payload=_payload(),
    )
    args = dict(
        sources=sources(),
        world_id=WORLD_ID,
        campaign_id=CAMPAIGN_ID,
        admissibility=Admissibility.PLAYER,
    )
    assert project_scoped_snapshot(parsed, **args) == historical(parsed, **args)
