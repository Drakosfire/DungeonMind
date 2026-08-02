"""Pure loaders, renderers, and validators for D&D Threat candidates.

Side-effect-free: package data is read with ``importlib.resources`` only
inside these functions (never at import time); no environment variables, no
network, no database, no graph repository, no registration, no LLM. The
rendered prompt fragment is generated deterministically from the catalog and
is never validation authority — the bundled, pin-verified Threat catalog is,
enforced by ``validate_threat_candidate_packet``. Raw payloads enter only
through ``parse_threat_candidate_packet``, which converts Pydantic failures
into sanitized package-owned errors: failures identify candidate IDs and
term IDs but never echo source prose, summaries, evidence locators, rejected
inputs, or local paths.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from importlib import resources
from typing import Any

from pydantic import ValidationError

from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor
from dungeonmind.domain.canonical import canonical_sha256

from ..contracts.candidates import (
    FORBIDDEN_THREAT_KIND,
    REQUIRED_THREAT_PREDICATE,
    DndCandidateEndpointRef,
    DndNodeCandidate,
    DndThreatCandidatePacket,
)
from ..contracts.vocabulary import (
    DndSemanticVocabulary,
    DndVocabularyRef,
    qualified_term_namespace,
)
from ..domain.errors import DndCandidateValidationError, DndVocabularyIntegrityError

_PROFILE_RESOURCE_DIR = "profiles"
_PROFILE_V2_RESOURCE = "dnd5e-v2.json"
_VOCABULARY_RESOURCE_DIR = "vocabularies"
_THREAT_VOCABULARY_RESOURCE = "threat-v1.json"


def _validation_messages(exc: ValidationError) -> list[str]:
    """Sanitized pydantic failure messages (never rejected input values)."""
    messages = [str(err.get("msg", "invalid")) for err in exc.errors()]
    return list(dict.fromkeys(messages))


def _read_resource_text(directory: str, name: str) -> str:
    return (
        resources.files("dungeonmind_dnd")
        .joinpath(directory)
        .joinpath(name)
        .read_text(encoding="utf-8")
    )


def _load_json_resource(directory: str, name: str, *, description: str) -> Any:
    try:
        raw = _read_resource_text(directory, name)
    except OSError as exc:
        # ``from None``: OS errors carry absolute paths in their messages.
        raise DndVocabularyIntegrityError(
            f"{description} could not be read",
            details={"reason": type(exc).__name__},
        ) from None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise DndVocabularyIntegrityError(
            f"{description} is not valid JSON",
            details={"reason": "JSONDecodeError"},
        ) from None


def _load_builtin_v2_descriptor() -> SemanticProfileDescriptor:
    data = _load_json_resource(
        _PROFILE_RESOURCE_DIR,
        _PROFILE_V2_RESOURCE,
        description="bundled dnd5e-v2 profile descriptor",
    )
    try:
        return SemanticProfileDescriptor.model_validate(data)
    except ValidationError as exc:
        messages = _validation_messages(exc)
        raise DndVocabularyIntegrityError(
            "bundled dnd5e-v2 profile descriptor failed validation: "
            + "; ".join(messages),
            details={"reason": "ValidationError", "messages": messages},
        ) from None


def _load_catalog() -> DndSemanticVocabulary:
    data = _load_json_resource(
        _VOCABULARY_RESOURCE_DIR,
        _THREAT_VOCABULARY_RESOURCE,
        description="bundled Threat vocabulary catalog",
    )
    try:
        return DndSemanticVocabulary.model_validate(data)
    except ValidationError as exc:
        messages = _validation_messages(exc)
        raise DndVocabularyIntegrityError(
            "bundled Threat vocabulary catalog failed validation: "
            + "; ".join(messages),
            details={"reason": "ValidationError", "messages": messages},
        ) from None


def _verify_vocabulary_against_descriptor(
    catalog: DndSemanticVocabulary,
    descriptor: SemanticProfileDescriptor,
) -> None:
    pinned = catalog.semantic_profile
    if (
        pinned.profile_id != descriptor.profile_id
        or pinned.profile_revision != descriptor.profile_revision
    ):
        raise DndVocabularyIntegrityError(
            "catalog profile pin does not match the bundled descriptor identity",
            details={
                "profile_id": pinned.profile_id,
                "profile_revision": pinned.profile_revision,
            },
        )
    digest = canonical_sha256(descriptor.model_dump(mode="json"))
    if digest != pinned.descriptor_sha256:
        raise DndVocabularyIntegrityError(
            "catalog profile pin digest does not match the bundled descriptor",
            details={
                "profile_id": pinned.profile_id,
                "profile_revision": pinned.profile_revision,
                "expected_sha256": pinned.descriptor_sha256,
                "actual_sha256": digest,
            },
        )
    namespaces = set(descriptor.term_namespaces)
    terms = [kind.term for kind in catalog.object_kinds]
    terms.extend(predicate.term for predicate in catalog.predicates)
    for predicate in catalog.predicates:
        terms.extend(predicate.subject_kinds)
        terms.extend(predicate.object_kinds)
    for term in terms:
        namespace = qualified_term_namespace(term)
        if namespace not in namespaces:
            raise DndVocabularyIntegrityError(
                "catalog term namespace is not admitted by the pinned profile",
                details={"term": term, "namespace": namespace},
            )


def vocabulary_sha256(vocabulary: DndSemanticVocabulary) -> str:
    """Content digest of a vocabulary catalog's canonical JSON form."""
    return canonical_sha256(vocabulary.model_dump(mode="json"))


