"""Pure candidate correctness and explicit structural cache ownership proofs."""

import gc
import random
import re
import weakref
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, fields, replace
from threading import Barrier, Event, Thread

import pytest

from dungeonmind.application.vnext import alias_search_index as owner
from dungeonmind.application.vnext.builder import build_parsed_knowledge_revision
from dungeonmind.application.vnext.errors import SearchReadIntegrityError
from dungeonmind.application.vnext.model import ParsedKnowledgeRevision
from dungeonmind.contracts.vnext.domain import Entity
from dungeonmind.contracts.vnext.knowledge import IdentityAlias
from tests.unit.test_vnext_parsed_knowledge_revision import _make_base_revision


def _parsed(texts=("Old Park pond", "Straße", "🌙 moon"), *, revision="rev:aliases"):
    return build_parsed_knowledge_revision(
        _make_base_revision().model_copy(update={"revision_id": revision}),
        entities=[Entity(entity_id=f"ent:{i}") for i in range(len(texts))],
        aliases=[
            IdentityAlias(
                alias_id=f"alias:{i}",
                entity_id=f"ent:{i}",
                alias_text=text,
                evidence_ref_ids=[],
                standing="established",
            )
            for i, text in enumerate(texts)
        ],
    )


def _contains(text, needle):
    """Independent literal scanner, deliberately not production regex matching."""
    continuation = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_:-")
    position = text.find(needle)
    while position >= 0:
        end = position + len(needle)
        if (position == 0 or text[position - 1] not in continuation) and (
            end == len(text) or text[end] not in continuation
        ):
            return True
        position = text.find(needle, position + 1)
    return False


def _oracle(text, query):
    query = query.strip().casefold()
    text = text.casefold()
    tokens = sorted(set(t for t in re.findall(r"[a-z0-9]+", query) if len(t) > 1))
    matches = []
    for token in tokens:
        alternatives = [token]
        if token.endswith("s"):
            if len(token) > 3:
                alternatives.append(token[:-1])
        else:
            alternatives.append(token + "s")
        if any(_contains(text, word) for word in alternatives):
            matches.append(token)
    kinds = tuple(
        kind
        for kind, yes in (
            ("exact", text.strip() == query),
            ("phrase", _contains(text, query)),
            ("token", bool(matches)),
        )
        if yes
    )
    return kinds, tuple(matches)


def _terms(query):
    normalized = owner.normalize_alias_query(query)
    tokens = owner.alias_query_tokens(normalized)
    return (
        normalized,
        *(variant for token in tokens for variant in owner.alias_token_variants(token)),
    )


@pytest.mark.parametrize(
    "text,query",
    [
        ("  STRASSE  ", "Straße"),
        ("Alte Straße crossing", "strasse"),
        ("Old Park pond crossing", "Park pond"),
        ("lanterns", "lantern"),
        ("lantern", "lanterns"),
        ("bus", "bu"),
        ("bus", "buses"),
        ("Astoria", "Astor"),
        ("obj:x-extra", "obj:x"),
        ("obj:x", "obj:x"),
        ("foo_bar", "bar"),
        ("foo:bar", "bar"),
        ("foo-bar", "bar"),
        ("foo/bar", "bar"),
        ("🌙 café", "🌙"),
        ("é rouge", "é"),
        ("a/b", "a/b"),
        ("a.b", "."),
        ("a b", "a b"),
        ("THE old", "the"),
        ("[a+b]", "a+b"),
        ("\r\nPark\r\n", "park"),
        ("İstanbul", "i̇stanbul"),
    ],
)
def test_matching_and_candidates_agree_with_independent_oracle(text, query):
    parsed = _parsed((text, "unrelated"))
    index = owner._build_alias_search_index(parsed)
    normalized = owner.normalize_alias_query(query)
    actual = owner.alias_match_text(text, normalized, owner.alias_query_tokens(normalized))
    assert actual == _oracle(text, query)
    if actual[0]:
        assert "alias:0" in index.candidate_ids(_terms(query))


def test_generated_candidates_never_omit_a_brute_force_match():
    rng = random.Random(20261119)
    alphabet = "abcsST ßé🌙_:-/.12"
    texts = tuple("".join(rng.choices(alphabet, k=24)) for _ in range(40))
    parsed = _parsed(texts)
    index = owner._build_alias_search_index(parsed)
    queries = ["".join(rng.choices(alphabet, k=rng.randint(1, 8))) for _ in range(120)]
    queries += [
        text[start : start + width] for text in texts for start, width in ((0, 1), (4, 2), (6, 5))
    ]
    for query in queries:
        if not query.strip():
            continue
        candidates = index.candidate_ids(_terms(query))
        assert candidates == tuple(sorted(set(candidates)))
        for i, text in enumerate(texts):
            expected = _oracle(text, query)
            assert (
                owner.alias_match_text(
                    text,
                    owner.normalize_alias_query(query),
                    owner.alias_query_tokens(owner.normalize_alias_query(query)),
                )
                == expected
            )
            if expected[0]:
                assert f"alias:{i}" in candidates, (text, query)


