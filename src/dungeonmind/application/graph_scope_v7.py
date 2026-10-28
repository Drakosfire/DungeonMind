"""Opt-in v7 proof admission composed with the frozen field/relationship projector."""

from __future__ import annotations

from dataclasses import replace

from ..contracts.projection import Admissibility, ScopeMode
from ..contracts.projection_v2 import ScopeModeV2
from .graph_scope import (
    CampaignScope,
    EvidenceResolution,
    GenesisEvidenceCompatibility,
    ObjectScopeExclusion,
    ScopedGraphProjection,
    SourceLookup,
    _admit_v4_assertion,
    project_scoped_snapshot,
)
from .graph_snapshot import (
    GRAPH_SCHEMA_V6,
    GraphObjectView,
    ParsedGraphSnapshot,
    build_label_and_alias_indexes,
)
from .graph_snapshot_v7 import (
    GRAPH_SCHEMA_V7,
    AdmittedExistenceAssertion,
    GraphObjectV7View,
)


def project_scoped_snapshot_v7(
    snapshot: ParsedGraphSnapshot,
    *,
    sources: SourceLookup,
    world_id: str,
    campaign_id: str | None,
    admissibility: Admissibility,
    scope_mode: ScopeMode | ScopeModeV2 | None = None,
    evidence_cache: dict[str, EvidenceResolution] | None = None,
    genesis_compatibility: GenesisEvidenceCompatibility | None = None,
) -> ScopedGraphProjection:
    """Admit complete independent proofs; keep all legacy field gates intact.

    Choosing one proven core claim permits the frozen projector to validate
    fields and endpoint relationships without changing its conjunction rule.
    Other admitted proofs remain separate, inspectable assertions afterward.
    No graph payload, source standing, or durable metadata is rewritten.
    """
    if snapshot.graph_schema != GRAPH_SCHEMA_V7:
        return project_scoped_snapshot(
            snapshot,
            sources=sources,
            world_id=world_id,
            campaign_id=campaign_id,
            admissibility=admissibility,
            scope_mode=scope_mode,
            evidence_cache=evidence_cache,
            genesis_compatibility=genesis_compatibility,
        )
    scope = CampaignScope.resolve(scope_mode=scope_mode, campaign_id=campaign_id)
    cache = evidence_cache if evidence_cache is not None else {}
    selected: dict[str, list[AdmittedExistenceAssertion]] = {}
    hidden: dict[str, ObjectScopeExclusion] = {}
    proof_exclusions: dict[str, ObjectScopeExclusion] = {}
    core_objects = {}
    for oid, obj in snapshot.objects.items():
        if not isinstance(obj, GraphObjectV7View) or obj.existence_assertion_metadata is None:
            hidden[oid] = ObjectScopeExclusion(scope_unknown=True)
            continue
        candidates = [
            AdmittedExistenceAssertion(
                label=obj.label,
                kind=obj.kind,
                assertion_metadata=obj.existence_assertion_metadata,
            ),
            *sorted(
                obj.independent_existence_assertions,
                key=lambda proof: proof.assertion_metadata.assertion_id,
            ),
        ]
        admitted = []
        excluded = []
        for proof in candidates:
            ok, exclusion = _admit_v4_assertion(
                proof.assertion_metadata,
                snapshot=snapshot,
                sources=sources,
                world_id=world_id,
                scope=scope,
                admissibility=admissibility,
                evidence_cache=cache,
                genesis_compatibility=genesis_compatibility,
            )
            if ok:
                admitted.append(proof)
            else:
                excluded.append(exclusion)
                proof_exclusions[proof.assertion_metadata.assertion_id] = exclusion
        if not admitted:
            hidden[oid] = ObjectScopeExclusion(
                rejections=[r for e in excluded for r in e.rejections],
                out_of_scope=any(e.out_of_scope for e in excluded),
                scope_unknown=any(e.scope_unknown for e in excluded),
            )
            continue
        selected[oid] = admitted
        chosen = admitted[0]
        core_objects[oid] = GraphObjectView.model_validate(
            {
                **{name: getattr(obj, name) for name in GraphObjectView.model_fields},
                "label": chosen.label,
                "kind": chosen.kind,
                "existence_assertion_metadata": chosen.assertion_metadata,
                "core_evidence_ref_ids": list(chosen.assertion_metadata.evidence_ref_ids),
            }
        )
    # Only core identity is selected here. The unchanged legacy projector
    # still gates every alias, summary, property, aspect and relationship.
    core = replace(snapshot, graph_schema=GRAPH_SCHEMA_V6, objects=core_objects)
    scoped = project_scoped_snapshot(
        core,
        sources=sources,
        world_id=world_id,
        campaign_id=campaign_id,
        admissibility=admissibility,
        scope_mode=scope_mode,
        evidence_cache=cache,
        genesis_compatibility=genesis_compatibility,
    )
    objects = {}
    evidence = dict(scoped.snapshot.evidence)
    for oid, obj in scoped.snapshot.objects.items():
        proofs = selected[oid]
        core_ids = list(
            dict.fromkeys(eid for p in proofs for eid in p.assertion_metadata.evidence_ref_ids)
        )
        for eid in core_ids:
            evidence[eid] = snapshot.evidence[eid].model_copy(deep=True)
        objects[oid] = GraphObjectV7View.model_validate(
            {
                **{name: getattr(obj, name) for name in GraphObjectView.model_fields},
                "independent_existence_assertions": proofs[1:],
                "core_evidence_ref_ids": core_ids,
                "evidence_ref_ids": list(dict.fromkeys([*core_ids, *obj.evidence_ref_ids])),
                "aliases": list(
                    dict.fromkeys(
                        [
                            *obj.aliases,
                            *(p.label for p in proofs[1:] if p.label != obj.label),
                        ]
                    )
                ),
            }
        )
    labels, aliases = build_label_and_alias_indexes(objects)
    return replace(
        scoped,
        snapshot=replace(
            scoped.snapshot,
            graph_schema=GRAPH_SCHEMA_V7,
            objects=objects,
            evidence=evidence,
            label_index=labels,
            alias_index=aliases,
        ),
        object_exclusions={**scoped.object_exclusions, **hidden},
        assertion_exclusions={**scoped.assertion_exclusions, **proof_exclusions},
    )