def load_builtin_threat_vocabulary() -> DndSemanticVocabulary:
    """Load and pin-verify the bundled Threat vocabulary catalog."""
    descriptor = _load_builtin_v2_descriptor()
    catalog = _load_catalog()
    _verify_vocabulary_against_descriptor(catalog, descriptor)
    return catalog


def builtin_threat_vocabulary_ref() -> DndVocabularyRef:
    """Pinned ref (id + revision + digest) of the bundled Threat catalog."""
    catalog = load_builtin_threat_vocabulary()
    return DndVocabularyRef(
        vocabulary_id=catalog.vocabulary_id,
        vocabulary_revision=catalog.vocabulary_revision,
        catalog_sha256=vocabulary_sha256(catalog),
    )


def _inject_enum(
    schema: dict[str, Any], model_name: str, field_name: str, values: list[str]
) -> None:
    prop = schema["$defs"][model_name]["properties"][field_name]
    if "anyOf" in prop:
        for branch in prop["anyOf"]:
            if branch.get("type") == "string":
                branch["enum"] = values
    else:
        prop["enum"] = values


def threat_candidate_json_schema() -> dict[str, object]:
    """Deterministic JSON Schema for the packet contract, with the catalog's
    exact kind/predicate terms injected as enums for structured output."""
    catalog = load_builtin_threat_vocabulary()
    schema = DndThreatCandidatePacket.model_json_schema()
    kinds = sorted(kind.term for kind in catalog.object_kinds)
    predicates = sorted(predicate.term for predicate in catalog.predicates)
    _inject_enum(schema, "DndNodeCandidate", "kind", kinds)
    _inject_enum(schema, "DndRelationshipCandidate", "predicate", predicates)
    _inject_enum(schema, "DndCandidateEndpointRef", "expected_kind", kinds)
    return schema


