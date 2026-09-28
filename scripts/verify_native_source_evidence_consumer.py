#!/usr/bin/env python3
"""Exercise native source admission through the exact accepted WorldKeeper runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

EXPECTED_KEEPER = "49a8620f066ce7ef8972a699020c012f50af9158"
BODY = "Authored acceptance fixture: the silver bell is kept beneath the north arch.\n"


def _load_keeper(checkout: Path) -> str:
    source = checkout / "src"
    revision = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if revision != EXPECTED_KEEPER:
        raise SystemExit(f"Keeper pin mismatch: expected {EXPECTED_KEEPER}, got {revision}")
    sys.path.insert(0, str(source))
    import worldkeeper

    module_path = Path(worldkeeper.__file__).resolve()
    if source.resolve() not in module_path.parents:
        raise SystemExit(f"Keeper imported from unexpected path: {module_path}")
    return str(module_path)


def run(database_url: str, keeper_checkout: Path) -> dict[str, object]:
    keeper_module_path = _load_keeper(keeper_checkout)

    import worldkeeper.application.commit as keeper_commit
    import worldkeeper.integrations.dungeonmind.runtime as keeper_runtime
    from worldkeeper.application.commit import PreparedChangeStale
    from worldkeeper.application.contracts import (
        AssertionMetadata,
        CreateFact,
        CreateObject,
        LiteralFactValue,
        TemporalScope,
        Visibility,
        WorldChangeIntent,
    )
    from worldkeeper.integrations.dungeonmind import DungeonMindWorldKeeperRuntime

    import dungeonmind
    from dungeonmind.application.vnext.admission import (
        AlwaysAdmitPolicy,
        DomainAdmissionPolicyRegistry,
    )
    from dungeonmind.application.vnext.builder import build_parsed_knowledge_revision
    from dungeonmind.application.vnext.evidence_reads import EvidenceReadService
    from dungeonmind.application.vnext.initialization import initialize_empty_knowledge_space
    from dungeonmind.application.vnext.materialization import decode_native_graph_payload
    from dungeonmind.application.vnext.native_source_access import (
        open_admitted_native_text,
        open_native_text_source_access_context,
    )
    from dungeonmind.application.vnext.native_source_admission import (
        publish_native_text_source_evidence,
    )
    from dungeonmind.application.vnext.read_context import KnowledgeReadContext
    from dungeonmind.application.vnext.records import StoredKnowledgeRevision
    from dungeonmind.contracts.vnext.common import (
        EpistemicBasis,
        KnowledgeStanding,
        ScopeSelector,
    )
    from dungeonmind.contracts.vnext.domain import (
        DomainContractDescriptor,
        SemanticProfileDescriptorV2,
        SemanticProfilePredicate,
    )
    from dungeonmind.contracts.vnext.native_source import (
        NativeTextEvidenceSpanRequestV1,
        NativeTextSourceAdmissionV1,
    )
    from dungeonmind.contracts.vnext.projection import ProjectionRequest
    from dungeonmind.domain.canonical import canonical_sha256
    from dungeonmind.infrastructure.postgres import (
        PostgresDatabase,
        PostgresNativeSourceEvidenceRepository,
    )

    candidate_source = Path(__file__).resolve().parents[1] / "src"
    candidate_module_path = Path(dungeonmind.__file__).resolve()
    if candidate_source.resolve() not in candidate_module_path.parents:
        raise AssertionError(
            f"candidate DungeonMind imported from unexpected path: {candidate_module_path}"
        )

    space_id = f"space:native-source-witness:{uuid.uuid4().hex}"
    now = datetime.now(tz=UTC).replace(microsecond=0)
    body_bytes = BODY.encode("utf-8")
    domain = DomainContractDescriptor(
        domain_id="test.native-source-witness",
        domain_revision="1",
        scope_axes=[],
        visibility_labels=[],
        claim_modes=["test:fact"],
        source_annotation_schemas=[],
        admission_policy_id="test.native-source-witness.allow",
    )
    profile = SemanticProfileDescriptorV2(
        profile_id="test.native-source-witness.profile",
        profile_revision="1",
        term_namespaces=["test"],
        predicates=[
            SemanticProfilePredicate(
                term="test:claim",
                allowed_value_kinds=["literal"],
            )
        ],
    )
    database = PostgresDatabase(database_url)
    repository = PostgresNativeSourceEvidenceRepository(database)
    genesis = initialize_empty_knowledge_space(
        repository=repository,
        space_id=space_id,
        initialization_id=f"init:{uuid.uuid4().hex}",
        created_at=now,
        domain_contract=domain,
        semantic_profile=profile,
    )
    admission_id = f"admit:{uuid.uuid4().hex}"
    request = NativeTextSourceAdmissionV1(
        space_id=space_id,
        admission_id=admission_id,
        expected_parent_revision_id=genesis.published_revision_id,
        created_at=now,
        body_text=BODY,
        expected_body_sha256=hashlib.sha256(body_bytes).hexdigest(),
        source_classification="test:authored_text",
        authority="primary",
        visibility={"kind": "public"},
        spans=[
            NativeTextEvidenceSpanRequestV1(
                client_ref="whole-authored-source",
                evidence_role="support",
                start_byte=0,
                end_byte=len(body_bytes),
                expected_slice_sha256=hashlib.sha256(body_bytes).hexdigest(),
            )
        ],
    )
    admission = publish_native_text_source_evidence(
        repository=repository,
        request=request,
        domain_contract=domain,
        semantic_profile=profile,
    )
    evidence_id = admission.bindings[0].evidence_ref_id

    def intent() -> WorldChangeIntent:
        metadata = AssertionMetadata(
            scope=(),
            visibility=Visibility(),
            epistemic_basis=EpistemicBasis.ASSERTED.value,
            claim_mode="test:fact",
            standing=KnowledgeStanding.ESTABLISHED.value,
            evidence_ref_ids=(evidence_id,),
            temporal_scope=TemporalScope(),
        )
        return WorldChangeIntent(
            space_id=space_id,
            producer="producer:native-source-witness",
            operations=(
                CreateObject(
                    client_op_id="object:authored-fact",
                    facts=(
                        CreateFact(
                            client_op_id="fact:arch-bell",
                            predicate="test:claim",
                            value=LiteralFactValue.from_json(
                                "The silver bell is kept beneath the north arch."
                            ),
                            metadata=metadata,
                        ),
                    ),
                ),
            ),
        )

    def runtime(prepared_id: str) -> DungeonMindWorldKeeperRuntime:
        return DungeonMindWorldKeeperRuntime(
            repository=repository,
            domain_contract=domain,
            semantic_profile=profile,
            clock=lambda: now,
            prepared_id_factory=lambda: prepared_id,
        )

    service = runtime("prepared:native-source-witness")
    if not callable(service.prepare_change) or not callable(service.commit_prepared_change):
        raise AssertionError("actual Keeper runtime lacks its accepted prepare/commit surface")
    stale_service = runtime("prepared:native-source-stale-witness")
    stale_prepared = stale_service.prepare_change(intent())
    prepared = service.prepare_change(intent())
    committed = service.commit_prepared_change(prepared, confirmed_by="actor:witness")
    event_count_after_commit = len(repository.head_events(space_id))
    replayed = service.commit_prepared_change(prepared, confirmed_by="actor:witness")
    if replayed != committed or len(repository.head_events(space_id)) != event_count_after_commit:
        raise AssertionError("Keeper replay changed the committed publication")
    try:
        stale_service.commit_prepared_change(stale_prepared, confirmed_by="actor:witness")
    except PreparedChangeStale:
        pass
    else:
        raise AssertionError("stale prepared Keeper change unexpectedly committed")

    object_results = {
        item.client_op_id: item.durable_object_id for item in committed.object_results
    }
    assertion_results = {
        item.client_op_id: item.durable_assertion_id for item in committed.assertion_results
    }
    if set(object_results) != {"object:authored-fact"}:
        raise AssertionError(f"unexpected object bindings: {object_results}")
    if set(assertion_results) != {"fact:arch-bell"}:
        raise AssertionError(f"unexpected assertion bindings: {assertion_results}")

    # A fresh repository/connection verifies restart read-back, evidence admission and bytes.
    reopened = PostgresNativeSourceEvidenceRepository(PostgresDatabase(database_url))
    child = reopened.get_revision(space_id, committed.child_revision_id)
    if child is None or child.revision.parent_revision_id != admission.published_revision_id:
        raise AssertionError("Keeper child does not descend from the exact admitted evidence child")
    parsed = build_parsed_knowledge_revision(
        revision=child.revision,
        decoded_content=decode_native_graph_payload(child.graph_payload),
    )
    assertion_id = assertion_results["fact:arch-bell"]
    assertion = parsed.get_assertion(assertion_id)
    if assertion is None or assertion.metadata.evidence_ref_ids != (evidence_id,):
        raise AssertionError("exact native child does not retain the admitted evidence binding")
    context = open_native_text_source_access_context(
        repository=reopened,
        space_id=space_id,
        revision_id=committed.child_revision_id,
        domain_contract=domain,
    )
    access = open_admitted_native_text(context, evidence_id)
    if access.status != "available" or access.body_text != BODY:
        raise AssertionError("reopened native source preview did not verify exact authored bytes")

    policy = AlwaysAdmitPolicy(domain.admission_policy_id)
    request_projection = ProjectionRequest(
        space_id=space_id,
        revision_id=committed.child_revision_id,
        scope_selector=ScopeSelector(include_unscoped=True),
        standing_selector=[KnowledgeStanding.ESTABLISHED],
    )
    read_context = KnowledgeReadContext(
        parsed=parsed,
        request=request_projection,
        domain_contract=domain,
        semantic_profile=profile,
        domain_policy=DomainAdmissionPolicyRegistry({policy.policy_id: policy}).resolve(
            policy.policy_id
        ),
        source_reader=reopened.open_native_source_view(space_id),
    )
    evidence_result = EvidenceReadService().get_assertion_evidence(read_context, assertion_id)
    if not evidence_result.available or tuple(
        item.evidence_ref_id for item in evidence_result.evidence
    ) != (evidence_id,):
        raise AssertionError(
            "ordinary native assertion/evidence read did not admit the exact source"
        )

    # Type-only imports are resolved above too: these names guard accidental API drift.
    source_view = reopened.open_native_source_view(space_id)
    if not isinstance(child, StoredKnowledgeRevision) or not all(
        callable(getattr(source_view, member, None))
        for member in ("open_coherent_view", "get_provenance_snapshot", "get_native_text_source")
    ):
        raise AssertionError("candidate repository does not satisfy the native read ports")
    expected_domain_digest = canonical_sha256(domain.model_dump(mode="json"))
    if child.revision.domain_contract_ref.descriptor_sha256 != expected_domain_digest:
        raise AssertionError("child descriptor differs from the initialized authority")

    return {
        "status": "NATIVE_SOURCE_KEEPER_CONSUMER_WITNESS_PASS",
        "keeper_commit": EXPECTED_KEEPER,
        "keeper_module": keeper_module_path,
        "candidate_dungeonmind_module": str(candidate_module_path),
        "keeper_runtime_module": str(Path(keeper_runtime.__file__).resolve()),
        "keeper_commit_module": str(Path(keeper_commit.__file__).resolve()),
        "space_id": space_id,
        "genesis_revision_id": genesis.published_revision_id,
        "admission_id": admission_id,
        "source_artifact_id": admission.source_artifact_id,
        "source_revision_id": admission.source_revision_id,
        "evidence_ref_id": evidence_id,
        "source_body_sha256": access.body_sha256,
        "admitted_child_revision_id": admission.published_revision_id,
        "keeper_child_revision_id": committed.child_revision_id,
        "object_bindings": object_results,
        "assertion_bindings": assertion_results,
        "ordinary_evidence_read": evidence_result.available,
        "source_preview_after_reopen": access.status,
        "replay_exact": replayed == committed,
        "stale_parent_rejected": True,
        "seeded_evidence": False,
        "provider_called": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keeper-source", type=Path, required=True)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DUNGEONMIND_DATABASE_URL"),
    )
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DUNGEONMIND_DATABASE_URL is required")
    print(
        json.dumps(run(args.database_url, args.keeper_source.resolve()), sort_keys=True, indent=2)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
