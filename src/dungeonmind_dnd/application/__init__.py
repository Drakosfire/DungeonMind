"""Pure, side-effect-free D&D profile application logic.

Includes the non-mutating B.2d create-or-connect planner; nothing here
appends, decides, or publishes.
"""

from .contribution_planning import plan_threat_candidate_contribution
from .contribution_review import build_threat_contribution_review_intent
from .threat_candidates import (
    builtin_threat_vocabulary_ref,
    load_builtin_threat_vocabulary,
    parse_threat_candidate_packet,
    render_threat_vocabulary_prompt,
    threat_candidate_json_schema,
    validate_threat_candidate_packet,
    vocabulary_sha256,
)
from .threat_mechanics import (
    derive_threat_mechanics_binding,
    derive_threat_mechanics_binding_id,
    hydrate_threat_mechanics,
)
from .threat_mechanics_transport import hydrate_threat_mechanics_request
from .world_object_mechanics import (
    derive_world_object_mechanics_binding,
    derive_world_object_mechanics_binding_id,
    hydrate_world_object_mechanics,
)
from .world_object_vocabulary import (
    builtin_world_object_vocabulary_ref,
    load_builtin_v3_descriptor,
    load_builtin_world_object_vocabulary,
)

__all__ = [
    "build_threat_contribution_review_intent",
    "builtin_threat_vocabulary_ref",
    "builtin_world_object_vocabulary_ref",
    "derive_threat_mechanics_binding",
    "derive_threat_mechanics_binding_id",
    "derive_world_object_mechanics_binding",
    "derive_world_object_mechanics_binding_id",
    "hydrate_threat_mechanics",
    "hydrate_threat_mechanics_request",
    "hydrate_world_object_mechanics",
    "load_builtin_threat_vocabulary",
    "load_builtin_v3_descriptor",
    "load_builtin_world_object_vocabulary",
    "parse_threat_candidate_packet",
    "plan_threat_candidate_contribution",
    "render_threat_vocabulary_prompt",
    "threat_candidate_json_schema",
    "validate_threat_candidate_packet",
    "vocabulary_sha256",
]
