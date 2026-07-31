"""Deterministic context assembly for agent-visible Mind Turn input."""

from __future__ import annotations

from typing import Any

from ..contracts.evidence import EvidenceRef
from ..contracts.projection import Admissibility, ProjectionFocus
from ..contracts.retrieval import Coverage, SourceAnchor
from ..domain.canonical import canonical_json
from .graph_snapshot import GraphObjectView, GraphRelationshipView

DEFAULT_CONTEXT_CHAR_LIMIT = 12_000


def assemble_agent_context(
    *,
    revision_id: str,
    world_id: str,
    campaign_id: str | None,
    admissibility: Admissibility,
    focus: ProjectionFocus,
    objects: list[GraphObjectView],
    relationships: list[GraphRelationshipView],
    evidence: list[EvidenceRef],
    source_anchors: list[SourceAnchor],
    coverage: Coverage,
    char_limit: int = DEFAULT_CONTEXT_CHAR_LIMIT,
) -> str:
    """Build canonical JSON context, truncating lower-ranked candidates first."""

    ranked_objects = list(objects)
    ranked_relationships = list(relationships)
    ranked_evidence = list(evidence)
    ranked_anchors = list(source_anchors)

    def _document(
        objs: list[GraphObjectView],
        rels: list[GraphRelationshipView],
        evs: list[EvidenceRef],
        anchors: list[SourceAnchor],
    ) -> dict[str, Any]:
        return {
            "revision_id": revision_id,
            "world_id": world_id,
            "campaign_id": campaign_id,
            "admissibility": admissibility.value,
            "focus": focus.model_dump(mode="json"),
            "objects": [obj.model_dump(mode="json") for obj in objs],
            "relationships": [rel.model_dump(mode="json") for rel in rels],
            "evidence": [item.model_dump(mode="json") for item in evs],
            "source_anchors": [item.model_dump(mode="json") for item in anchors],
            "coverage": coverage.model_dump(mode="json"),
        }

    document = _document(
        ranked_objects,
        ranked_relationships,
        ranked_evidence,
        ranked_anchors,
    )
    rendered = canonical_json(document)
    while len(rendered.encode("utf-8")) > char_limit:
        if ranked_relationships:
            ranked_relationships.pop()
        elif ranked_objects and len(ranked_objects) > 1:
            ranked_objects.pop()
        elif ranked_anchors:
            ranked_anchors.pop()
        elif ranked_evidence:
            ranked_evidence.pop()
        else:
            break
        document = _document(
            ranked_objects,
            ranked_relationships,
            ranked_evidence,
            ranked_anchors,
        )
        rendered = canonical_json(document)
    return rendered
