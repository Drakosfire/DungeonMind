"""Pure, side-effect-free D&D profile application logic."""

from .threat_candidates import (
    builtin_threat_vocabulary_ref,
    load_builtin_threat_vocabulary,
    render_threat_vocabulary_prompt,
    threat_candidate_json_schema,
    validate_threat_candidate_packet,
    vocabulary_sha256,
)

__all__ = [
    "builtin_threat_vocabulary_ref",
    "load_builtin_threat_vocabulary",
    "render_threat_vocabulary_prompt",
    "threat_candidate_json_schema",
    "validate_threat_candidate_packet",
    "vocabulary_sha256",
]
