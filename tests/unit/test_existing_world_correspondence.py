"""Unit proofs for the existing-world correspondence contract and evaluator.

The checker is read-only: classifications are returned, integrity and
availability failures are raised as typed errors, and no classification is
ever inferred from the current head, a world label, or latest state.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dungeonmind.application.existing_world_adoption import (
    adopt_existing_world,
    parse_existing_world_adoption_bundle,
)
from dungeonmind.application.existing_world_correspondence import (
    ExistingWorldCorrespondenceService,
)
from dungeonmind.contracts.contribution import (
    ContributionSourceKind,
    GraphContributionV2,
)
from dungeonmind.contracts.existing_world_adoption import (
    existing_world_adoption_bundle_v2_canonical_bytes,
)
from dungeonmind.contracts.existing_world_correspondence import (
    CORRESPONDENCE_CHECK_ORDER,
    EXISTING_WORLD_CORRESPONDENCE_CHECK_SCHEMA,
    EXISTING_WORLD_CORRESPONDENCE_RESULT_SCHEMA,
    ExistingWorldCorrespondenceCheckV1,
    ExistingWorldCorrespondenceResultV1,
)
from dungeonmind.domain.errors import (
    PersistenceIntegrityError,
    PersistenceUnavailableError,
)
from dungeonmind.infrastructure.memory import (
    InMemoryContributionRepository,
    InMemoryExistingWorldAdoptionRepository,
    InMemoryIdentityDecisionRepository,
    InMemorySourceRepository,
    InMemoryWorldGraphRepository,
)
from tests.unit.test_eldyrwild_existing_world_adoption_bundle_v2 import (
    ADOPTION_ID,
    NOW,
    PUBLISHED_REVISION_ID,
    SOURCE_WORLD_REVISION_ID,
    WORLD_ID,
    eldyrwild_graph_reader,
    parse_sealed_bundle,
    raw_bundle,
)

CHANGED_SOURCE_REVISION_ID = "rev:" + "f0" * 16
NOT_EVALUATED_DETAIL = "not evaluated: source_identity diverged"


class _WorldHarness:
    def __init__(self) -> None:
        self.world_graph = InMemoryWorldGraphRepository()
        self.sources = InMemorySourceRepository()
        self.contributions = InMemoryContributionRepository()
        self.identity = InMemoryIdentityDecisionRepository()
        self.adoptions = InMemoryExistingWorldAdoptionRepository(
            self.world_graph,
            self.sources,
            self.contributions,
            self.identity,
        )
        self.service = ExistingWorldCorrespondenceService(
            adoption_repository=self.adoptions,
            world_graph_repository=self.world_graph,
            contribution_repository=self.contributions,
            identity_repository=self.identity,
            source_repository=self.sources,
            graph_reader=eldyrwild_graph_reader(),
        )

    def check(
        self,
        raw: bytes | None = None,
        *,
        world_id: str = WORLD_ID,
    ) -> ExistingWorldCorrespondenceResultV1:
        return self.service.check(
            raw if raw is not None else raw_bundle(),
            world_id=world_id,
        )


def _adopted_harness() -> _WorldHarness:
    harness = _WorldHarness()
    adopt_existing_world(
        raw_bundle(),
        adopted_at=NOW,
        adoption_repository=harness.adoptions,
        graph_reader=eldyrwild_graph_reader(),
    )
    return harness


def _checks_by_name(
    result: ExistingWorldCorrespondenceResultV1,
) -> dict[str, ExistingWorldCorrespondenceCheckV1]:
    return {check.check: check for check in result.checks}


def _changed_source_snapshot_bytes() -> bytes:
    bundle = parse_sealed_bundle()
    changed = bundle.model_copy(
        update={
            "source_provenance": bundle.source_provenance.model_copy(
                update={"source_world_revision_id": CHANGED_SOURCE_REVISION_ID}
            )
        }
    )
    raw = existing_world_adoption_bundle_v2_canonical_bytes(changed)
    reparsed = parse_existing_world_adoption_bundle(
        raw,
        graph_reader=eldyrwild_graph_reader(),
    )
    assert reparsed.world_id == WORLD_ID
    assert reparsed.source_provenance.source_world_revision_id == CHANGED_SOURCE_REVISION_ID
    return raw


def _changed_adoption_id_snapshot_bytes() -> bytes:
    """Canonical bundle identical to the adopted one except ``adoption_id``."""
    bundle = parse_sealed_bundle()
    changed = bundle.model_copy(update={"adoption_id": ADOPTION_ID + "-tampered"})
    raw = existing_world_adoption_bundle_v2_canonical_bytes(changed)
    reparsed = parse_existing_world_adoption_bundle(
        raw,
        graph_reader=eldyrwild_graph_reader(),
    )
    assert reparsed.adoption_id == ADOPTION_ID + "-tampered"
    assert (
        reparsed.source_provenance.source_world_revision_id == SOURCE_WORLD_REVISION_ID
    )
    return raw


def _changed_producer_snapshot_bytes() -> bytes:
    """Canonical bundle identical to the adopted one except producer provenance."""
    bundle = parse_sealed_bundle()
    changed = bundle.model_copy(
        update={
            "source_provenance": bundle.source_provenance.model_copy(
                update={"producer_revision": "producer-revision-tampered"}
            )
        }
    )
    raw = existing_world_adoption_bundle_v2_canonical_bytes(changed)
    reparsed = parse_existing_world_adoption_bundle(
        raw,
        graph_reader=eldyrwild_graph_reader(),
    )
    assert reparsed.source_provenance.producer_revision == "producer-revision-tampered"
    assert (
        reparsed.source_provenance.source_world_revision_id == SOURCE_WORLD_REVISION_ID
    )
    return raw


def _evidence_referenced_source_revision_id() -> str:
    bundle = parse_sealed_bundle()
    snapshot = eldyrwild_graph_reader().parse(
        graph_schema=bundle.graph_schema,
        graph_payload=bundle.graph_payload,
    )
    for record in snapshot.evidence.values():
        if record.source_revision_id is not None:
            return record.source_revision_id
    raise AssertionError("fixture evidence must reference at least one source revision")


def _tamper_contribution(harness: _WorldHarness) -> str:
    """Simulate a coherent-but-different durable write: same identity, new content."""
    target = parse_sealed_bundle().contributions[0]
    stored = harness.contributions.get(WORLD_ID, target.contribution_id)
    assert stored is not None
    mutated = stored.model_copy(update={"extraction_profile": "tampered-profile"})
    harness.contributions._items[(WORLD_ID, target.contribution_id)] = mutated
    return target.contribution_id


def _tamper_source_revision(harness: _WorldHarness) -> str:
    target = parse_sealed_bundle().source_revisions[0]
    stored = harness.sources.get_revision(target.source_revision_id)
    assert stored is not None
    mutated = stored.model_copy(update={"content_sha256": "0" * 64})
    harness.sources._revisions[target.source_revision_id] = mutated
    return target.source_revision_id


def _check(
    name: str,
    outcome: str,
    detail: str = "",
) -> ExistingWorldCorrespondenceCheckV1:
    return ExistingWorldCorrespondenceCheckV1(check=name, outcome=outcome, detail=detail)  # type: ignore[arg-type]


def _all_match_checks() -> list[ExistingWorldCorrespondenceCheckV1]:
    return [_check(name, "match") for name in CORRESPONDENCE_CHECK_ORDER]


def _stale_checks() -> list[ExistingWorldCorrespondenceCheckV1]:
    return [
        _check("source_identity", "diverged", "observed differs from adopted"),
        *[
            _check(name, "not_evaluated", NOT_EVALUATED_DETAIL)
            for name in CORRESPONDENCE_CHECK_ORDER[1:]
        ],
    ]


def _result_kwargs(checks: list[ExistingWorldCorrespondenceCheckV1]) -> dict[str, object]:
    return {
        "world_id": WORLD_ID,
        "observed_source_revision": SOURCE_WORLD_REVISION_ID,
        "adopted_source_revision": SOURCE_WORLD_REVISION_ID,
        "adoption_id": ADOPTION_ID,
        "adopted_revision": PUBLISHED_REVISION_ID,
        "checks": checks,
    }


def test_result_contract_pins_schema_and_roundtrips() -> None:
    result = ExistingWorldCorrespondenceResultV1(
        classification="CORRESPONDING",
        **_result_kwargs(_all_match_checks()),  # type: ignore[arg-type]
    )
    assert result.schema_version == EXISTING_WORLD_CORRESPONDENCE_RESULT_SCHEMA
    assert all(
        check.schema_version == EXISTING_WORLD_CORRESPONDENCE_CHECK_SCHEMA
        for check in result.checks
    )
    reloaded = ExistingWorldCorrespondenceResultV1.model_validate(
        result.model_dump(mode="json")
    )
    assert reloaded == result


def test_check_contract_enforces_detail_hygiene() -> None:
    with pytest.raises(ValidationError):
        _check("source_identity", "match", "match carries no diagnostic")
    with pytest.raises(ValidationError):
        _check("source_identity", "diverged", "")
    with pytest.raises(ValidationError):
        _check("source_identity", "not_evaluated", " ")


def test_result_contract_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ExistingWorldCorrespondenceResultV1.model_validate(
            {
                "schema_version": EXISTING_WORLD_CORRESPONDENCE_RESULT_SCHEMA,
                "classification": "NOT_ADOPTED",
                "world_id": WORLD_ID,
                "observed_source_revision": SOURCE_WORLD_REVISION_ID,
                "surprise": "field",
            }
        )


def test_not_adopted_contract_requires_null_adopted_fields_and_no_checks() -> None:
    result = ExistingWorldCorrespondenceResultV1(
        classification="NOT_ADOPTED",
        world_id=WORLD_ID,
        observed_source_revision=SOURCE_WORLD_REVISION_ID,
    )
    assert result.adopted_source_revision is None
    assert result.adoption_id is None
    assert result.adopted_revision is None
    assert result.checks == []
    with pytest.raises(ValidationError):
        ExistingWorldCorrespondenceResultV1(
            classification="NOT_ADOPTED",
            world_id=WORLD_ID,
            observed_source_revision=SOURCE_WORLD_REVISION_ID,
            adopted_revision=PUBLISHED_REVISION_ID,
        )
    with pytest.raises(ValidationError):
        ExistingWorldCorrespondenceResultV1(
            classification="NOT_ADOPTED",
            world_id=WORLD_ID,
            observed_source_revision=SOURCE_WORLD_REVISION_ID,
            checks=_all_match_checks(),
        )


def test_corresponding_contract_requires_populated_adopted_fields_and_all_match() -> None:
    kwargs = _result_kwargs(_all_match_checks())
    del kwargs["adopted_revision"]
    with pytest.raises(ValidationError):
        ExistingWorldCorrespondenceResultV1(classification="CORRESPONDING", **kwargs)  # type: ignore[arg-type]
    diverged = _all_match_checks()
    diverged[3] = _check("contribution_history", "diverged", "contribution drift")
    with pytest.raises(ValidationError):
        ExistingWorldCorrespondenceResultV1(
            classification="CORRESPONDING",
            **_result_kwargs(diverged),  # type: ignore[arg-type]
        )


def test_stale_contract_requires_source_divergence_and_unevaluated_rest() -> None:
    result = ExistingWorldCorrespondenceResultV1(
        classification="STALE",
        **_result_kwargs(_stale_checks()),  # type: ignore[arg-type]
    )
    assert result.checks[0].outcome == "diverged"
    with pytest.raises(ValidationError):
        ExistingWorldCorrespondenceResultV1(
            classification="STALE",
            **_result_kwargs(_all_match_checks()),  # type: ignore[arg-type]
        )
    evaluated = _stale_checks()
    evaluated[1] = _check("graph_payload", "match")
    with pytest.raises(ValidationError):
        ExistingWorldCorrespondenceResultV1(
            classification="STALE",
            **_result_kwargs(evaluated),  # type: ignore[arg-type]
        )


def test_mismatch_contract_requires_matched_source_and_one_divergence() -> None:
    diverged = _all_match_checks()
    diverged[2] = _check("source_history", "diverged", "source drift")
    result = ExistingWorldCorrespondenceResultV1(
        classification="MISMATCH",
        **_result_kwargs(diverged),  # type: ignore[arg-type]
    )
    assert result.classification == "MISMATCH"
    with pytest.raises(ValidationError):
        ExistingWorldCorrespondenceResultV1(
            classification="MISMATCH",
            **_result_kwargs(_all_match_checks()),  # type: ignore[arg-type]
        )
    with pytest.raises(ValidationError):
        ExistingWorldCorrespondenceResultV1(
            classification="MISMATCH",
            **_result_kwargs(_stale_checks()),  # type: ignore[arg-type]
        )


def test_mismatch_contract_allows_not_evaluated_only_after_first_divergence() -> None:
    checks = _all_match_checks()
    checks[2] = _check("source_history", "diverged", "source drift")
    checks[3] = _check("contribution_history", "not_evaluated", "short-circuited")
    checks[4] = _check("identity_history", "not_evaluated", "short-circuited")
    result = ExistingWorldCorrespondenceResultV1(
        classification="MISMATCH",
        **_result_kwargs(checks),  # type: ignore[arg-type]
    )
    assert result.classification == "MISMATCH"


def test_mismatch_contract_rejects_not_evaluated_before_first_divergence() -> None:
    checks = _all_match_checks()
    checks[1] = _check("graph_payload", "not_evaluated", "skipped early")
    checks[3] = _check("contribution_history", "diverged", "contribution drift")
    with pytest.raises(ValidationError):
        ExistingWorldCorrespondenceResultV1(
            classification="MISMATCH",
            **_result_kwargs(checks),  # type: ignore[arg-type]
        )


def test_result_contract_requires_canonical_check_order() -> None:
    reordered = _all_match_checks()
    reordered[1], reordered[2] = reordered[2], reordered[1]
    with pytest.raises(ValidationError):
        ExistingWorldCorrespondenceResultV1(
            classification="CORRESPONDING",
            **_result_kwargs(reordered),  # type: ignore[arg-type]
        )


def test_exact_snapshot_corresponds_with_exact_identities() -> None:
    harness = _adopted_harness()
    result = harness.check()
    assert result.classification == "CORRESPONDING"
    assert result.world_id == WORLD_ID
    assert result.observed_source_revision == SOURCE_WORLD_REVISION_ID
    assert result.adopted_source_revision == SOURCE_WORLD_REVISION_ID
    assert result.adoption_id == ADOPTION_ID
    assert result.adopted_revision == PUBLISHED_REVISION_ID
    assert [check.check for check in result.checks] == list(CORRESPONDENCE_CHECK_ORDER)
    assert all(check.outcome == "match" for check in result.checks)
    assert all(check.detail == "" for check in result.checks)


def test_repeated_check_is_canonically_equal() -> None:
    harness = _adopted_harness()
    first = harness.check()
    second = harness.check()
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_changed_valid_source_snapshot_is_stale() -> None:
    harness = _adopted_harness()
    result = harness.check(_changed_source_snapshot_bytes())
    assert result.classification == "STALE"
    assert result.observed_source_revision == CHANGED_SOURCE_REVISION_ID
    assert result.adopted_source_revision == SOURCE_WORLD_REVISION_ID
    assert result.adoption_id == ADOPTION_ID
    assert result.adopted_revision == PUBLISHED_REVISION_ID
    checks = _checks_by_name(result)
    assert checks["source_identity"].outcome == "diverged"
    assert CHANGED_SOURCE_REVISION_ID in checks["source_identity"].detail
    assert SOURCE_WORLD_REVISION_ID in checks["source_identity"].detail
    for name in CORRESPONDENCE_CHECK_ORDER[1:]:
        assert checks[name].outcome == "not_evaluated"
        assert checks[name].detail == NOT_EVALUATED_DETAIL


def test_same_revision_but_changed_adoption_id_is_stale_never_corresponding() -> None:
    harness = _adopted_harness()
    result = harness.check(_changed_adoption_id_snapshot_bytes())
    assert result.classification == "STALE"
    assert result.observed_source_revision == SOURCE_WORLD_REVISION_ID
    assert result.adopted_source_revision == SOURCE_WORLD_REVISION_ID
    checks = _checks_by_name(result)
    assert checks["source_identity"].outcome == "diverged"
    assert ADOPTION_ID in checks["source_identity"].detail
    assert f"{ADOPTION_ID}-tampered" in checks["source_identity"].detail
    for name in CORRESPONDENCE_CHECK_ORDER[1:]:
        assert checks[name].outcome == "not_evaluated"


def test_same_revision_but_changed_producer_provenance_is_stale() -> None:
    harness = _adopted_harness()
    result = harness.check(_changed_producer_snapshot_bytes())
    assert result.classification == "STALE"
    assert result.observed_source_revision == SOURCE_WORLD_REVISION_ID
    assert result.adopted_source_revision == SOURCE_WORLD_REVISION_ID
    checks = _checks_by_name(result)
    assert checks["source_identity"].outcome == "diverged"
    assert "producer_revision" in checks["source_identity"].detail
    for name in CORRESPONDENCE_CHECK_ORDER[1:]:
        assert checks[name].outcome == "not_evaluated"


def test_coherent_contribution_drift_is_mismatch_even_with_matching_graph() -> None:
    harness = _adopted_harness()
    tampered_id = _tamper_contribution(harness)
    result = harness.check()
    assert result.classification == "MISMATCH"
    checks = _checks_by_name(result)
    assert checks["source_identity"].outcome == "match"
    assert checks["graph_payload"].outcome == "match"
    assert checks["contribution_history"].outcome == "diverged"
    assert tampered_id in checks["contribution_history"].detail
    assert checks["source_history"].outcome == "match"
    assert checks["identity_history"].outcome == "match"
    assert checks["evidence_identity"].outcome == "match"


def test_coherent_source_revision_drift_is_mismatch() -> None:
    harness = _adopted_harness()
    tampered_id = _tamper_source_revision(harness)
    result = harness.check()
    assert result.classification == "MISMATCH"
    checks = _checks_by_name(result)
    assert checks["source_history"].outcome == "diverged"
    assert tampered_id in checks["source_history"].detail
    assert checks["graph_payload"].outcome == "match"


def test_extra_durable_contribution_is_mismatch() -> None:
    harness = _adopted_harness()
    extra = GraphContributionV2(
        contribution_id="contribution:extraneous-durable-write",
        world_id=WORLD_ID,
        source_kind=ContributionSourceKind.MANUAL_IMPORT,
        produced_at=NOW,
    )
    harness.contributions.append(extra)
    result = harness.check()
    assert result.classification == "MISMATCH"
    checks = _checks_by_name(result)
    assert checks["contribution_history"].outcome == "diverged"
    assert "contribution:extraneous-durable-write" in checks["contribution_history"].detail


def test_missing_receipt_is_not_adopted() -> None:
    harness = _WorldHarness()
    result = harness.check()
    assert result.classification == "NOT_ADOPTED"
    assert result.world_id == WORLD_ID
    assert result.observed_source_revision == SOURCE_WORLD_REVISION_ID
    assert result.adopted_source_revision is None
    assert result.adoption_id is None
    assert result.adopted_revision is None
    assert result.checks == []


def test_world_id_drift_between_input_and_bundle_fails_closed() -> None:
    harness = _adopted_harness()
    with pytest.raises(PersistenceIntegrityError) as exc:
        harness.check(world_id="other-world")
    assert exc.value.details["reason"] == "world_id_drift"


@pytest.mark.parametrize(
    ("raw", "reason"),
    (
        (b"not json at all", "raw_bundle_not_json"),
        (b'["not", "an", "object"]', "bundle_shape_invalid"),
        (b'{"schema_version": "dm_surprise_v9"}', "unsupported_adoption_bundle_schema"),
    ),
)
def test_malformed_inputs_raise_integrity_error(raw: bytes, reason: str) -> None:
    harness = _adopted_harness()
    with pytest.raises(PersistenceIntegrityError) as exc:
        harness.check(raw)
    assert exc.value.details["reason"] == reason


def test_non_canonical_input_raises_integrity_error() -> None:
    raw = raw_bundle()
    assert raw.endswith(b"\n")
    harness = _adopted_harness()
    with pytest.raises(PersistenceIntegrityError) as exc:
        harness.check(raw[:-1] + b" \n")
    assert exc.value.details["reason"] == "non_canonical_bundle_bytes"


def test_non_bytes_input_raises_integrity_error() -> None:
    harness = _adopted_harness()
    with pytest.raises(PersistenceIntegrityError) as exc:
        harness.check("not-bytes")  # type: ignore[arg-type]
    assert exc.value.details["reason"] == "raw_bundle_not_bytes"


def test_dangling_receipt_revision_raises_integrity_error() -> None:
    harness = _adopted_harness()
    harness.world_graph._revisions.pop((WORLD_ID, PUBLISHED_REVISION_ID))
    with pytest.raises(PersistenceIntegrityError):
        harness.check()


def test_service_resolution_names_the_missing_revision() -> None:
    harness = _adopted_harness()
    receipt = harness.adoptions.get_for_world(WORLD_ID)
    assert receipt is not None
    harness.world_graph._revisions.pop((WORLD_ID, PUBLISHED_REVISION_ID))

    class _UncheckingAdoptions:
        """Port shape without the adapters' receipt↔revision cross-verification."""

        def adopt(self, command):
            raise NotImplementedError

        def get(self, world_id: str, adoption_id: str):
            return receipt if adoption_id == receipt.adoption_id else None

        def get_for_world(self, world_id: str):
            return receipt

    service = ExistingWorldCorrespondenceService(
        adoption_repository=_UncheckingAdoptions(),
        world_graph_repository=harness.world_graph,
        contribution_repository=harness.contributions,
        identity_repository=harness.identity,
        source_repository=harness.sources,
        graph_reader=eldyrwild_graph_reader(),
    )
    with pytest.raises(PersistenceIntegrityError) as exc:
        service.check(raw_bundle(), world_id=WORLD_ID)
    assert exc.value.details["reason"] == "adopted_revision_missing"
    assert exc.value.details["published_revision_id"] == PUBLISHED_REVISION_ID