def test_posting_counts_permutation_immutability_and_candidate_locality():
    parsed = _parsed(("Park pond", "unrelated", "Park pond"))
    index = owner._build_alias_search_index(parsed)
    memberships = {
        (text.strip().casefold()[i : i + width], f"alias:{j}")
        for j, text in enumerate(("Park pond", "unrelated", "Park pond"))
        for width in (1, 2, 3)
        for i in range(len(text.strip().casefold()) - width + 1)
    }
    assert index.posting_count == len(memberships)
    assert index.alias_count == 3
    assert index.candidate_ids(("park pond",)) == ("alias:0", "alias:2")
    assert index.candidate_ids(()) == ()
    reordered = replace(
        parsed,
        aliases_by_id=type(parsed.aliases_by_id)(
            list(reversed(tuple(parsed.aliases_by_id.items())))
        ),
    )
    assert owner._build_alias_search_index(reordered) == index
    with pytest.raises(FrozenInstanceError):
        index.alias_count = 4
    with pytest.raises(TypeError):
        index.postings["park"] = ("forged",)
    assert all(type(ids) is tuple for ids in index.postings.values())
    assert (
        parsed.semantic_digest == _parsed(("Park pond", "unrelated", "Park pond")).semantic_digest
    )


@pytest.mark.parametrize("query", [None, False, 3, b"park", "", " \r\n\t"])
def test_invalid_queries_fail_with_existing_search_error(query):
    with pytest.raises(SearchReadIntegrityError):
        owner.normalize_alias_query(query)


@pytest.mark.parametrize(
    "entries,postings",
    [(0, 1), (-1, 1), (True, 1), (1.5, 1), (1, 0), (1, -1), (1, False), (1, 1.5)],
)
def test_invalid_cache_capacities(entries, postings):
    with pytest.raises(SearchReadIntegrityError):
        owner.AliasSearchIndexCache(entries, postings)


def test_complete_identity_fields_and_no_index_rebuild_on_hit(monkeypatch):
    parsed = _parsed()
    key = owner.index_key_for_parsed(parsed)
    assert key.algorithm_version == owner.ALIAS_SEARCH_INDEX_VERSION
    cache = owner.AliasSearchIndexCache(10, 10000)
    first, hit = cache.get_or_build(parsed)
    assert not hit

    def forbidden(_parsed):
        pytest.fail("cache hit rebuilt alias index")

    with monkeypatch.context() as scope:
        scope.setattr(owner, "_build_alias_search_index", forbidden)
        assert cache.get_or_build(parsed) == (first, True)
    changes = [
        replace(parsed, identity=replace(parsed.identity, **{field: "different"}))
        for field in ("space_id", "revision_id", "graph_payload_sha256")
    ]
    changes += [
        replace(parsed, **{field: "different"})
        for field in ("semantic_digest", "format_version", "compatibility_key")
    ]
    for changed in changes:
        assert owner.index_key_for_parsed(changed) != key
        assert cache.get_or_build(changed)[1] is False
    monkeypatch.setattr(owner, "ALIAS_SEARCH_INDEX_VERSION", "algorithm:v2")
    assert owner.index_key_for_parsed(parsed) != key
    assert cache.get_or_build(parsed)[1] is False
    with pytest.raises(SearchReadIntegrityError):
        cache.get_or_build(replace(parsed, semantic_digest=""))
    with pytest.raises(SearchReadIntegrityError):
        cache.get_or_build(object())


