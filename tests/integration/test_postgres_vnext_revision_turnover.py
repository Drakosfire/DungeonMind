"""Core-only PostgreSQL timing witness for publication and parsed-cache turnover."""

import json
import os
from functools import wraps
from pathlib import Path
from time import perf_counter

import pytest

from dungeonmind.application.vnext import _read_artifact, native_source_access
from dungeonmind.application.vnext.admission import AlwaysAdmitPolicy
from dungeonmind.application.vnext.neighborhood import NeighborhoodReadService
from dungeonmind.application.vnext.read_context import KnowledgeReadContext
from dungeonmind.contracts.vnext import ProjectionRequest, ScopeSelector
from dungeonmind.infrastructure.postgres import vnext_knowledge
from dungeonmind.infrastructure.postgres.vnext_knowledge import VerifiedKnowledgeRevisionCache
from dungeonmind.infrastructure.postgres.vnext_sources import PostgresNativeSourceEvidenceRepository
from tests.integration.test_postgres_vnext_prospective_publication import _publish
from tests.unit.test_vnext_cas_publication import SPACE, genesis_command
from tests.unit.test_vnext_governed_materialization import _lab_descriptors
from tests.unit.test_vnext_prospective_publication import _contribution, _entity

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("entity_count", [1, 10_000])
@pytest.mark.parametrize("proof_entries", [1, 2])
def test_native_context_rebuild_on_child_and_parent_return(
    pg, monkeypatch, entity_count, proof_entries
):
    proofs = VerifiedKnowledgeRevisionCache(max_bytes=64_000_000, max_entries=proof_entries)
    repo = PostgresNativeSourceEvidenceRepository(pg.database, verification_cache=proofs)
    domain, profile = _lab_descriptors()
    use_artifact = os.environ.get("DUNGEONMIND_BENCH_ARTIFACT") == "1"
    payload = genesis_command().graph_payload
    exemplar = payload["assertions"][0]
    for index in range(1, entity_count):
        entity_id = f"ent:turnover-{index:05d}"
        payload["entities"].append(
            {"entity_id": entity_id, "schema_version": "dm_entity_v1"}
        )
        payload["assertions"].append(
            {
                **exemplar,
                "assertion_id": f"asrt:turnover-{index:05d}",
                "subject_entity_id": entity_id,
            }
        )
    service = NeighborhoodReadService()
    results = {}
    parent = repo.publish_revision(genesis_command(payload=payload)).revision.revision_id
    cache = native_source_access.NativeParsedRevisionCache()
    rebuilds = []
    measurements = {}
    parse = native_source_access.parse_verified_source_rows

    def measured_parse(stored, rows):
        counts = {key: len(table) for key, table in rows.items()}
        start = perf_counter()
        result = parse(stored, rows)
        rebuilds.append(
            {
                "revision": stored.revision.revision_id,
                "rows": counts,
                "parse_ms": (perf_counter() - start) * 1000,
            }
        )
        return result

    monkeypatch.setattr(native_source_access, "parse_verified_source_rows", measured_parse)

    stage_samples = {}
    stage_counts = {}
    stages = {}
    calls = {}

    def measure_stage(owner, attribute):
        original = getattr(owner, attribute)

        @wraps(original)
        def measured(*args, **kwargs):
            start = perf_counter()
            result = original(*args, **kwargs)
            calls[attribute] = calls.get(attribute, 0) + 1
            stages[attribute] = stages.get(attribute, 0.0) + (perf_counter() - start) * 1000
            return result

        monkeypatch.setattr(owner, attribute, measured)

    measure_stage(repo, "get_revision_for_native_read")
    measure_stage(repo, "get_native_read_artifact")
    measure_stage(native_source_access, "decode_read_artifact")
    measure_stage(vnext_knowledge, "_bounded_depth")
    measure_stage(vnext_knowledge, "_reconstruct")
    measure_stage(vnext_knowledge, "canonical_json")
    measure_stage(repo, "open_native_source_view")
    measure_stage(_read_artifact, "_build_parsed_knowledge_revision_from_records")

    def read(label, revision_id):
        stages.clear()
        calls.clear()
        start = perf_counter()
        context = native_source_access.open_native_text_source_access_context(
            repository=repo,
            space_id=SPACE,
            revision_id=revision_id,
            domain_contract=domain,
            parsed_cache=cache,
            prefer_verified_source_rows=not use_artifact,
        )
        prepared = KnowledgeReadContext(
            parsed=context.parsed,
            request=ProjectionRequest(
                space_id=SPACE,
                revision_id=revision_id,
                scope_selector=ScopeSelector(include_unscoped=True),
            ),
            domain_contract=domain,
            semantic_profile=profile,
            domain_policy=AlwaysAdmitPolicy(policy_id=domain.admission_policy_id),
            source_reader=context.source_view,
        )
        result = service.get_neighborhood(prepared, ["ent:alice"])
        assert result.found_seed_entity_ids == ("ent:alice",)
        results[label] = result.result_digest
        measurements[label] = (perf_counter() - start) * 1000
        stage_samples[label] = dict(stages)
        stage_counts[label] = dict(calls)
        return context.parsed

    first_parent = read("first_parent_neighborhood_ms", parent)
    assert read("warm_parent_neighborhood_ms", parent) is first_parent

    stages.clear()
    calls.clear()
    contribution = _contribution([_entity()])
    start = perf_counter()
    published = _publish(repo, first_parent, contribution, "prepared:turnover-child")
    child = published.publication_receipt.published_revision_id
    measurements["publication_ms"] = (perf_counter() - start) * 1000
    stage_samples["publication_ms"] = dict(stages)
    stage_counts["publication_ms"] = dict(calls)
    first_child = read("first_child_neighborhood_ms", child)
    assert first_child.identity.revision_id == child
    assert read("warm_child_neighborhood_ms", child) is first_child
    returned_parent = read("return_to_parent_neighborhood_ms", parent)
    assert first_child.semantic_digest != first_parent.semantic_digest
    assert results["first_parent_neighborhood_ms"] == results["return_to_parent_neighborhood_ms"]
    assert results["first_child_neighborhood_ms"] == results["warm_child_neighborhood_ms"]
    assert returned_parent == first_parent
    assert returned_parent is not first_parent
    assert stage_counts["publication_ms"].get("_reconstruct", 0) == 1
    assert stage_counts["first_child_neighborhood_ms"].get("_reconstruct", 0) == 0
    assert stage_counts["return_to_parent_neighborhood_ms"].get(
        "_reconstruct", 0
    ) == (0 if proof_entries == 2 else 1)
    if use_artifact:
        assert "decode_read_artifact" in stage_samples["first_child_neighborhood_ms"]
    else:
        assert [sample["revision"] for sample in rebuilds] == [parent, child, parent]
    status = Path("/proc/self/status")
    memory = {}
    if status.is_file():
        for line in status.read_text().splitlines():
            name, _, value = line.partition(":")
            if name in {"VmRSS", "VmHWM"}:
                memory[name] = int(value.split()[0])
    print(json.dumps({
        "entity_count": entity_count,
        "process_memory_kib": memory,
        "proof_entries": proof_entries,
        "proof_retained_bytes": proofs.retained_bytes,
        "measurements": measurements,
        "rebuilds": rebuilds,
        "read_stages_ms": stage_samples,
        "read_stage_calls": stage_counts,
    }, sort_keys=True))
