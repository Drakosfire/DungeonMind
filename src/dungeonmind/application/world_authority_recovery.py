"""Read-only Eldyrwild World authority preflight.

This module does not restore databases, run SQL, or write graph history.
Callers supply already-constructed application repositories. Restore/backup
remain operator/Postgres tooling in the recovery script.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

ELDYRWILD_WORLD_ID = "eldyrwild"
ELDYRWILD_D_A = "rev:34b1f8e2625d5ba693fc726a2a1a4720"
ELDYRWILD_D_B = "rev:680c246047d67f9fe0293ee90526f670"
ELDYRWILD_BUNDLE_SHA256 = "90574dfc4101e4198c7fd96478d6f49e65aa534d0aa91fa41a9a17da9d49695f"
ELDYRWILD_MEMBERSHIP_M0 = "538195e399158bfb4fafce01f9c5af3c63e2137f70694fdead7a26e5800e0890"
ELDYRWILD_MEMBERSHIP_M1 = "16d3161d270691460ccbf6d183055ad9f29f00bdbecf5c26dfe0189da2b9914e"
ELDYRWILD_RECEIPT_SCHEMA_V3 = "dm_existing_world_adoption_receipt_v3"
ELDYRWILD_RECEIPT_SCHEMA_V4 = "dm_existing_world_adoption_receipt_v4"
ELDYRWILD_ADOPTION_ARTIFACTS = 83
ELDYRWILD_ADOPTION_SOURCE_REVISIONS = 83
ELDYRWILD_ADOPTION_CONTRIBUTIONS = 93
ELDYRWILD_ADOPTION_IDENTITY_DECISIONS = 13
ELDYRWILD_D_B_CONTRIBUTIONS = 95
ELDYRWILD_SCHEMA_REVISION = "0007_reviewed_world_init"

STATUS_READY = "READY"
STATUS_NOT_READY = "NOT_READY"

REASON_WORLD_MISSING = "world_missing"
REASON_STALE_RECOVERY_POINT = "stale_recovery_point"
REASON_INTEGRITY_FAILURE = "integrity_failure"
REASON_AUTHORITY_UNAVAILABLE = "authority_unavailable"


class _Head(Protocol):
    world_id: str
    head_revision_id: str


class _RevisionEnvelope(Protocol):
    revision_id: str
    parent_revision_id: str | None
    world_id: str


class _StoredRevision(Protocol):
    revision: _RevisionEnvelope


class _WorldGraph(Protocol):
    def get_head(self, world_id: str) -> _Head | None: ...

    def get_revision(self, world_id: str, revision_id: str) -> _StoredRevision | None: ...


class _Adoptions(Protocol):
    def get_for_world(self, world_id: str) -> Any | None: ...


class _Sources(Protocol):
    def list_artifacts_for_world(self, world_id: str) -> list[Any]: ...

    def list_revisions(self, source_artifact_id: str) -> list[Any]: ...


class _WorldList(Protocol):
    def list_for_world(self, world_id: str) -> list[Any]: ...


@dataclass(frozen=True)
class RecoveryExpectation:
    world_id: str = ELDYRWILD_WORLD_ID
    adopted_revision_id: str = ELDYRWILD_D_A
    expected_head: str = ELDYRWILD_D_B
    expected_parent: str = ELDYRWILD_D_A
    bundle_sha256: str = ELDYRWILD_BUNDLE_SHA256
    membership_m0: str = ELDYRWILD_MEMBERSHIP_M0
    membership_m1: str = ELDYRWILD_MEMBERSHIP_M1
    receipt_schema: str = ELDYRWILD_RECEIPT_SCHEMA_V4
    artifact_count: int = ELDYRWILD_ADOPTION_ARTIFACTS
    source_revision_count: int = ELDYRWILD_ADOPTION_SOURCE_REVISIONS
    adoption_contribution_count: int = ELDYRWILD_ADOPTION_CONTRIBUTIONS
    current_contribution_count: int = ELDYRWILD_D_B_CONTRIBUTIONS
    identity_decision_count: int = ELDYRWILD_ADOPTION_IDENTITY_DECISIONS
    schema_revision: str = ELDYRWILD_SCHEMA_REVISION


@dataclass(frozen=True)
class ProjectionWitness:
    revision_id: str
    head_revision_id: str
    object_count: int


@dataclass(frozen=True)
class WorldAuthorityPreflight:
    status: str
    reason: str | None
    world_id: str
    schema_revision: str | None = None
    receipt_schema: str | None = None
    adopted_revision_id: str | None = None
    current_head: str | None = None
    parent_revision_id: str | None = None
    bundle_sha256: str | None = None
    membership_m0: str | None = None
    membership_m1: str | None = None
    artifact_count: int | None = None
    source_revision_count: int | None = None
    contribution_count: int | None = None
    identity_decision_count: int | None = None
    projection: ProjectionWitness | None = None
    diagnostics: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ready(self) -> bool:
        return self.status == STATUS_READY


def _receipt_shape_diagnostics(
    *,
    receipt: Any | None,
    receipt_schema: str | None,
    bundle_sha256: str | None,
    membership_m0: str | None,
    membership_m1: str | None,
    adopted_revision_id: str | None,
    expected: RecoveryExpectation,
) -> list[str]:
    """Accept the dump-stored v3 checkpoint or a later v4 wrapper.

    The CHECKPOINT A dump stores ``dm_existing_world_adoption_receipt_v3`` with
    ``membership_sha256`` equal to the post-repair digest (M1). A sidecar
    records the v4 M0/M1 pair, but those fields are not in the dump. Do not
    rewrite the restored receipt.
    """

    if receipt is None:
        return ["existing-world adoption receipt is missing"]
    diagnostics: list[str] = []
    if bundle_sha256 != expected.bundle_sha256:
        diagnostics.append("adoption bundle digest mismatch")
    if adopted_revision_id != expected.adopted_revision_id:
        diagnostics.append(
            f"adopted revision {adopted_revision_id!r} != {expected.adopted_revision_id!r}"
        )
    receipt_artifact_count = getattr(receipt, "source_artifact_count", None)
    if receipt_artifact_count != expected.artifact_count:
        diagnostics.append("receipt source_artifact_count mismatch")
    if receipt_schema == ELDYRWILD_RECEIPT_SCHEMA_V4:
        if membership_m0 != expected.membership_m0:
            diagnostics.append("membership M0 mismatch")
        if membership_m1 != expected.membership_m1:
            diagnostics.append("membership M1 mismatch")
    elif receipt_schema == ELDYRWILD_RECEIPT_SCHEMA_V3:
        if membership_m0 != expected.membership_m1:
            diagnostics.append("dump v3 membership checkpoint mismatch")
        if membership_m1 is not None:
            diagnostics.append("v3 receipt must not carry effective_membership_sha256")
    else:
        diagnostics.append(f"unsupported receipt schema {receipt_schema!r}")
    return diagnostics


def unavailable_preflight(
    *,
    world_id: str = ELDYRWILD_WORLD_ID,
    diagnostic: str,
) -> WorldAuthorityPreflight:
    return WorldAuthorityPreflight(
        status=STATUS_NOT_READY,
        reason=REASON_AUTHORITY_UNAVAILABLE,
        world_id=world_id,
        diagnostics=(diagnostic,),
    )


def check_world_authority(
    *,
    world_graph: _WorldGraph,
    adoptions: _Adoptions,
    sources: _Sources,
    contributions: _WorldList,
    identity_decisions: _WorldList,
    expected: RecoveryExpectation | None = None,
    project: Callable[[], ProjectionWitness] | None = None,
    schema_revision: str | None = None,
) -> WorldAuthorityPreflight:
    """Verify one Eldyrwild database against the accepted D_A/D_B lineage."""

    expectation = expected or RecoveryExpectation()
    diagnostics: list[str] = []
    world_id = expectation.world_id

    receipt = adoptions.get_for_world(world_id)
    head = world_graph.get_head(world_id)
    if receipt is None and head is None:
        return WorldAuthorityPreflight(
            status=STATUS_NOT_READY,
            reason=REASON_WORLD_MISSING,
            world_id=world_id,
            schema_revision=schema_revision,
            diagnostics=("no adoption receipt and no world head",),
        )

    adopted_revision_id = getattr(receipt, "published_revision_id", None) if receipt else None
    current_head = getattr(head, "head_revision_id", None) if head else None
    receipt_schema = getattr(receipt, "schema_version", None) if receipt else None
    bundle_sha256 = getattr(receipt, "bundle_sha256", None) if receipt else None
    membership_m0 = getattr(receipt, "membership_sha256", None) if receipt else None
    membership_m1 = getattr(receipt, "effective_membership_sha256", None) if receipt else None

    artifacts = sources.list_artifacts_for_world(world_id)
    source_revision_count = 0
    for artifact in artifacts:
        artifact_id = getattr(artifact, "source_artifact_id", None)
        if not artifact_id:
            diagnostics.append("source artifact missing source_artifact_id")
            continue
        source_revision_count += len(sources.list_revisions(artifact_id))
    contribution_count = len(contributions.list_for_world(world_id))
    identity_count = len(identity_decisions.list_for_world(world_id))

    parent_revision_id: str | None = None
    if current_head:
        stored = world_graph.get_revision(world_id, current_head)
        if stored is None:
            diagnostics.append(f"current head {current_head} has no stored revision")
        else:
            parent_revision_id = stored.revision.parent_revision_id

    adopted_stored = None
    if adopted_revision_id:
        adopted_stored = world_graph.get_revision(world_id, adopted_revision_id)
        if adopted_stored is None:
            diagnostics.append(f"adopted revision {adopted_revision_id} is missing")
        elif adopted_stored.revision.parent_revision_id is not None:
            diagnostics.append("adopted D_A must be parentless")

    diagnostics.extend(
        _receipt_shape_diagnostics(
            receipt=receipt,
            receipt_schema=receipt_schema,
            bundle_sha256=bundle_sha256,
            membership_m0=membership_m0,
            membership_m1=membership_m1,
            adopted_revision_id=adopted_revision_id,
            expected=expectation,
        )
    )

    if len(artifacts) != expectation.artifact_count:
        diagnostics.append(
            f"source artifact count {len(artifacts)} != {expectation.artifact_count}"
        )
    if source_revision_count != expectation.source_revision_count:
        diagnostics.append(
            f"source revision count {source_revision_count} != {expectation.source_revision_count}"
        )
    if identity_count != expectation.identity_decision_count:
        diagnostics.append(
            f"identity decision count {identity_count} != {expectation.identity_decision_count}"
        )
    if contribution_count < expectation.adoption_contribution_count:
        diagnostics.append(
            f"contribution count {contribution_count} below adopted "
            f"{expectation.adoption_contribution_count}"
        )
    if contribution_count != expectation.current_contribution_count:
        diagnostics.append(
            f"current contribution count {contribution_count} != "
            f"{expectation.current_contribution_count}"
        )

    if schema_revision != expectation.schema_revision:
        diagnostics.append(
            f"schema revision {schema_revision!r} != {expectation.schema_revision!r}"
        )

    if current_head is None:
        diagnostics.append("world head is missing")
    elif current_head == expectation.adopted_revision_id and (
        current_head != expectation.expected_head
    ):
        return WorldAuthorityPreflight(
            status=STATUS_NOT_READY,
            reason=REASON_STALE_RECOVERY_POINT,
            world_id=world_id,
            schema_revision=schema_revision,
            receipt_schema=receipt_schema,
            adopted_revision_id=adopted_revision_id,
            current_head=current_head,
            parent_revision_id=parent_revision_id,
            bundle_sha256=bundle_sha256,
            membership_m0=membership_m0,
            membership_m1=membership_m1,
            artifact_count=len(artifacts),
            source_revision_count=source_revision_count,
            contribution_count=contribution_count,
            identity_decision_count=identity_count,
            diagnostics=tuple(
                [
                    *diagnostics,
                    "current head is D_A; expected D_B. D_A must not be blessed as current.",
                ]
            ),
        )
    elif current_head != expectation.expected_head:
        diagnostics.append(
            f"current head {current_head!r} != expected {expectation.expected_head!r}"
        )
    elif parent_revision_id != expectation.expected_parent:
        diagnostics.append(
            f"parent({current_head})={parent_revision_id!r} != {expectation.expected_parent!r}"
        )

    projection: ProjectionWitness | None = None
    if project is not None and not diagnostics:
        try:
            projection = project()
        except Exception as exc:
            diagnostics.append(f"projection failed: {exc}")
        else:
            if projection.revision_id != expectation.expected_head:
                diagnostics.append(
                    f"projection revision {projection.revision_id!r} != "
                    f"{expectation.expected_head!r}"
                )
            if projection.head_revision_id != expectation.expected_head:
                diagnostics.append(
                    f"projection head {projection.head_revision_id!r} != "
                    f"{expectation.expected_head!r}"
                )

    if diagnostics:
        return WorldAuthorityPreflight(
            status=STATUS_NOT_READY,
            reason=REASON_INTEGRITY_FAILURE,
            world_id=world_id,
            schema_revision=schema_revision,
            receipt_schema=receipt_schema,
            adopted_revision_id=adopted_revision_id,
            current_head=current_head,
            parent_revision_id=parent_revision_id,
            bundle_sha256=bundle_sha256,
            membership_m0=membership_m0,
            membership_m1=membership_m1,
            artifact_count=len(artifacts),
            source_revision_count=source_revision_count,
            contribution_count=contribution_count,
            identity_decision_count=identity_count,
            projection=projection,
            diagnostics=tuple(diagnostics),
        )

    return WorldAuthorityPreflight(
        status=STATUS_READY,
        reason=None,
        world_id=world_id,
        schema_revision=schema_revision,
        receipt_schema=receipt_schema,
        adopted_revision_id=adopted_revision_id,
        current_head=current_head,
        parent_revision_id=parent_revision_id,
        bundle_sha256=bundle_sha256,
        membership_m0=membership_m0,
        membership_m1=membership_m1,
        artifact_count=len(artifacts),
        source_revision_count=source_revision_count,
        contribution_count=contribution_count,
        identity_decision_count=identity_count,
        projection=projection,
    )
