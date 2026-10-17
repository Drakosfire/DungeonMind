"""Copy-work regression plus mutation isolation for the guarded scalar contract."""

import pytest

from dungeonmind.application.graph_snapshot import (
    GraphEvidenceRecord,
    ParsedGraphSnapshot,
    _isolate_evidence_record,
)
from dungeonmind.application.parsed_revision_cache import ParsedImmutableRevisionCache
from dungeonmind.contracts.evidence import EvidenceRefV2


def _v2():
    return EvidenceRefV2(
        evidence_ref_id="ev:copy", source_artifact_id="src:copy",
        source_revision_id="srcrev:copy", source_domain_key="buddy.worldbuilding",
        source_domain="worldbuilding", evidence_role="support", can_open_source=True,
        can_highlight_span=True, session_id="session:copy", source_span_ref_id="span:copy",
        locator="source://copy", uri=None, source_locator="line:3", line_ref="L3",
    )


@pytest.mark.parametrize("factory", [_v2, lambda: GraphEvidenceRecord(
    evidence_ref_id="ev:v1", source_artifact_id="src:v1", source_domain="worldbuilding",
)])
def test_record_copy_preserves_type_values_and_owns_model_state(factory):
    original = factory()
    clone = _isolate_evidence_record(original)
    assert type(clone) is type(original)
    assert clone.model_dump() == original.model_dump()
    assert clone is not original
    assert clone.__dict__ is not original.__dict__
    assert clone.model_fields_set is not original.model_fields_set
    clone.locator = "caller://changed"
    clone.model_fields_set.clear()
    assert original.locator != clone.locator
    assert original.model_fields_set


def test_exact_scalar_record_avoids_recursive_copy(monkeypatch):
    original = _v2()

    def unexpected_recursion(*args, **kwargs):
        raise AssertionError("exact scalar record should not recursively copy")

    monkeypatch.setattr(EvidenceRefV2, "__deepcopy__", unexpected_recursion)
    assert _isolate_evidence_record(original).model_dump() == original.model_dump()


@pytest.mark.parametrize("field", ["locator", "source_locator", "line_ref"])
def test_mutable_value_in_scalar_slot_falls_back_to_deep_isolation(field):
    # Models allow assignment without validation. The cache must still isolate
    # such unexpected state, not silently assume that annotations enforce it.
    original = _v2().model_copy(update={field: {"nested": ["original"]}})
    clone = _isolate_evidence_record(original)
    getattr(clone, field)["nested"].append("caller")
    assert getattr(original, field) == {"nested": ["original"]}


def test_future_subclass_with_mutable_fields_keeps_deep_isolation():
    class FutureEvidence(EvidenceRefV2):
        annotations: dict[str, list[str]]

    original = FutureEvidence(**_v2().model_dump(), annotations={"notes": ["original"]})
    clone = _isolate_evidence_record(original)
    clone.annotations["notes"].append("caller")
    assert original.annotations == {"notes": ["original"]}


@pytest.mark.parametrize("attribute", ["__pydantic_extra__", "__pydantic_private__"])
def test_extra_or_private_model_state_keeps_deep_isolation(attribute):
    original = _v2()
    object.__setattr__(original, attribute, {"notes": ["original"]})
    clone = _isolate_evidence_record(original)
    getattr(clone, attribute)["notes"].append("caller")
    assert getattr(original, attribute) == {"notes": ["original"]}


def test_scalar_subclass_with_mutable_attributes_keeps_deep_isolation():
    class AnnotatedString(str):
        pass

    original = _v2()
    original.locator = AnnotatedString("source://copy")
    original.locator.notes = ["original"]
    clone = _isolate_evidence_record(original)
    clone.locator.notes.append("caller")
    assert original.locator.notes == ["original"]


@pytest.mark.parametrize("mutable", [False, True])
def test_cache_put_and_each_return_own_scalar_and_fallback_records(mutable):
    record = _v2()
    if mutable:
        record = record.model_copy(update={"locator": ["original"]})
    parsed = ParsedGraphSnapshot(
        world_id="world:copy", graph_schema="dm_union_graph_v5",
        objects={}, relationships={}, evidence={record.evidence_ref_id: record},
    )
    cache = ParsedImmutableRevisionCache()
    cache.put("world:copy", "rev:copy", parsed, compatibility_id="reader:copy")
    first = cache.get("world:copy", "rev:copy", compatibility_id="reader:copy")
    if mutable:
        first.evidence[record.evidence_ref_id].locator.append("caller")
        record.locator.append("loader")
    else:
        first.evidence[record.evidence_ref_id].locator = "caller://changed"
        record.locator = "loader://changed"
    second = cache.get("world:copy", "rev:copy", compatibility_id="reader:copy")
    expected = ["original"] if mutable else "source://copy"
    assert second.evidence[record.evidence_ref_id].locator == expected
