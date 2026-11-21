"""Fixed 10k neighborhood workload for the compact-index experiment."""
from dungeonmind.application.vnext._read_artifact import parse_verified_source_rows
from dungeonmind.application.vnext.admission import AlwaysAdmitPolicy
from dungeonmind.application.vnext.materialization import encode_native_graph_payload
from dungeonmind.application.vnext.neighborhood import NeighborhoodReadService
from dungeonmind.application.vnext.read_context import KnowledgeReadContext
from dungeonmind.application.vnext.records import StoredKnowledgeRevision
from dungeonmind.contracts.vnext.common import LabelsAllVisibility, ScopeSelector
from dungeonmind.domain.canonical import canonical_sha256
from benchmarks.vnext_neighborhood_10k import _build_space


def prepare():
    fixture = _build_space(decoy_count=10_000, raw_inputs=True)
    rows = encode_native_graph_payload(
        entities={x.entity_id: x for x in fixture["entities"]},
        assertions={x.assertion_id: x for x in fixture["assertions"]},
        aliases={},
        evidence={x.evidence_ref_id: x for x in fixture["evidence"]},
    )
    revision = fixture["revision"].model_copy(
        update={"graph_payload_sha256": canonical_sha256(rows)}
    )

    def open_revision(parser=parse_verified_source_rows):
        stored = StoredKnowledgeRevision.seal(revision, rows)
        return parser(stored, stored.graph_payload)

    def query(parsed, *, withdraw=False, out_of_scope=False, hide_source=False):
        reader = fixture["source_reader"]
        request = fixture["request"]
        if out_of_scope:
            request = request.model_copy(update={"scope_selector": ScopeSelector()})
        if hide_source:
            artifact = reader._artifacts["src:art-0000"]
            reader._artifacts["src:art-0000"] = artifact.model_copy(update={
                "visibility": LabelsAllVisibility(labels=["bench:audience"]),
            })
            request = request.model_copy(update={"audience_labels": []})
        if withdraw:
            artifact = reader._artifacts["src:art-0000"]
            reader._artifacts["src:art-0000"] = artifact.model_copy(update={"status": "retracted"})
        domain = fixture["domain_contract"]
        context = KnowledgeReadContext(
            parsed=parsed, request=request, domain_contract=domain,
            semantic_profile=fixture["semantic_profile"],
            domain_policy=AlwaysAdmitPolicy(policy_id=domain.admission_policy_id),
            source_reader=reader,
        )
        return NeighborhoodReadService().get_neighborhood(context, ["ent:branch"], depth=2)

    return open_revision, query