def render_threat_vocabulary_prompt() -> str:
    """Deterministic controlled-vocabulary prompt fragment.

    Generated only from catalog data plus static contract rules; contains no
    campaign prose, no rulebook text, and no fixture content. The prompt is
    guidance for a producer — validation authority is always the catalog.
    """
    catalog = load_builtin_threat_vocabulary()
    lines: list[str] = [
        "You extract one structured D&D 5e Threat candidate packet from one "
        "source excerpt.",
        "",
        f"Semantic profile: {catalog.semantic_profile.profile_id} "
        f"revision {catalog.semantic_profile.profile_revision}",
        f"Vocabulary: {catalog.vocabulary_id} revision {catalog.vocabulary_revision}",
        "",
        "Allowed object kinds (exact terms; no others):",
    ]
    for kind in catalog.object_kinds:
        lines.append(f"- {kind.term} ({kind.label}): {kind.description}")
    lines.append("")
    lines.append(
        "Allowed relationship predicates (exact terms; subject -> object "
        "direction is mandatory):"
    )
    for predicate in catalog.predicates:
        subjects = " | ".join(predicate.subject_kinds)
        objects = " | ".join(predicate.object_kinds)
        lines.append(
            f"- {predicate.term} ({predicate.label}): {predicate.description}"
        )
        lines.append(f"  direction: {subjects} -> {objects}")
    lines.extend(
        [
            "",
            "Rules:",
            f"- Threat is always the {REQUIRED_THREAT_PREDICATE} relationship, "
            f"never an object kind; do not emit {FORBIDDEN_THREAT_KIND}.",
            "- Do not emit any kind or predicate outside the lists above, "
            "and no terms from any other namespace.",
            "- Candidate IDs are temporary (cand:...) and must never begin "
            "with obj: or rel:.",
            "- Reference an existing graph object only as existing_object_id "
            "with its expected_kind.",
            "- Every node and every relationship carries at least one evidence "
            "reference from the excerpt.",
            "- Do not emit properties, confidence scores, stable object IDs, "
            "merge decisions, or graph revision IDs.",
        ]
    )
    return "\n".join(lines) + "\n"


def _endpoint_kind(
    endpoint: DndCandidateEndpointRef,
    node_by_id: dict[str, DndNodeCandidate],
) -> str:
    if endpoint.candidate_id is not None:
        return node_by_id[endpoint.candidate_id].kind
    if endpoint.expected_kind is None:  # pragma: no cover — endpoint invariant
        raise DndCandidateValidationError(
            "existing object endpoint is missing expected_kind"
        )
    return endpoint.expected_kind


def parse_threat_candidate_packet(
    payload: Mapping[str, Any] | DndThreatCandidatePacket,
) -> DndThreatCandidatePacket:
    """Package-owned ingestion boundary for raw candidate payloads.

    Pydantic ``ValidationError`` is converted into a sanitized
    ``DndCandidateValidationError``: only validator message strings (which
    identify candidate IDs, term IDs, and evidence IDs) are carried forward —
    never raw ``errors()`` records, rejected input values, labels, summaries,
    or evidence locators. Candidate contracts additionally set
    ``hide_input_in_errors=True`` as defense in depth. Raw ``model_validate``
    remains available internally but is not the documented ingestion API.
    """
    if isinstance(payload, DndThreatCandidatePacket):
        return payload
    try:
        return DndThreatCandidatePacket.model_validate(payload)
    except ValidationError as exc:
        messages = _validation_messages(exc)
        raise DndCandidateValidationError(
            "candidate packet failed contract validation: " + "; ".join(messages),
            details={"reason": "ValidationError", "messages": messages},
        ) from None


def _require_authoritative_catalog(vocabulary: DndSemanticVocabulary) -> None:
    """Reject any injected catalog that is not the bundled authoritative
    Threat catalog: exact match on vocabulary ID, revision, pinned profile
    ref, and canonical digest."""
    bundled = load_builtin_threat_vocabulary()
    if (
        vocabulary.vocabulary_id == bundled.vocabulary_id
        and vocabulary.vocabulary_revision == bundled.vocabulary_revision
        and vocabulary.semantic_profile == bundled.semantic_profile
        and vocabulary_sha256(vocabulary) == vocabulary_sha256(bundled)
    ):
        return
    raise DndVocabularyIntegrityError(
        "injected vocabulary is not the bundled authoritative Threat catalog",
        details={
            "vocabulary_id": vocabulary.vocabulary_id,
            "vocabulary_revision": vocabulary.vocabulary_revision,
        },
    )


def validate_threat_candidate_packet(
    packet: DndThreatCandidatePacket,
    vocabulary: DndSemanticVocabulary | None = None,
) -> DndThreatCandidatePacket:
    """Validate a packet against the bundled, pin-verified Threat catalog:
    exact pins, term membership, predicate direction/domain/range. Returns
    the packet unchanged.

    The checked-in catalog is authoritative. An injected catalog is accepted
    only when it exactly matches the bundled identity (vocabulary ID,
    revision, pinned profile ref, canonical digest); any other catalog is
    rejected with ``DndVocabularyIntegrityError`` so a caller cannot widen
    the term inventory with its own internally consistent vocabulary.
    """
    if vocabulary is None:
        catalog = load_builtin_threat_vocabulary()
    else:
        _require_authoritative_catalog(vocabulary)
        catalog = vocabulary
    return _validate_against_catalog(packet, catalog)