def test_dangling_contribution_raises_integrity_error() -> None:
    harness = _adopted_harness()
    target = parse_sealed_bundle().contributions[0]
    expected = len(parse_sealed_bundle().contributions)
    harness.contributions._items.pop((WORLD_ID, target.contribution_id))
    with pytest.raises(PersistenceIntegrityError) as exc:
        harness.check()
    assert exc.value.details["reason"] == "adopted_contribution_missing"
    assert exc.value.details["adopted_contribution_count"] == expected
    assert exc.value.details["durable_contribution_count"] == expected - 1


def test_same_cardinality_contribution_swap_fails_closed_on_identity() -> None:
    """A delete-plus-insert swap keeps the count pin intact; the matched
    snapshot's receipt-committed identities still name the missing row."""
    harness = _adopted_harness()
    target = parse_sealed_bundle().contributions[0]
    harness.contributions._items.pop((WORLD_ID, target.contribution_id))
    harness.contributions.append(
        GraphContributionV2(
            contribution_id="contribution:extraneous-durable-write",
            world_id=WORLD_ID,
            source_kind=ContributionSourceKind.MANUAL_IMPORT,
            produced_at=NOW,
        )
    )
    with pytest.raises(PersistenceIntegrityError) as exc:
        harness.check()
    assert exc.value.details["reason"] == "adopted_contribution_missing"
    assert exc.value.details["contribution_id"] == target.contribution_id


