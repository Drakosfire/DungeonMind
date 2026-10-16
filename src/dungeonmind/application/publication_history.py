"""Discover verified historical publications without replaying a write.

This explicit review/reopen read walks one immutable pin, never mutable head.
Repositories own durable reconstruction; this service owns the cross-record
correspondence and complete ancestry scan. Errors propagate rather than claiming
an authoritative empty result.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts.review_publication import FinalizedReviewPublication
from ..domain.canonical import canonical_sha256
from ..domain.errors import PersistenceIntegrityError
from .repositories import (
    ContributionReviewRepository,
    DurableContributionReviewState,
    FinalizedReviewPublicationRepository,
    WorldGraphRepository,
)
from .review_publication import _reload_review


@dataclass(frozen=True)
class HistoricalReviewPublication:
    """Native terminal receipt joined to its validated durable review.

    Consumers still prove their own source/candidate mapping. A matching reviewer
    and plan schema alone do not establish complete extraction coverage.
    """

    publication: FinalizedReviewPublication
    review: DurableContributionReviewState


@dataclass(frozen=True)
class PublicationHistory:
    """Complete, newest-first results at the supplied immutable revision pin.

    Only successful complete scans return. This is historical publication, not
    current assertion activity or pending/failed operation history.
    """

    world_id: str
    revision_id: str
    reviewer_id: str
    source_plan_schema: str
    publications: tuple[HistoricalReviewPublication, ...]
    scanned_revision_count: int


def discover_review_publications(
    *,
    world_id: str,
    revision_id: str,
    reviewer_id: str,
    source_plan_schema: str,
    world_graph_repository: WorldGraphRepository,
    publication_repository: FinalizedReviewPublicationRepository,
    review_repository: ContributionReviewRepository,
) -> PublicationHistory:
    """Read every ancestor, then return exact-selector terminal publications.

    Missing required ancestry/review, corrupt joins and unavailable repositories
    raise. There is no cap, partial result, implicit head lookup or write/retry.
    Exact selectors must be derived by the owning consumer, not treated as access
    authorization. Ordinary API capability/World access checks remain upstream.
    """
    if any(not value.strip() for value in (
        world_id, revision_id, reviewer_id, source_plan_schema,
    )):
        raise ValueError("publication history requires nonblank exact selectors")

    visited: set[str] = set()
    matches: list[HistoricalReviewPublication] = []
    current_id: str | None = revision_id
    expected_parent_digest: str | None = None
    expected_parent_schema: str | None = None
    while current_id is not None:
        if current_id in visited:
            raise PersistenceIntegrityError("publication history ancestry contains a cycle")
        visited.add(current_id)
        stored = world_graph_repository.get_revision(world_id, current_id)
        if stored is None:
            raise PersistenceIntegrityError("publication history ancestry is incomplete")
        revision = stored.revision
        if (
            revision.world_id != world_id
            or revision.revision_id != current_id
            or canonical_sha256(stored.graph_payload) != revision.graph_payload_sha256
            or (expected_parent_digest is not None
                and revision.graph_payload_sha256 != expected_parent_digest)
            or (expected_parent_schema is not None
                and revision.graph_schema != expected_parent_schema)
        ):
            raise PersistenceIntegrityError("publication history revision binding disagrees")

        publication = publication_repository.get_for_published_revision(world_id, current_id)
        expected_parent_digest = None
        expected_parent_schema = None
        if publication is not None:
            publication = FinalizedReviewPublication.model_validate(
                publication.model_dump(mode="json")
            )
            if (
                publication.world_id != world_id
                or publication.published_revision_id != current_id
                or publication.expected_parent_revision_id != revision.parent_revision_id
                or publication.graph_payload_sha256 != revision.graph_payload_sha256
                or publication.graph_schema != revision.graph_schema
                or revision.operation_ids != [publication.operation_id]
                or publication.published_at != revision.created_at
            ):
                raise PersistenceIntegrityError("publication history child binding disagrees")
            state = review_repository.get(world_id, publication.review_id)
            if state is None:
                raise PersistenceIntegrityError("publication history review is missing")
            state = _reload_review(state, world_id=world_id, review_id=publication.review_id)
            record = state.record
            if (
                record.reviewed_contribution_id != publication.reviewed_contribution_id
                or record.reviewed_contribution_sha256 != publication.reviewed_contribution_sha256
                or record.review_intent_sha256 != publication.review_intent_sha256
                or record.confirmation_id != publication.confirmation_id
                or record.operation_id != publication.operation_id
                or record.plan_ref.expected_parent_revision_id
                != publication.expected_parent_revision_id
                or record.plan_ref.base_graph_payload_sha256
                != publication.parent_graph_payload_sha256
                or record.plan_ref.base_graph_schema != publication.graph_schema
            ):
                raise PersistenceIntegrityError("publication history review binding disagrees")
            expected_parent_digest = publication.parent_graph_payload_sha256
            expected_parent_schema = publication.graph_schema
            if (
                record.reviewer_id == reviewer_id
                and record.plan_ref.source_plan_schema == source_plan_schema
            ):
                matches.append(HistoricalReviewPublication(publication, state))
        current_id = revision.parent_revision_id

    return PublicationHistory(
        world_id=world_id,
        revision_id=revision_id,
        reviewer_id=reviewer_id,
        source_plan_schema=source_plan_schema,
        publications=tuple(matches),
        scanned_revision_count=len(visited),
    )
