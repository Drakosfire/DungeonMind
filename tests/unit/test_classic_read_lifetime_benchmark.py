"""Lock experiment comparisons to the actual Core read boundary and work counts."""

import pytest
from benchmarks.classic_read_lifetime import build_fixture, measure, run_experiment

from dungeonmind.application.parsed_revision_cache import ParsedImmutableRevisionCache
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.vocabulary import Visibility


def test_fresh_services_share_only_parse_and_keep_other_work_fresh():
    report = run_experiment([10], 3)
    cell = report["cells"][0]
    local = cell["summary"]["factory_local"]["total_work"]
    shared = cell["summary"]["shared_parse"]["total_work"]
    assert local["reader.parse"] == 3
    assert shared["reader.parse"] == 1
    for counts in (local, shared):
        assert counts["graph.get_revision"] == 3
        assert counts["sources.get_provenance_snapshot"] == 3
        assert counts["initializations.get_for_world"] == 3
    assert local["cache.isolated_snapshots"] == 6
    assert shared["cache.isolated_snapshots"] == 4
    assert [sample["cache_hit"] for sample in cell["samples"]["shared_parse"]] == [
        False,
        True,
        True,
    ]
    assert cell["order"] == [
        "factory_local",
        "shared_parse",
        "shared_parse",
        "factory_local",
        "factory_local",
        "shared_parse",
    ]
    assert report["connections"] is None and report["sql_statements"] is None


def test_shared_parse_across_fresh_services_does_not_reuse_admission():
    fixture = build_fixture(10)
    fixture.target = "obj:000000"
    fixture.request = fixture.request.model_copy(update={"admissibility": Admissibility.PLAYER})
    cache = ParsedImmutableRevisionCache()
    first_sample, first = measure(fixture, cache)
    assert first.found
    artifact = fixture.sources.get_artifact("src:world-lore")
    with fixture.sources._lock:
        fixture.sources._artifacts[artifact.source_artifact_id] = artifact.model_copy(
            update={"visibility": Visibility.GM},
            deep=True,
        )
    second_sample, second = measure(fixture, cache)
    assert second_sample["cache_hit"] is True
    assert not second.found
    assert first_sample["semantic_sha256"] != second_sample["semantic_sha256"]
    assert first.found  # returned result remains independently owned


@pytest.mark.parametrize("sizes,repeats", [([4], 2), ([10], 1)])
def test_invalid_measurement_configuration_fails(sizes, repeats):
    with pytest.raises(ValueError):
        run_experiment(sizes, repeats)