def test_dangling_source_revision_raises_integrity_error() -> None:
    harness = _adopted_harness()
    target = parse_sealed_bundle().source_revisions[0]
    harness.sources._revisions.pop(target.source_revision_id)
    with pytest.raises(PersistenceIntegrityError) as exc:
        harness.check()
    assert exc.value.details["reason"] == "adopted_source_revision_missing"


def test_dangling_source_artifact_raises_integrity_error() -> None:
    harness = _adopted_harness()
    target = parse_sealed_bundle().source_artifacts[0]
    harness.sources._artifacts.pop(target.source_artifact_id)
    with pytest.raises(PersistenceIntegrityError) as exc:
        harness.check()
    assert exc.value.details["reason"] == "adopted_source_artifact_missing"


def test_dangling_identity_decision_raises_integrity_error() -> None:
    harness = _adopted_harness()
    target = parse_sealed_bundle().identity_decisions[0]
    harness.identity._items.pop((WORLD_ID, target.decision_id))
    with pytest.raises(PersistenceIntegrityError) as exc:
        harness.check()
    assert exc.value.details["reason"] == "adopted_identity_decision_missing"


def test_deleted_adopted_contribution_fails_closed_before_stale_classification() -> None:
    """adopt A → delete adopted history → present valid B must raise, never STALE."""
    harness = _adopted_harness()
    target = parse_sealed_bundle().contributions[0]
    harness.contributions._items.pop((WORLD_ID, target.contribution_id))
    with pytest.raises(PersistenceIntegrityError) as exc:
        harness.check(_changed_source_snapshot_bytes())
    assert exc.value.details["reason"] == "adopted_contribution_missing"