def test_entry_posting_lru_eviction_clear_and_oversize():
    one, two, three = (_parsed(("same alias",), revision=f"rev:{i}") for i in range(3))
    size = owner._build_alias_search_index(one).posting_count
    cache = owner.AliasSearchIndexCache(3, size * 2)
    assert not cache.get_or_build(one)[1]
    assert not cache.get_or_build(two)[1]
    assert cache.get_or_build(one)[1]
    assert not cache.get_or_build(three)[1]
    assert cache.entry_count == 2 and cache.posting_count == size * 2
    assert cache.get_or_build(one)[1]
    assert not cache.get_or_build(two)[1]  # least-recently-used revision was evicted
    cache.clear()
    assert cache.entry_count == cache.posting_count == 0
    entries = owner.AliasSearchIndexCache(1, size * 3)
    entries.get_or_build(one)
    entries.get_or_build(two)
    assert entries.entry_count == 1 and not entries.get_or_build(one)[1]
    tiny = owner.AliasSearchIndexCache(1, size - 1)
    empty = _parsed(())
    tiny.get_or_build(empty)
    assert not tiny.get_or_build(one)[1]
    assert not tiny.get_or_build(one)[1]
    assert tiny.get_or_build(empty)[1]  # oversized misses preserve retained entries
    assert tiny.entry_count == 1 and tiny.posting_count == 0


def test_cache_retains_no_parsed_object():
    class WeakParsed(ParsedKnowledgeRevision):
        __slots__ = ("__weakref__",)

    parsed = _parsed()
    weak_parsed = WeakParsed(
        **{field.name: getattr(parsed, field.name) for field in fields(parsed) if field.init}
    )
    reference = weakref.ref(weak_parsed)
    cache = owner.AliasSearchIndexCache(2, 10000)
    index, _ = cache.get_or_build(weak_parsed)
    del weak_parsed, parsed
    gc.collect()
    assert reference() is None
    assert index.candidate_ids(("park",)) == ("alias:0",)


def test_synchronized_same_key_build_is_once_and_returns_immutable_index(monkeypatch):
    parsed = _parsed()
    cache = owner.AliasSearchIndexCache(2, 10000)
    barrier = Barrier(8)
    calls = []
    build = owner._build_alias_search_index

    def counted(value):
        calls.append(value.revision_id)
        return build(value)

    monkeypatch.setattr(owner, "_build_alias_search_index", counted)

    def query(_):
        barrier.wait(timeout=10)
        return cache.get_or_build(parsed)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(query, range(8)))
    assert len(calls) == 1
    assert sum(hit for _, hit in results) == 7
    assert all(index is results[0][0] for index, _ in results)
    assert cache.posting_count == results[0][0].posting_count


def test_clear_serializes_with_build_and_failed_build_does_not_poison(monkeypatch):
    parsed = _parsed()
    cache = owner.AliasSearchIndexCache(1, 10000)
    entered, release, clearing = Event(), Event(), Event()
    build = owner._build_alias_search_index

    def paused(value):
        entered.set()
        assert release.wait(timeout=10)
        return build(value)

    monkeypatch.setattr(owner, "_build_alias_search_index", paused)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(cache.get_or_build, parsed)
        assert entered.wait(timeout=10)

        def clear():
            clearing.set()
            cache.clear()

        thread = Thread(target=clear)
        thread.start()
        assert clearing.wait(timeout=10)
        release.set()
        assert future.result(timeout=10)[1] is False
        thread.join(timeout=10)
        assert not thread.is_alive()
    assert cache.entry_count == cache.posting_count == 0

    def fail(_value):
        raise RuntimeError("synthetic build failure")

    monkeypatch.setattr(owner, "_build_alias_search_index", fail)
    with pytest.raises(RuntimeError, match="synthetic build failure"):
        cache.get_or_build(parsed)
    assert cache.entry_count == cache.posting_count == 0
    monkeypatch.setattr(owner, "_build_alias_search_index", build)
    assert cache.get_or_build(parsed)[1] is False


def test_malformed_identity_uses_search_error_not_attribute_error():
    parsed = _parsed()
    with pytest.raises(SearchReadIntegrityError, match="identity"):
        owner.index_key_for_parsed(replace(parsed, identity=None))


def test_unrelated_postings_do_not_expand_selected_phrase_candidates():
    texts = ("Park pond", *(f"Unrelated mountain chapter {i}" for i in range(128)))
    index = owner._build_alias_search_index(_parsed(texts))
    assert index.alias_count == 129
    assert index.candidate_ids(_terms("Park pond")) == ("alias:0",)


def test_token_policy_has_no_stopwords_and_preserves_short_phrase_queries():
    assert owner.alias_query_tokens("the old a i pond") == ("old", "pond", "the")
    assert owner.alias_token_variants("lantern") == ("lantern", "lanterns")
    assert owner.alias_token_variants("lanterns") == ("lantern", "lanterns")
    assert owner.alias_token_variants("bus") == ("bus",)
    index = owner._build_alias_search_index(_parsed(("🌙 café", "é rouge", "a/b")))
    for query, expected in (("🌙", "alias:0"), ("é", "alias:1"), ("a/b", "alias:2")):
        assert expected in index.candidate_ids(_terms(query))
