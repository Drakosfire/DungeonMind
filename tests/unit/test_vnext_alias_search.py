"""Authorized alias witnesses and fresh-source/cache composition proofs."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from dungeonmind.application.vnext.alias_search import (
    AliasSearchReadService,
    _capture_alias_search_trace,
)
from dungeonmind.application.vnext.alias_search_index import AliasSearchIndexCache
from dungeonmind.application.vnext.errors import SearchReadIntegrityError
from dungeonmind.application.vnext.read_context import KnowledgeReadContext
from dungeonmind.contracts.vnext.common import KnowledgeStanding, LabelsAllVisibility
from dungeonmind.contracts.vnext.domain import Entity
from dungeonmind.contracts.vnext.knowledge import IdentityAlias
from dungeonmind.domain.errors import PersistenceIntegrityError
from tests.unit.test_vnext_search import _artifact, _evidence, _lab_context, _revision

SVC = AliasSearchReadService()


def alias(
    identifier, text, entity="ent:one", *, evidence=(), standing=KnowledgeStanding.ESTABLISHED
):
    return IdentityAlias(
        alias_id=identifier,
        entity_id=entity,
        alias_text=text,
        evidence_ref_ids=list(evidence),
        standing=standing,
    )


def context(aliases, **kwargs):
    return _lab_context(
        entities=[
            Entity(entity_id=identifier) for identifier in sorted({a.entity_id for a in aliases})
        ],
        assertions=[],
        aliases=aliases,
        **kwargs,
    )


def fresh(old, reader):
    return KnowledgeReadContext(
        parsed=old.parsed,
        request=old.request,
        domain_contract=old.domain_contract,
        semantic_profile=old.semantic_profile,
        domain_policy=old.domain_policy,
        source_reader=reader,
    )


def cache():
    return AliasSearchIndexCache(max_entries=2, max_postings=500_000)


@pytest.mark.parametrize(
    "text,query,kinds",
    [
        ("  Straẞe Watch  ", "STRASSE WATCH", ("exact", "phrase", "token")),
        ("Old Park pond crossing", "Park pond", ("phrase", "token")),
        ("Copper lantern keeper", "lanterns", ("token",)),
        ("River guards", "guard", ("token",)),
        ("漁師の家", "漁師", ("phrase",)),
        ("The 🧙‍♀️ crossing", "🧙‍♀️", ("phrase",)),
        ("Ring !!! watch", "!!!", ("phrase",)),
    ],
)
def test_public_alias_witness_matches_without_assertion_presence(text, query, kinds):
    ctx, reader = context([alias("alias:one", text)])
    result = SVC.search_aliases(ctx, query)
    (hit,) = result.hits
    assert hit.alias.alias_text == text
    assert hit.match_kinds == kinds
    assert not hit.ambiguous and result.completeness.status == "complete"
    assert reader.snapshot_call_count == 0
    with pytest.raises(FrozenInstanceError):
        hit.alias.alias_text = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.limit = 1  # type: ignore[misc]


@pytest.mark.parametrize(
    "text,query",
    [
        ("Astoria", "Astor"),
        ("obj:npc-mere-astor", "astor"),
        ("key:keeper", "keeper"),
        ("keeper_word", "keeper"),
    ],
)
def test_prefixes_and_opaque_id_fragments_do_not_gain_alias_matches(text, query):
    ctx, _ = context([alias("alias:one", text)])
    assert not SVC.search_aliases(ctx, query).hits


def test_ambiguity_is_authorized_and_computed_before_result_limit():
    aliases = [alias("alias:b", "COBALT", "ent:two"), alias("alias:a", "Cobalt", "ent:one")]
    ctx, _ = context(aliases)
    result = SVC.search_aliases(ctx, "cobalt", limit=1)
    assert len(result.hits) == 1 and result.hits[0].ambiguous
    assert result.completeness.status == "partial"
    assert result.completeness.reason == "result_limit"
    zero = SVC.search_aliases(ctx, "cobalt", limit=0)
    assert not zero.hits and zero.completeness.status == "partial"
    full = SVC.search_aliases(ctx, "cobalt", limit=len(ctx.parsed.aliases_by_id))
    assert [hit.alias.alias_id for hit in full.hits] == ["alias:a", "alias:b"]
    assert full.completeness.status == "complete"
    repeated_entity, _ = context([alias("alias:a", "Cobalt"), alias("alias:b", "COBALT")])
    assert all(not hit.ambiguous for hit in SVC.search_aliases(repeated_entity, "cobalt").hits)


def test_hidden_alias_cannot_suppress_or_occupy_slots_or_change_public_digest():
    visible = alias("alias:public", "Cobalt", evidence=("ev:public",))
    hidden = alias("alias:000hidden", "COBALT", "ent:hidden", evidence=("ev:hidden",))
    ev = [
        _evidence("ev:public", "src:public", "rev:public"),
        _evidence("ev:hidden", "src:hidden", "rev:hidden"),
    ]
    artifacts = {
        "src:public": _artifact("src:public", "rev:public"),
        "src:hidden": _artifact("src:hidden", "rev:hidden").model_copy(
            update={"visibility": LabelsAllVisibility(labels=["test:hidden"])}
        ),
    }
    revisions = {
        "rev:public": _revision("rev:public", "src:public"),
        "rev:hidden": _revision("rev:hidden", "src:hidden"),
    }
    baseline, _ = context([visible], evidence=ev, artifacts=artifacts, revisions=revisions)
    extended, _ = context([visible, hidden], evidence=ev, artifacts=artifacts, revisions=revisions)
    expected = SVC.search_aliases(baseline, "cobalt", limit=1)
    actual = SVC.search_aliases(extended, "cobalt", limit=1)
    assert actual == expected
    assert not actual.hits[0].ambiguous and actual.completeness.status == "complete"
    assert "hidden" not in repr(actual)
    assert "candidate" not in repr(actual) and "snapshot_calls" not in repr(actual)


@pytest.mark.parametrize(
    "fault", ["standing", "missing_artifact", "missing_revision", "withdrawn", "wrong_binding"]
)
def test_existing_alias_source_and_standing_fail_closed(fault):
    item = alias(
        "alias:one",
        "Cobalt",
        evidence=("evidence:lab",),
        standing=KnowledgeStanding.PROVISIONAL
        if fault == "standing"
        else KnowledgeStanding.ESTABLISHED,
    )
    artifacts = (
        {}
        if fault == "missing_artifact"
        else {"src:lab": _artifact(status="retracted" if fault == "withdrawn" else "active")}
    )
    revisions = (
        {}
        if fault == "missing_revision"
        else {
            "srcrev:lab": _revision(
                artifact_id="src:wrong" if fault == "wrong_binding" else "src:lab"
            )
        }
    )
    ctx, _ = context([item], artifacts=artifacts, revisions=revisions)
    assert not SVC.search_aliases(ctx, "cobalt").hits


def test_reused_candidate_index_reauthorizes_fresh_context_after_withdrawal():
    ctx, reader = context([alias("alias:one", "Cobalt", evidence=("evidence:lab",))])
    structural = cache()
    with _capture_alias_search_trace() as traces:
        first = SVC.search_aliases(ctx, "cobalt", index_cache=structural)
        reader._artifacts["src:lab"] = _artifact(status="retracted")
        second = SVC.search_aliases(fresh(ctx, reader), "cobalt", index_cache=structural)
    assert first.hits and not second.hits
    assert not traces[0].index_cache_hit and traces[1].index_cache_hit
    assert traces[1].index_build_aliases_visited == 0
    assert traces[0].provenance_snapshot_calls == traces[1].provenance_snapshot_calls == 1
    assert structural.entry_count == 1


def test_corrupt_provenance_protocol_remains_a_persistence_error(monkeypatch):
    ctx, _ = context([alias("alias:one", "Cobalt", evidence=("evidence:lab",))])
    kind = type(ctx.source_reader)
    original = kind.get_provenance_snapshot

    def corrupt(self, **kwargs):
        return replace(original(self, **kwargs), requested_artifact_ids=())

    monkeypatch.setattr(kind, "get_provenance_snapshot", corrupt)
    with pytest.raises(PersistenceIntegrityError):
        SVC.search_aliases(ctx, "cobalt")


def test_unrelated_aliases_do_not_expand_candidate_admission_or_source_fetches():
    aliases = [alias("alias:target", "Cobalt lantern", evidence=("evidence:lab",))]
    aliases += [
        alias(f"alias:decoy:{i}", f"zzzz unrelated {i}", f"ent:decoy:{i}") for i in range(3000)
    ]
    ctx, reader = context(aliases)
    structural = cache()
    with _capture_alias_search_trace() as traces:
        first = SVC.search_aliases(ctx, "cobalt lantern", index_cache=structural)
        second = SVC.search_aliases(fresh(ctx, reader), "cobalt lantern", index_cache=structural)
    assert first == second and len(first.hits) == 1
    assert traces[0].index_build_aliases_visited == len(aliases)
    assert traces[1].index_build_aliases_visited == 0
    for work in traces:
        assert (
            work.structural_candidate_aliases
            == work.matched_aliases
            == work.authorized_aliases
            == 1
        )
        assert work.evidence_refs_requested == 1
        assert work.source_artifact_ids_requested == work.source_revision_ids_requested == 1
        assert work.provenance_snapshot_calls == 1


def test_order_digest_and_cache_are_stable_under_primary_input_permutation():
    aliases = [
        alias("alias:z", "Old cobalt crossing", "ent:z"),
        alias("alias:b", "Cobalt", "ent:b"),
        alias("alias:a", "COBALT", "ent:a"),
    ]
    left, _ = context(aliases)
    right, _ = context(list(reversed(aliases)))
    structural = cache()
    with _capture_alias_search_trace() as traces:
        first = SVC.search_aliases(left, "cobalt", index_cache=structural)
        second = SVC.search_aliases(right, "cobalt", index_cache=structural)
    assert first == second
    assert [h.alias.alias_id for h in first.hits] == ["alias:a", "alias:b", "alias:z"]
    assert traces[1].index_cache_hit


@pytest.mark.parametrize(
    "query,limit,structural",
    [
        (" ", 1, None),
        (None, 1, None),
        ("cobalt", -1, None),
        ("cobalt", True, None),
        ("cobalt", 1.0, None),
        ("cobalt", 1, object()),
    ],
)
def test_invalid_public_request_refuses_before_admission(query, limit, structural):
    ctx, reader = context([alias("alias:one", "Cobalt")])
    with pytest.raises(SearchReadIntegrityError):
        SVC.search_aliases(ctx, query, limit=limit, index_cache=structural)
    assert reader.snapshot_call_count == 0


def test_foreign_cached_index_refuses_before_source_authorization(monkeypatch):
    current, reader = context([alias("alias:one", "Cobalt", evidence=("evidence:lab",))])
    foreign, _ = context([alias("alias:two", "Cobalt")], space_id="space:foreign")
    structural = cache()
    foreign_index, _ = structural.get_or_build(foreign.parsed)
    monkeypatch.setattr(
        AliasSearchIndexCache, "get_or_build", lambda self, parsed: (foreign_index, True)
    )
    with pytest.raises(SearchReadIntegrityError, match="pinned"):
        SVC.search_aliases(current, "cobalt", index_cache=structural)
    assert reader.snapshot_call_count == 0