def test_deleted_adopted_identity_decision_fails_closed_before_stale() -> None:
    harness = _adopted_harness()
    target = parse_sealed_bundle().identity_decisions[0]
    harness.identity._items.pop((WORLD_ID, target.decision_id))
    with pytest.raises(PersistenceIntegrityError) as exc:
        harness.check(_changed_source_snapshot_bytes())
    assert exc.value.details["reason"] == "adopted_identity_decision_missing"


def test_deleted_evidence_referenced_source_revision_fails_closed_before_stale() -> None:
    harness = _adopted_harness()
    target = _evidence_referenced_source_revision_id()
    harness.sources._revisions.pop(target)
    with pytest.raises(PersistenceIntegrityError) as exc:
        harness.check(_changed_source_snapshot_bytes())
    assert exc.value.details["reason"] == "adopted_source_revision_missing"
    assert exc.value.details["source_revision_id"] == target


def test_corrupted_graph_payload_hash_raises_integrity_error() -> None:
    harness = _adopted_harness()
    stored = harness.world_graph._revisions[(WORLD_ID, PUBLISHED_REVISION_ID)]
    stored.graph_payload["objects"][0]["label"] = "Tampered label"
    with pytest.raises(PersistenceIntegrityError) as exc:
        harness.check()
    assert exc.value.details["reason"] == "adopted_graph_payload_hash_drift"


