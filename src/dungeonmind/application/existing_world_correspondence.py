"""Read-only observational correspondence for one adopted existing world.

The checker answers one narrow question: does one supplied Buddy authority
snapshot (exact ``ExistingWorldAdoptionBundleV2`` bytes) observationally
correspond to one adopted DungeonMind world? It never writes, never repairs,
never auto-adopts or catches up, and never infers adoption state from the
current head, a world label, or latest-by-timestamp state. The adoption
receipt is retrieved independently via ``get_for_world(world_id)``.

``source_identity`` pins the exact adopted bundle identity, not a field
subset: the supplied bytes' SHA-256 (the bundle parser proves supplied bytes
are the canonical bytes) must equal the receipt's ``bundle_sha256``, and the
bundle's ``adoption_id`` and full ``source_provenance`` must equal the
receipt's. A snapshot that is merely revision-compatible — same source
revision, graph, and history but a different adoption identity — is
``STALE``, never ``CORRESPONDING``.

Errors are raised, never returned as classifications:

- malformed or integrity-invalid source input raises
  ``PersistenceIntegrityError`` (the unchanged #33 bundle parser names the
  parse/schema/self-hash failure in ``details["reason"]``);
- a receipt whose referenced world/revision/payload/history/evidence is
  missing or integrity-invalid raises ``PersistenceIntegrityError`` —
  corrupted adopted state is never ``NOT_ADOPTED``, never ``STALE``, and
  never ``MISMATCH``;
- persistence outages raise ``PersistenceUnavailableError``; no result is
  produced and a retry is a fresh read-only re-evaluation.

Evaluation order (receipt presence is decided before any comparison, and
receipt-referenced state is resolved before any classification):

1. parse/validate the source input;
2. receipt lookup — a miss classifies ``NOT_ADOPTED``;
3. resolve the receipt's referenced durable state, independent of the
   supplied snapshot: the pinned published revision and graph payload (hash
   chain plus parse), the per-world contribution and identity histories
   (enumerated; a count below the receipt's adoption-time pin means adopted
   rows are missing), and the complete per-world source membership
   (artifacts enumerated via ``list_artifacts_for_world``, revisions per
   artifact; counts below the receipt's pins mean adopted source rows are
   missing, and every source record referenced by the adopted payload's
   evidence or the enumerated contributions must be present) — missing or
   integrity-invalid referenced state raises;
4. ``source_identity`` — exact bundle identity (canonical SHA-256,
   ``adoption_id``, full ``source_provenance``); a divergence classifies
   ``STALE`` and every other check is ``not_evaluated`` (a different valid
   snapshot's history is its own, never the receipt's referenced history);
5. only for an identity-matched snapshot — whose bytes are exactly the
   adopted bundle, so its claimed history is the receipt-committed history —
   verify every claimed identity against the resolved membership (a
   same-cardinality swap is caught here by identity, never by count) and
   compare; ``CORRESPONDING`` when every check matches, ``MISMATCH`` when at
   least one diverges.

Port-surface boundary: contribution, identity, and source-artifact history
are all enumerated per world, so extra durable records diverge at compare
time and deleted records fail closed before classification. Source revisions
are enumerated per artifact through the world's complete artifact
membership, so the receipt's adoption-time cardinality pins are fully
operational for source history.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NoReturn

from pydantic import BaseModel, ValidationError

from ..contracts.evidence import SourceArtifactRecord, SourceRevision
from ..contracts.existing_world_adoption import (
    ExistingWorldAdoptionSourceProvenanceV1,
    sha256_bytes,
)
from ..contracts.existing_world_correspondence import (
    CORRESPONDENCE_CHECK_ORDER,
    CorrespondenceCheckName,
    ExistingWorldCorrespondenceCheckV1,
    ExistingWorldCorrespondenceResultV1,
)
from ..contracts.graph import StoredGraphRevision
from ..domain.canonical import canonical_json, canonical_sha256
from ..domain.errors import PersistenceIntegrityError
from .existing_world_adoption import (
    ExistingWorldAdoptionBundle,
    parse_existing_world_adoption_bundle,
)
from .graph_snapshot import GraphSnapshotReader, ParsedGraphSnapshot
from .repositories import (
    ContributionRepository,
    DurableExistingWorldAdoptionReceipt,
    DurableGraphContribution,
    DurableIdentityDecision,
    ExistingWorldAdoptionRepository,
    IdentityDecisionRepository,
    SourceRepository,
    WorldGraphRepository,
)


def _integrity(reason: str, **details: Any) -> NoReturn:
    raise PersistenceIntegrityError(
        "existing-world correspondence failed persistence-integrity validation",
        details={"reason": reason, **details},
    ) from None


def _record_digest(model: BaseModel) -> str:
    return canonical_sha256(model.model_dump(mode="json"))


def _provenance_drifts(
    observed: ExistingWorldAdoptionSourceProvenanceV1,
    adopted: ExistingWorldAdoptionSourceProvenanceV1,
) -> list[str]:
    drifts: list[str] = []
    for field in (
        "producer_id",
        "producer_revision",
        "source_world_revision_id",
        "source_graph_payload_sha256",
    ):
        observed_value = getattr(observed, field)
        adopted_value = getattr(adopted, field)
        if observed_value != adopted_value:
            drifts.append(
                f"source_provenance.{field}: observed {observed_value!r} "
                f"differs from adopted {adopted_value!r}"
            )
    if observed.authority_refs != adopted.authority_refs:
        drifts.append(
            "source_provenance.authority_refs: observed "
            f"{len(observed.authority_refs)} refs differ from adopted "
            f"{len(adopted.authority_refs)} refs"
        )
    return drifts


@dataclass(frozen=True)
class _ResolvedRevision:
    stored: StoredGraphRevision
    snapshot: ParsedGraphSnapshot


@dataclass(frozen=True)
class _ResolvedHistory:
    artifacts: dict[str, SourceArtifactRecord]
    revisions: dict[str, SourceRevision]
    revision_ids_by_artifact: dict[str, set[str]]
    contributions: dict[str, DurableGraphContribution]
    identity_decisions: dict[str, DurableIdentityDecision]


class ExistingWorldCorrespondenceService:
    """Read-only correspondence evaluator over the existing-world ports."""

    def __init__(
        self,
        *,
        adoption_repository: ExistingWorldAdoptionRepository,
        world_graph_repository: WorldGraphRepository,
        contribution_repository: ContributionRepository,
        identity_repository: IdentityDecisionRepository,
        source_repository: SourceRepository,
        graph_reader: GraphSnapshotReader,
    ) -> None:
        self._adoptions = adoption_repository
        self._world_graph = world_graph_repository
        self._contributions = contribution_repository
        self._identity = identity_repository
        self._sources = source_repository
        self._graph_reader = graph_reader

    def check(
        self,
        raw_bundle: bytes,
        *,
        world_id: str,
    ) -> ExistingWorldCorrespondenceResultV1:
        """Classify snapshot↔adopted-world correspondence. Never writes."""
        bundle = parse_existing_world_adoption_bundle(
            raw_bundle,
            graph_reader=self._graph_reader,
        )
        if bundle.world_id != world_id:
            _integrity(
                "world_id_drift",
                bundle_world_id=bundle.world_id,
                world_id=world_id,
            )
        observed_source_revision = bundle.source_provenance.source_world_revision_id
        observed_bundle_sha256 = sha256_bytes(bytes(raw_bundle))

        receipt = self._adoptions.get_for_world(world_id)
        if receipt is None:
            return ExistingWorldCorrespondenceResultV1(
                classification="NOT_ADOPTED",
                world_id=world_id,
                observed_source_revision=observed_source_revision,
            )
        if receipt.world_id != world_id:
            _integrity(
                "receipt_world_mismatch",
                receipt_world_id=receipt.world_id,
                world_id=world_id,
            )

        resolved = self._resolve_revision(world_id=world_id, receipt=receipt)
        history = self._resolve_adopted_history(
            world_id=world_id,
            receipt=receipt,
            resolved=resolved,
        )

        checks: dict[CorrespondenceCheckName, ExistingWorldCorrespondenceCheckV1] = {}
        checks["source_identity"] = self._source_identity_check(
            bundle,
            observed_bundle_sha256=observed_bundle_sha256,
            receipt=receipt,
        )
        if checks["source_identity"].outcome == "diverged":
            for name in CORRESPONDENCE_CHECK_ORDER[1:]:
                checks[name] = ExistingWorldCorrespondenceCheckV1(
                    check=name,
                    outcome="not_evaluated",
                    detail="not evaluated: source_identity diverged",
                )
            return self._result(
                "STALE",
                world_id=world_id,
                observed_source_revision=observed_source_revision,
                receipt=receipt,
                checks=checks,
            )

        self._resolve_claimed_history(bundle, history=history)
        bundle_snapshot = self._graph_reader.parse(
            graph_schema=bundle.graph_schema,
            graph_payload=bundle.graph_payload,
        )
        checks["graph_payload"] = self._graph_payload_check(bundle, resolved)
        checks["source_history"] = self._source_history_check(bundle, receipt, history)
        checks["contribution_history"] = self._contribution_history_check(
            bundle, receipt, history
        )
        checks["identity_history"] = self._identity_history_check(bundle, receipt, history)
        checks["evidence_identity"] = self._evidence_identity_check(
            bundle_snapshot, resolved.snapshot
        )
        classification = (
            "CORRESPONDING"
            if all(check.outcome == "match" for check in checks.values())
            else "MISMATCH"
        )
        return self._result(
            classification,
            world_id=world_id,
            observed_source_revision=observed_source_revision,
            receipt=receipt,
            checks=checks,
        )

    def _result(
        self,
        classification: Any,
        *,
        world_id: str,
        observed_source_revision: str,
        receipt: DurableExistingWorldAdoptionReceipt,
        checks: dict[CorrespondenceCheckName, ExistingWorldCorrespondenceCheckV1],
    ) -> ExistingWorldCorrespondenceResultV1:
        return ExistingWorldCorrespondenceResultV1(
            classification=classification,
            world_id=world_id,
            observed_source_revision=observed_source_revision,
            adopted_source_revision=receipt.source_provenance.source_world_revision_id,
            adoption_id=receipt.adoption_id,
            adopted_revision=receipt.published_revision_id,
            checks=[checks[name] for name in CORRESPONDENCE_CHECK_ORDER],
        )

    def _resolve_revision(
        self,
        *,
        world_id: str,
        receipt: DurableExistingWorldAdoptionReceipt,
    ) -> _ResolvedRevision:
        stored = self._world_graph.get_revision(world_id, receipt.published_revision_id)
        if stored is None:
            _integrity(
                "adopted_revision_missing",
                world_id=world_id,
                published_revision_id=receipt.published_revision_id,
            )
        assert stored is not None
        if stored.revision.world_id != world_id:
            _integrity(
                "adopted_revision_world_mismatch",
                world_id=world_id,
                published_revision_id=receipt.published_revision_id,
            )
        payload_sha256 = canonical_sha256(stored.graph_payload)
        if payload_sha256 != stored.revision.graph_payload_sha256:
            _integrity(
                "adopted_graph_payload_hash_drift",
                world_id=world_id,
                published_revision_id=receipt.published_revision_id,
            )
        if stored.revision.graph_payload_sha256 != receipt.graph_payload_sha256:
            _integrity(
                "adopted_graph_payload_receipt_drift",
                world_id=world_id,
                published_revision_id=receipt.published_revision_id,
            )
        try:
            snapshot = self._graph_reader.parse(
                graph_schema=stored.revision.graph_schema,
                graph_payload=stored.graph_payload,
            )
        except PersistenceIntegrityError:
            raise
        except (TypeError, ValidationError, ValueError) as exc:
            raise PersistenceIntegrityError(
                "existing-world correspondence failed persistence-integrity validation",
                details={"reason": "adopted_graph_payload_parse_failed"},
            ) from exc
        if snapshot.world_id != world_id:
            _integrity(
                "adopted_graph_world_mismatch",
                world_id=world_id,
                published_revision_id=receipt.published_revision_id,
            )
        return _ResolvedRevision(stored=stored, snapshot=snapshot)

    def _source_identity_check(
        self,
        bundle: ExistingWorldAdoptionBundle,
        *,
        observed_bundle_sha256: str,
        receipt: DurableExistingWorldAdoptionReceipt,
    ) -> ExistingWorldCorrespondenceCheckV1:
        """Pin the exact adopted bundle identity: canonical SHA-256, adoption
        id, and full source provenance — not a revision-compatible subset."""
        drifts: list[str] = []
        if observed_bundle_sha256 != receipt.bundle_sha256:
            drifts.append(
                f"observed bundle sha256 {observed_bundle_sha256!r} differs from "
                f"adopted bundle sha256 {receipt.bundle_sha256!r}"
            )
        if bundle.adoption_id != receipt.adoption_id:
            drifts.append(
                f"observed adoption_id {bundle.adoption_id!r} differs from "
                f"adopted adoption_id {receipt.adoption_id!r}"
            )
        drifts.extend(
            _provenance_drifts(bundle.source_provenance, receipt.source_provenance)
        )
        if not drifts:
            return ExistingWorldCorrespondenceCheckV1(
                check="source_identity", outcome="match"
            )
        return ExistingWorldCorrespondenceCheckV1(
            check="source_identity",
            outcome="diverged",
            detail="source identity diverged: " + "; ".join(drifts),
        )

    def _resolve_adopted_history(
        self,
        *,
        world_id: str,
        receipt: DurableExistingWorldAdoptionReceipt,
        resolved: _ResolvedRevision,
    ) -> _ResolvedHistory:
        """Resolve receipt-referenced history independent of the supplied snapshot.

        The receipt pins per-world contribution/identity/source cardinality at
        adoption time; enumeration below a pin means adopted rows are missing.
        Source membership is enumerated completely (artifacts per world, then
        revisions per artifact), so even a source record referenced by neither
        evidence nor contributions is accounted for before classification.
        Every source record the adopted payload's evidence or the enumerated
        contributions reference must be present in that membership. Adapter
        reads fail closed on integrity-invalid records. Runs before any
        classification so corrupted adopted state can never hide behind a
        ``STALE`` result.
        """
        referenced_artifact_ids: set[str] = set()
        referenced_revision_ids: set[str] = set()
        for evidence in resolved.snapshot.evidence.values():
            if evidence.source_artifact_id:
                referenced_artifact_ids.add(evidence.source_artifact_id)
            if evidence.source_revision_id is not None:
                referenced_revision_ids.add(evidence.source_revision_id)

        contributions = {
            item.contribution_id: item
            for item in self._contributions.list_for_world(world_id)
        }
        if len(contributions) < receipt.contribution_count:
            _integrity(
                "adopted_contribution_missing",
                world_id=world_id,
                adopted_contribution_count=receipt.contribution_count,
                durable_contribution_count=len(contributions),
            )
        for contribution in contributions.values():
            if contribution.source_artifact_id is not None:
                referenced_artifact_ids.add(contribution.source_artifact_id)
            if contribution.source_revision_id is not None:
                referenced_revision_ids.add(contribution.source_revision_id)
            for assertion in contribution.assertions:
                if assertion.source_artifact_id is not None:
                    referenced_artifact_ids.add(assertion.source_artifact_id)
                if assertion.source_revision_id is not None:
                    referenced_revision_ids.add(assertion.source_revision_id)

        identity_decisions = {
            item.decision_id: item for item in self._identity.list_for_world(world_id)
        }
        if len(identity_decisions) < receipt.identity_decision_count:
            _integrity(
                "adopted_identity_decision_missing",
                world_id=world_id,
                adopted_identity_decision_count=receipt.identity_decision_count,
                durable_identity_decision_count=len(identity_decisions),
            )

        artifacts = {
            artifact.source_artifact_id: artifact
            for artifact in self._sources.list_artifacts_for_world(world_id)
        }
        revision_ids_by_artifact: dict[str, set[str]] = {}
        revisions: dict[str, SourceRevision] = {}
        for artifact_id in sorted(artifacts):
            artifact_revisions = self._sources.list_revisions(artifact_id)
            revision_ids_by_artifact[artifact_id] = {
                revision.source_revision_id for revision in artifact_revisions
            }
            for revision in artifact_revisions:
                revisions[revision.source_revision_id] = revision

        for artifact_id in sorted(referenced_artifact_ids):
            if artifact_id not in artifacts:
                _integrity(
                    "adopted_source_artifact_missing",
                    source_artifact_id=artifact_id,
                )
        for revision_id in sorted(referenced_revision_ids):
            if revision_id not in revisions:
                _integrity(
                    "adopted_source_revision_missing",
                    source_revision_id=revision_id,
                )
        if len(artifacts) < receipt.source_artifact_count:
            _integrity(
                "adopted_source_artifact_missing",
                world_id=world_id,
                adopted_source_artifact_count=receipt.source_artifact_count,
                durable_source_artifact_count=len(artifacts),
            )
        if len(revisions) < receipt.source_revision_count:
            _integrity(
                "adopted_source_revision_missing",
                world_id=world_id,
                adopted_source_revision_count=receipt.source_revision_count,
                durable_source_revision_count=len(revisions),
            )
        return _ResolvedHistory(
            artifacts=artifacts,
            revisions=revisions,
            revision_ids_by_artifact=revision_ids_by_artifact,
            contributions=contributions,
            identity_decisions=identity_decisions,
        )

    def _resolve_claimed_history(
        self,
        bundle: ExistingWorldAdoptionBundle,
        *,
        history: _ResolvedHistory,
    ) -> None:
        """Complete resolution for an identity-matched snapshot.

        The supplied bytes are exactly the adopted bundle, so every claimed
        identity is receipt-committed; a missing row is dangling adopted
        state. A same-cardinality contribution/identity swap is caught here by
        identity, never by count.
        """
        for artifact in bundle.source_artifacts:
            if artifact.source_artifact_id not in history.artifacts:
                durable = self._sources.get_artifact(artifact.source_artifact_id)
                if durable is None:
                    _integrity(
                        "adopted_source_artifact_missing",
                        source_artifact_id=artifact.source_artifact_id,
                    )
                history.artifacts[artifact.source_artifact_id] = durable
            if artifact.source_artifact_id not in history.revision_ids_by_artifact:
                history.revision_ids_by_artifact[artifact.source_artifact_id] = {
                    revision.source_revision_id
                    for revision in self._sources.list_revisions(
                        artifact.source_artifact_id
                    )
                }
        for revision in bundle.source_revisions:
            if revision.source_revision_id not in history.revisions:
                durable = self._sources.get_revision(revision.source_revision_id)
                if durable is None:
                    _integrity(
                        "adopted_source_revision_missing",
                        source_revision_id=revision.source_revision_id,
                    )
                history.revisions[revision.source_revision_id] = durable
        for contribution in bundle.contributions:
            if contribution.contribution_id not in history.contributions:
                _integrity(
                    "adopted_contribution_missing",
                    contribution_id=contribution.contribution_id,
                )
        for decision in bundle.identity_decisions:
            if decision.decision_id not in history.identity_decisions:
                _integrity(
                    "adopted_identity_decision_missing",
                    decision_id=decision.decision_id,
                )

    def _graph_payload_check(
        self,
        bundle: ExistingWorldAdoptionBundle,
        resolved: _ResolvedRevision,
    ) -> ExistingWorldCorrespondenceCheckV1:
        durable_sha256 = canonical_sha256(resolved.stored.graph_payload)
        observed_sha256 = canonical_sha256(bundle.graph_payload)
        if durable_sha256 == observed_sha256:
            return ExistingWorldCorrespondenceCheckV1(check="graph_payload", outcome="match")
        return ExistingWorldCorrespondenceCheckV1(
            check="graph_payload",
            outcome="diverged",
            detail=(
                f"durable graph payload sha256 {durable_sha256!r} differs "
                f"from snapshot {observed_sha256!r}"
            ),
        )

    def _source_history_check(
        self,
        bundle: ExistingWorldAdoptionBundle,
        receipt: DurableExistingWorldAdoptionReceipt,
        history: _ResolvedHistory,
    ) -> ExistingWorldCorrespondenceCheckV1:
        drifted_artifacts = sorted(
            artifact.source_artifact_id
            for artifact in bundle.source_artifacts
            if _record_digest(history.artifacts[artifact.source_artifact_id])
            != _record_digest(artifact)
        )
        drifted_revisions = sorted(
            revision.source_revision_id
            for revision in bundle.source_revisions
            if _record_digest(history.revisions[revision.source_revision_id])
            != _record_digest(revision)
        )
        bundle_revision_ids_by_artifact: dict[str, set[str]] = {
            artifact.source_artifact_id: set() for artifact in bundle.source_artifacts
        }
        for revision in bundle.source_revisions:
            bundle_revision_ids_by_artifact.setdefault(
                revision.source_artifact_id, set()
            ).add(revision.source_revision_id)
        revision_set_drift = sorted(
            artifact_id
            for artifact_id, durable_ids in history.revision_ids_by_artifact.items()
            if durable_ids != bundle_revision_ids_by_artifact.get(artifact_id, set())
        )
        extra_artifacts = sorted(
            set(history.artifacts)
            - {artifact.source_artifact_id for artifact in bundle.source_artifacts}
        )
        count_drift: list[str] = []
        if len(bundle.source_artifacts) != receipt.source_artifact_count:
            count_drift.append(
                f"source_artifacts:{len(bundle.source_artifacts)}"
                f"!=adopted:{receipt.source_artifact_count}"
            )
        if len(bundle.source_revisions) != receipt.source_revision_count:
            count_drift.append(
                f"source_revisions:{len(bundle.source_revisions)}"
                f"!=adopted:{receipt.source_revision_count}"
            )
        problems = (
            drifted_artifacts
            + drifted_revisions
            + revision_set_drift
            + extra_artifacts
            + count_drift
        )
        if not problems:
            return ExistingWorldCorrespondenceCheckV1(check="source_history", outcome="match")
        return ExistingWorldCorrespondenceCheckV1(
            check="source_history",
            outcome="diverged",
            detail=(
                "source history diverged: "
                f"drifted_artifacts={drifted_artifacts} "
                f"drifted_revisions={drifted_revisions} "
                f"revision_set_drift={revision_set_drift} "
                f"extra_artifacts={extra_artifacts} "
                f"count_drift={count_drift}"
            ),
        )

    def _contribution_history_check(
        self,
        bundle: ExistingWorldAdoptionBundle,
        receipt: DurableExistingWorldAdoptionReceipt,
        history: _ResolvedHistory,
    ) -> ExistingWorldCorrespondenceCheckV1:
        bundle_ids = {item.contribution_id for item in bundle.contributions}
        drifted = sorted(
            contribution.contribution_id
            for contribution in bundle.contributions
            if _record_digest(history.contributions[contribution.contribution_id])
            != _record_digest(contribution)
        )
        extra = sorted(set(history.contributions) - bundle_ids)
        count_drift: list[str] = []
        if len(bundle.contributions) != receipt.contribution_count:
            count_drift.append(
                f"contributions:{len(bundle.contributions)}"
                f"!=adopted:{receipt.contribution_count}"
            )
        if not drifted and not extra and not count_drift:
            return ExistingWorldCorrespondenceCheckV1(
                check="contribution_history", outcome="match"
            )
        return ExistingWorldCorrespondenceCheckV1(
            check="contribution_history",
            outcome="diverged",
            detail=(
                "contribution history diverged: "
                f"drifted={drifted} extra={extra} count_drift={count_drift}"
            ),
        )

    def _identity_history_check(
        self,
        bundle: ExistingWorldAdoptionBundle,
        receipt: DurableExistingWorldAdoptionReceipt,
        history: _ResolvedHistory,
    ) -> ExistingWorldCorrespondenceCheckV1:
        bundle_ids = {item.decision_id for item in bundle.identity_decisions}
        drifted = sorted(
            decision.decision_id
            for decision in bundle.identity_decisions
            if _record_digest(history.identity_decisions[decision.decision_id])
            != _record_digest(decision)
        )
        extra = sorted(set(history.identity_decisions) - bundle_ids)
        count_drift: list[str] = []
        if len(bundle.identity_decisions) != receipt.identity_decision_count:
            count_drift.append(
                f"identity_decisions:{len(bundle.identity_decisions)}"
                f"!=adopted:{receipt.identity_decision_count}"
            )
        if not drifted and not extra and not count_drift:
            return ExistingWorldCorrespondenceCheckV1(
                check="identity_history", outcome="match"
            )
        return ExistingWorldCorrespondenceCheckV1(
            check="identity_history",
            outcome="diverged",
            detail=(
                "identity history diverged: "
                f"drifted={drifted} extra={extra} count_drift={count_drift}"
            ),
        )

    def _evidence_identity_check(
        self,
        bundle_snapshot: ParsedGraphSnapshot,
        durable_snapshot: ParsedGraphSnapshot,
    ) -> ExistingWorldCorrespondenceCheckV1:
        bundle_evidence = {
            evidence_id: canonical_json(record.model_dump(mode="json"))
            for evidence_id, record in bundle_snapshot.evidence.items()
        }
        durable_evidence = {
            evidence_id: canonical_json(record.model_dump(mode="json"))
            for evidence_id, record in durable_snapshot.evidence.items()
        }
        missing_in_durable = sorted(set(bundle_evidence) - set(durable_evidence))
        extra_in_durable = sorted(set(durable_evidence) - set(bundle_evidence))
        drifted = sorted(
            evidence_id
            for evidence_id in set(bundle_evidence) & set(durable_evidence)
            if bundle_evidence[evidence_id] != durable_evidence[evidence_id]
        )
        if not missing_in_durable and not extra_in_durable and not drifted:
            return ExistingWorldCorrespondenceCheckV1(
                check="evidence_identity", outcome="match"
            )
        return ExistingWorldCorrespondenceCheckV1(
            check="evidence_identity",
            outcome="diverged",
            detail=(
                "evidence identity diverged: "
                f"drifted={drifted} missing_in_durable={missing_in_durable} "
                f"extra_in_durable={extra_in_durable}"
            ),
        )