def _validate_against_catalog(
    packet: DndThreatCandidatePacket,
    catalog: DndSemanticVocabulary,
) -> DndThreatCandidatePacket:
    """Catalog-dependent checks against one trusted catalog. Private seam so
    unit tests can inject alternate catalogs; the public validator always
    enforces the bundled authoritative identity first."""

    if packet.semantic_profile != catalog.semantic_profile:
        raise DndCandidateValidationError(
            "packet semantic profile ref does not equal the vocabulary's "
            "pinned profile",
            details={
                "profile_id": packet.semantic_profile.profile_id,
                "profile_revision": packet.semantic_profile.profile_revision,
            },
        )

    expected_ref = DndVocabularyRef(
        vocabulary_id=catalog.vocabulary_id,
        vocabulary_revision=catalog.vocabulary_revision,
        catalog_sha256=vocabulary_sha256(catalog),
    )
    if packet.vocabulary != expected_ref:
        raise DndCandidateValidationError(
            "packet vocabulary ref does not equal the loaded catalog identity",
            details={
                "vocabulary_id": packet.vocabulary.vocabulary_id,
                "vocabulary_revision": packet.vocabulary.vocabulary_revision,
                "expected_catalog_sha256": expected_ref.catalog_sha256,
                "actual_catalog_sha256": packet.vocabulary.catalog_sha256,
            },
        )

    kind_terms = {kind.term for kind in catalog.object_kinds}
    predicate_by_term = {predicate.term: predicate for predicate in catalog.predicates}
    namespaces = {
        qualified_term_namespace(term)
        for term in kind_terms | set(predicate_by_term)
    }
    node_by_id = {node.candidate_id: node for node in packet.nodes}

    def _require_catalog_namespace(term: str, *, candidate_id: str) -> None:
        namespace = qualified_term_namespace(term)
        if namespace not in namespaces:
            raise DndCandidateValidationError(
                "term uses a namespace outside the pinned catalog",
                details={
                    "candidate_id": candidate_id,
                    "term": term,
                    "namespace": namespace,
                },
            )

    for node in packet.nodes:
        _require_catalog_namespace(node.kind, candidate_id=node.candidate_id)
        if node.kind not in kind_terms:
            raise DndCandidateValidationError(
                "unknown object kind term for this vocabulary",
                details={"candidate_id": node.candidate_id, "term": node.kind},
            )

    for rel in packet.relationships:
        for endpoint in (rel.subject, rel.object):
            if endpoint.candidate_id is None:
                expected_kind = _endpoint_kind(endpoint, node_by_id)
                _require_catalog_namespace(
                    expected_kind, candidate_id=rel.candidate_id
                )
                if expected_kind not in kind_terms:
                    raise DndCandidateValidationError(
                        "unknown object kind term for this vocabulary",
                        details={
                            "candidate_id": rel.candidate_id,
                            "term": expected_kind,
                        },
                    )
        _require_catalog_namespace(rel.predicate, candidate_id=rel.candidate_id)
        predicate = predicate_by_term.get(rel.predicate)
        if predicate is None:
            raise DndCandidateValidationError(
                "unknown predicate term for this vocabulary",
                details={"candidate_id": rel.candidate_id, "term": rel.predicate},
            )
        subject_kind = _endpoint_kind(rel.subject, node_by_id)
        object_kind = _endpoint_kind(rel.object, node_by_id)
        if subject_kind not in predicate.subject_kinds:
            raise DndCandidateValidationError(
                "predicate direction violated: subject kind is outside the "
                "predicate domain",
                details={
                    "candidate_id": rel.candidate_id,
                    "predicate": rel.predicate,
                    "term": subject_kind,
                },
            )
        if object_kind not in predicate.object_kinds:
            raise DndCandidateValidationError(
                "predicate direction violated: object kind is outside the "
                "predicate range",
                details={
                    "candidate_id": rel.candidate_id,
                    "predicate": rel.predicate,
                    "term": object_kind,
                },
            )
    return packet
