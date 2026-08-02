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

__all__ = [
    "build_threat_contribution_review_intent",
    "builtin_threat_vocabulary_ref",
    "load_builtin_threat_vocabulary",
    "parse_threat_candidate_packet",
    "plan_threat_candidate_contribution",
    "render_threat_vocabulary_prompt",
    "threat_candidate_json_schema",
    "validate_threat_candidate_packet",
    "vocabulary_sha256",
]
