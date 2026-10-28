"""Trusted v3 relationship-rule projection; immutable catalogs are unchanged."""

from dungeonmind.application.semantic_profiles import descriptor_sha256
from dungeonmind.contracts.adopted_relationship_correction import (
    PredicateEndpointRuleV1,
    RelationshipCorrectionRulesV1,
)
from dungeonmind.contracts.semantic_profile import SemanticProfileRef

from .world_object_vocabulary import (
    load_builtin_v3_descriptor,
    load_builtin_world_object_v3_vocabulary,
    vocabulary_sha256,
)


def builtin_v3_relationship_correction_rules() -> RelationshipCorrectionRulesV1:
    descriptor = load_builtin_v3_descriptor()
    catalog = load_builtin_world_object_v3_vocabulary()
    return RelationshipCorrectionRulesV1(
        profile_ref=SemanticProfileRef(
            profile_id=descriptor.profile_id,
            profile_revision=descriptor.profile_revision,
            descriptor_sha256=descriptor_sha256(descriptor),
        ),
        catalog_id=catalog.vocabulary_id,
        catalog_version=catalog.vocabulary_revision,
        catalog_sha256=vocabulary_sha256(catalog),
        predicates=tuple(
            PredicateEndpointRuleV1(
                predicate=p.term,
                subject_kinds=tuple(p.subject_kinds),
                object_kinds=tuple(p.object_kinds),
            )
            for p in catalog.predicates
        ),
    )