def test_unavailable_receipt_read_raises_and_never_classifies() -> None:
    harness = _adopted_harness()
    inner = harness.adoptions

    class _UnavailableAdoptions:
        def adopt(self, command):
            return inner.adopt(command)

        def get(self, world_id: str, adoption_id: str):
            return inner.get(world_id, adoption_id)

        def get_for_world(self, world_id: str):
            raise PersistenceUnavailableError("simulated receipt-store outage")

    service = ExistingWorldCorrespondenceService(
        adoption_repository=_UnavailableAdoptions(),
        world_graph_repository=harness.world_graph,
        contribution_repository=harness.contributions,
        identity_repository=harness.identity,
        source_repository=harness.sources,
        graph_reader=eldyrwild_graph_reader(),
    )
    with pytest.raises(PersistenceUnavailableError):
        service.check(raw_bundle(), world_id=WORLD_ID)
    retried = harness.check()
    assert retried.classification == "CORRESPONDING"


def test_unavailable_history_read_raises_and_retry_reevaluates_fresh() -> None:
    harness = _adopted_harness()
    inner = harness.contributions

    class _UnavailableContributions:
        def append(self, contribution):
            return inner.append(contribution)

        def get(self, world_id: str, contribution_id: str):
            return inner.get(world_id, contribution_id)

        def list_for_world(self, world_id: str, *, status=None):
            raise PersistenceUnavailableError("simulated contribution-store outage")

        def update_status(self, world_id, contribution_id, status, *, superseded_by=None):
            return inner.update_status(
                world_id,
                contribution_id,
                status,
                superseded_by=superseded_by,
            )

    service = ExistingWorldCorrespondenceService(
        adoption_repository=harness.adoptions,
        world_graph_repository=harness.world_graph,
        contribution_repository=_UnavailableContributions(),
        identity_repository=harness.identity,
        source_repository=harness.sources,
        graph_reader=eldyrwild_graph_reader(),
    )
    with pytest.raises(PersistenceUnavailableError):
        service.check(raw_bundle(), world_id=WORLD_ID)
    retried = harness.check()
    assert retried.classification == "CORRESPONDING"
