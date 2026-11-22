"""Context-bound preview of admitted native UTF-8 source evidence."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager, suppress
from dataclasses import dataclass, replace
from functools import partial
from threading import Lock
from typing import Any, Generic, TypeVar, cast

from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext.domain import DomainContractDescriptor, DomainContractRef
from dungeonmind.contracts.vnext.knowledge import KnowledgeRevision
from dungeonmind.contracts.vnext.native_source import (
    NativeTextSourceAccessV1,
    NativeTextSourceOriginV1,
)
from dungeonmind.contracts.vnext.source import SourceArtifactV3, SourceRevisionV2
from dungeonmind.domain.canonical import canonical_json, canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError, PersistenceUnavailableError

from ._read_artifact import decode_read_artifact, parse_verified_source_rows
from .admission import _contract_visibility_visible
from .builder import (
    _build_parsed_knowledge_revision_from_records,
    build_parsed_knowledge_revision,
)
from .errors import KnowledgeReadContextIntegrityError, NativeTextSourceAccessIntegrityError
from .frozen_json import FrozenDict
from .materialization import NATIVE_VNEXT_GRAPH_SCHEMA, decode_native_graph_payload
from .model import ParsedKnowledgeRevision
from .ports import NativeSourceEvidenceRepository, NativeTextSourceView, StoredNativeTextSource
from .records import (
    ParsedDomainContractRef,
    ParsedEvidenceRef,
    ParsedKnowledgeRevisionIdentity,
    ParsedSemanticProfileRef,
    StoredKnowledgeRevision,
)

_EVICTED_RECORD_MAX_PAYLOAD_BYTES = 8_000_000


@dataclass(frozen=True, slots=True)
class NativeTextSourceMembership:
    """Verified evidence for one revision, with no structural Graph indexes."""

    identity: ParsedKnowledgeRevisionIdentity
    evidence_by_id: FrozenDict[str, ParsedEvidenceRef]

    @property
    def domain_contract_ref(self) -> ParsedDomainContractRef:
        return self.identity.domain_contract_ref

    @property
    def semantic_profile_ref(self) -> ParsedSemanticProfileRef:
        return self.identity.semantic_profile_ref

    def get_evidence(self, evidence_ref_id: str) -> ParsedEvidenceRef | None:
        return self.evidence_by_id.get(evidence_ref_id)


_MembershipT = TypeVar(
    "_MembershipT", bound=ParsedKnowledgeRevision | NativeTextSourceMembership, covariant=True,
)


@dataclass(frozen=True, slots=True)
class NativeTextSourceAccessContext(Generic[_MembershipT]):
    """Exact child membership, pinned source epoch and immutable visibility inputs."""

    space_id: str
    revision_id: str
    parsed: _MembershipT
    source_view: NativeTextSourceView
    audience_labels: frozenset[str]
    declared_visibility_labels: frozenset[str]
    source_annotation_schemas: frozenset[str]


class NativeParsedRevisionCache:
    """Keep one immutable parsed graph for repeated reads of a verified revision."""

    def __init__(
        self,
        *,
        retain_evicted_records: bool = False,
        max_evicted_payload_bytes: int = _EVICTED_RECORD_MAX_PAYLOAD_BYTES,
    ) -> None:
        if type(max_evicted_payload_bytes) is not int or max_evicted_payload_bytes < 1:
            raise ValueError("max_evicted_payload_bytes must be a positive integer")
        self._max_evicted_payload_bytes = max_evicted_payload_bytes
        self._lock = Lock()
        self._retain_evicted_records = retain_evicted_records
        self._evicted_records: tuple[
            tuple[str, str, str], Callable[[], ParsedKnowledgeRevision]
        ] | None = None
        self._entry: tuple[tuple[str, str, str], ParsedKnowledgeRevision] | None = None

    def _has_parsed_pin(self, space_id: str, revision_id: str) -> bool:
        """Routing hint only. A cache hit still requires ordinary revision verification."""
        with self._lock:
            if self._entry is None:
                return False
            parsed = self._entry[1]
            return (parsed.space_id, parsed.revision_id) == (space_id, revision_id)

    def parse(self, stored: StoredKnowledgeRevision) -> ParsedKnowledgeRevision:
        return self._parse_using(stored, lambda: _parse_revision(stored))

    def _parse_using(
        self,
        stored: StoredKnowledgeRevision,
        load: Callable[[], ParsedKnowledgeRevision],
    ) -> ParsedKnowledgeRevision:
        # Snapshot representation rather than retaining a mutable envelope model.
        # Equal-instant offsets and bool/int JSON must not collapse into one key.
        key = (
            canonical_json(stored.revision.model_dump(mode="json")),
            stored.graph_payload_sha256,
            stored._payload_json,
        )
        with self._lock:
            if self._entry is not None and self._entry[0] == key:
                return self._entry[1]
            archived = self._evicted_records
            parsed = archived[1]() if archived is not None and archived[0] == key else load()
            if self._retain_evicted_records and self._entry is not None:
                previous_key, previous = self._entry
                if len(previous_key[2].encode("utf-8")) <= self._max_evicted_payload_bytes:
                    # Keep immutable facts only. Indexes and digest will be rebuilt.
                    self._evicted_records = (
                        previous_key,
                        partial(
                            _build_parsed_knowledge_revision_from_records,
                            previous.identity,
                            entities=previous.entities_by_id,
                            assertions=previous.assertions_by_id,
                            aliases=previous.aliases_by_id,
                            evidence=previous.evidence_by_id,
                            _stream_digest=True,
                            _reuse_frozen_records=True,
                        ),
                    )
                else:
                    self._evicted_records = None
            self._entry = (key, parsed)
            return parsed


def _parse_verified_revision(
    repository: NativeSourceEvidenceRepository,
    stored: StoredKnowledgeRevision,
) -> ParsedKnowledgeRevision:
    # Optional structural capability: existing repositories and locked views need
    # no new method or PostgreSQL dependency. Readers return current-version rows
    # only; absent/unsupported stored versions return None. A returned body that
    # claims another version violates that binding. No read generates artifacts.
    reader = getattr(repository, "get_native_read_artifact", None)
    if callable(reader):
        body = reader(stored)
        if body is not None:
            if not isinstance(body, bytes):
                raise PersistenceIntegrityError("artifact reader returned a non-byte body")
            parsed = decode_read_artifact(body, stored)
            if parsed is None:
                raise PersistenceIntegrityError("current artifact row/body format mismatch")
            return parsed
    return _parse_revision(stored)


def _parse_revision(stored: StoredKnowledgeRevision) -> ParsedKnowledgeRevision:
    return build_parsed_knowledge_revision(
        revision=stored.revision,
        decoded_content=decode_native_graph_payload(stored.graph_payload),
    )


def open_native_text_source_access_context(
    *,
    repository: NativeSourceEvidenceRepository,
    space_id: str,
    revision_id: str,
    domain_contract: (
        DomainContractDescriptor
        | Callable[[DomainContractRef, SemanticProfileRef], DomainContractDescriptor]
    ),
    audience_labels: Sequence[str] = (),
    parsed_cache: NativeParsedRevisionCache | None = None,
    prefer_verified_source_rows: bool = False,
) -> NativeTextSourceAccessContext[ParsedKnowledgeRevision]:
    """Pin one exact native revision and one coherent source-authority epoch.

    A descriptor resolver receives both descriptor references from the loaded revision.
    Both descriptor forms undergo the same pin validation.
    """
    if not space_id.strip() or not revision_id.strip():
        raise KnowledgeReadContextIntegrityError("native source context identity is blank")
    read_rows = getattr(repository, "get_revision_for_native_read", None)
    if prefer_verified_source_rows and callable(read_rows):
        read_verified = cast(
            Callable[
                [str, str],
                tuple[StoredKnowledgeRevision | None, Callable[[], dict[str, Any]] | None],
            ],
            read_rows,
        )
        stored, load_rows = read_verified(space_id, revision_id)
    else:
        stored = repository.get_revision(space_id, revision_id)
        load_rows = None
    if stored is None:
        raise KnowledgeReadContextIntegrityError("native source context revision is missing")
    domain_snapshot = _verified_source_domain(stored.revision, domain_contract)

    def load_parsed() -> ParsedKnowledgeRevision:
        if load_rows is not None:
            take = getattr(repository, "_take_published_parse", None)
            if callable(take):
                published_parse = take(stored)
                if isinstance(published_parse, ParsedKnowledgeRevision):
                    return published_parse
            parsed_rows = parse_verified_source_rows(stored, load_rows())
            if parsed_rows is not None:
                return parsed_rows
        return _parse_verified_revision(repository, stored)

    parsed = (
        load_parsed() if parsed_cache is None else parsed_cache._parse_using(stored, load_parsed)
    )
    view = repository.open_native_source_view(space_id)
    return NativeTextSourceAccessContext(
        space_id=space_id,
        revision_id=revision_id,
        parsed=parsed,
        source_view=view,
        audience_labels=frozenset(audience_labels),
        declared_visibility_labels=frozenset(domain_snapshot.visibility_labels),
        source_annotation_schemas=frozenset(domain_snapshot.source_annotation_schemas),
    )


def _verified_source_domain(
    revision: KnowledgeRevision,
    domain_contract: (
        DomainContractDescriptor
        | Callable[[DomainContractRef, SemanticProfileRef], DomainContractDescriptor]
    ),
) -> DomainContractDescriptor:
    if revision.graph_schema != NATIVE_VNEXT_GRAPH_SCHEMA:
        raise KnowledgeReadContextIntegrityError("native source context is not a native revision")
    if callable(domain_contract):
        domain_contract = domain_contract(
            revision.domain_contract_ref, revision.semantic_profile_ref
        )
    domain_snapshot = DomainContractDescriptor.model_validate(
        domain_contract.model_dump(mode="json")
    )
    if (
        domain_snapshot.domain_id != revision.domain_contract_ref.domain_id
        or domain_snapshot.domain_revision != revision.domain_contract_ref.domain_revision
        or canonical_sha256(domain_snapshot.model_dump(mode="json"))
        != revision.domain_contract_ref.descriptor_sha256
    ):
        raise KnowledgeReadContextIntegrityError("native source context domain pin mismatch")
    return domain_snapshot


def refresh_native_text_source_access_context(
    *,
    repository: NativeSourceEvidenceRepository,
    context: NativeTextSourceAccessContext[_MembershipT],
) -> NativeTextSourceAccessContext[_MembershipT]:
    """Refresh source authority without reloading immutable Graph membership.

    The repository must be the authority that opened the original context. The
    exact parsed revision and its audience/domain inputs remain pinned; only
    the source view advances. Body reads still perform normal admission checks.
    """
    _validate_refresh_identity(context)
    view = repository.open_native_source_view(context.space_id)
    return _with_refreshed_view(context, view)


@contextmanager
def refresh_native_text_source_access_scope(
    *,
    repository: NativeSourceEvidenceRepository,
    context: NativeTextSourceAccessContext[_MembershipT],
) -> Iterator[NativeTextSourceAccessContext[_MembershipT]]:
    """Refresh one exact read while allowing its owner to share a read connection."""
    _validate_refresh_identity(context)
    open_scope = getattr(repository, "open_native_source_read_scope", None)
    if open_scope is None:
        yield _with_refreshed_view(context, repository.open_native_source_view(context.space_id))
        return
    with open_scope(context.space_id) as view:
        yield _with_refreshed_view(context, view)


def _validate_refresh_identity(context: NativeTextSourceAccessContext) -> None:
    identity = context.parsed.identity
    if (
        not context.space_id.strip()
        or not context.revision_id.strip()
        or identity.space_id != context.space_id
        or identity.revision_id != context.revision_id
        or identity.graph_schema != NATIVE_VNEXT_GRAPH_SCHEMA
    ):
        raise KnowledgeReadContextIntegrityError("native source context identity mismatch")


def _with_refreshed_view(
    context: NativeTextSourceAccessContext[_MembershipT], view: NativeTextSourceView,
) -> NativeTextSourceAccessContext[_MembershipT]:
    if view.epoch < context.source_view.epoch:
        raise KnowledgeReadContextIntegrityError("native source authority epoch moved backwards")
    return replace(context, source_view=view)


@dataclass(frozen=True, slots=True)
class NativeTextSourceMetadata:
    """Authorized navigation metadata, not a body/span verification receipt."""

    source_artifact: SourceArtifactV3
    source_revision: SourceRevisionV2
    evidence_ref_ids: tuple[str, ...]
    origin: NativeTextSourceOriginV1 | None


@dataclass(frozen=True, slots=True)
class NativeTextSourceCatalog:
    """All eligible metadata in one pinned source context, without reading bodies."""

    space_id: str
    revision_id: str
    source_authority_epoch: int
    sources: tuple[NativeTextSourceMetadata, ...]
    complete: bool


def _eligible_evidence(
    context: NativeTextSourceAccessContext,
    evidence: ParsedEvidenceRef,
) -> bool:
    return (
        evidence.can_open_source
        and evidence.can_highlight_span
        and evidence.source_revision_id is not None
        and evidence.source_span_ref_id is not None
        and all(
            item.schema_term in context.source_annotation_schemas
            for item in evidence.domain_metadata
        )
    )


def _metadata_allowed(
    context: NativeTextSourceAccessContext,
    evidence: ParsedEvidenceRef,
    artifact: SourceArtifactV3,
    revision: SourceRevisionV2,
) -> bool:
    """One owner for the shared metadata identity and access decision."""
    if artifact.source_artifact_id != evidence.source_artifact_id:
        raise NativeTextSourceAccessIntegrityError("artifact identity mismatch")
    if artifact.status != "active" or artifact.current_revision_id != revision.source_revision_id:
        return False
    if revision.source_artifact_id != artifact.source_artifact_id:
        raise NativeTextSourceAccessIntegrityError("revision artifact binding mismatch")
    if revision.source_revision_id != evidence.source_revision_id:
        raise NativeTextSourceAccessIntegrityError("revision identity mismatch")
    if revision.body_storage != "dm_native_utf8_body_v1":
        raise NativeTextSourceAccessIntegrityError("body storage kind mismatch")
    return _contract_visibility_visible(
        artifact,
        audience=context.audience_labels,
        declared_labels=context.declared_visibility_labels,
    ) and all(
        item.schema_term in context.source_annotation_schemas for item in artifact.domain_metadata
    )


def list_admitted_native_text_sources(
    context: NativeTextSourceAccessContext,
    *,
    evidence_ref_ids: Sequence[str] | None = None,
) -> NativeTextSourceCatalog:
    """Discover authorized metadata; selected reads still verify bytes and proofs.

    Missing metadata yields partial discovery. Visibility exclusions do not disclose
    the excluded source or make an authorized audience's catalogue partial.
    """
    pairs = {}
    evidence_by_id = context.parsed.evidence_by_id
    candidates = (
        evidence_by_id.values()
        if evidence_ref_ids is None
        else (evidence_by_id.get(identity) for identity in dict.fromkeys(evidence_ref_ids))
    )
    for evidence in candidates:
        if evidence is not None and _eligible_evidence(context, evidence):
            pairs.setdefault((evidence.source_artifact_id, evidence.source_revision_id), []).append(
                evidence
            )
    try:
        snapshot = context.source_view.get_native_metadata_snapshot(
            artifact_ids=sorted({pair[0] for pair in pairs}),
            revision_ids=sorted({pair[1] for pair in pairs}),
        )
        complete, sources = True, []
        for (artifact_id, revision_id), evidence in sorted(pairs.items()):
            artifact, revision = (
                snapshot.provenance.get_artifact(artifact_id),
                snapshot.provenance.get_revision(revision_id),
            )
            if artifact is None or revision is None:
                complete = False
                continue
            allowed = tuple(
                sorted(
                    row.evidence_ref_id
                    for row in evidence
                    if _metadata_allowed(context, row, artifact, revision)
                )
            )
            if allowed:
                sources.append(
                    NativeTextSourceMetadata(
                        source_artifact=artifact.model_copy(deep=True),
                        source_revision=revision.model_copy(deep=True),
                        evidence_ref_ids=allowed,
                        origin=snapshot.get_origin(artifact_id, revision_id),
                    )
                )
    except PersistenceUnavailableError:
        raise
    except PersistenceIntegrityError as exc:
        raise NativeTextSourceAccessIntegrityError("source metadata integrity failed") from exc
    return NativeTextSourceCatalog(
        space_id=context.space_id,
        revision_id=context.revision_id,
        source_authority_epoch=context.source_view.epoch,
        sources=tuple(sources),
        complete=complete,
    )


def _unavailable() -> NativeTextSourceAccessV1:
    return NativeTextSourceAccessV1(status="unavailable")


def open_admitted_native_text(
    context: NativeTextSourceAccessContext,
    evidence_ref_id: str,
) -> NativeTextSourceAccessV1:
    """Return exact verified body bytes only through evidence in the pinned child."""
    if not isinstance(evidence_ref_id, str) or not evidence_ref_id.strip():
        return _unavailable()
    parsed = context.parsed
    evidence = parsed.get_evidence(evidence_ref_id)
    if evidence is None:
        return _unavailable()
    if not _eligible_evidence(context, evidence):
        return _unavailable()

    try:
        source = context.source_view.get_native_text_source(
            source_artifact_id=evidence.source_artifact_id,
            # _eligible_evidence established both frozen fields are non-None.
            source_revision_id=cast(str, evidence.source_revision_id),
            span_id=cast(str, evidence.source_span_ref_id),
        )
    except PersistenceUnavailableError:
        raise
    except PersistenceIntegrityError as exc:
        raise NativeTextSourceAccessIntegrityError("source record integrity failed") from exc
    return _verify_opened_source(context, evidence, source)


def open_admitted_native_text_batch(
    context: NativeTextSourceAccessContext,
    evidence_ref_ids: Sequence[str],
) -> tuple[NativeTextSourceAccessV1, ...]:
    """Open evidence in caller order using one pinned source view."""
    load = getattr(context.source_view, "get_native_text_sources", None)
    if load is None:
        return tuple(open_admitted_native_text(context, item) for item in evidence_ref_ids)

    return _open_admitted_native_text_batch(context, evidence_ref_ids, load)


def open_first_admitted_native_text_by_group(
    context: NativeTextSourceAccessContext,
    evidence_groups: Sequence[Sequence[str]],
) -> Iterator[NativeTextSourceAccessV1]:
    """Yield the first available open in each ordered group, or an unavailable result.

    Discovery callers group evidence for the same source pair before opening.
    Batch only the first candidate per group. Later candidates remain lazy.
    """
    load = getattr(context.source_view, "get_native_text_sources_for_discovery", None)
    first_opens: tuple[NativeTextSourceAccessV1, ...] | None = None
    if callable(load):
        # A speculative open may fail ahead of an earlier group's fallback.
        # Let the ordinary opens determine which failure is observable.
        with suppress(Exception):
            first_opens = _open_admitted_native_text_batch(
                context, [group[0] if group else "" for group in evidence_groups], load
            )

    for index, group in enumerate(evidence_groups):
        opened = first_opens[index] if first_opens is not None else _unavailable()
        if opened.status != "available":
            start = 1 if first_opens is not None else 0
            for evidence_id in group[start:]:
                opened = open_admitted_native_text(context, evidence_id)
                if opened.status == "available":
                    break
        yield opened


def _open_admitted_native_text_batch(
    context: NativeTextSourceAccessContext,
    evidence_ref_ids: Sequence[str],
    load: Callable[[Sequence[tuple[str, str, str]]], Sequence[StoredNativeTextSource | None]],
) -> tuple[NativeTextSourceAccessV1, ...]:
    results = [_unavailable() for _ in evidence_ref_ids]
    eligible = []
    for index, evidence_id in enumerate(evidence_ref_ids):
        if not isinstance(evidence_id, str) or not evidence_id.strip():
            continue
        evidence = context.parsed.get_evidence(evidence_id)
        if evidence is not None and _eligible_evidence(context, evidence):
            eligible.append((index, evidence))
    if not eligible:
        return tuple(results)

    try:
        sources = load(tuple(
            (
                evidence.source_artifact_id,
                cast(str, evidence.source_revision_id),
                cast(str, evidence.source_span_ref_id),
            )
            for _, evidence in eligible
        ))
    except PersistenceIntegrityError as exc:
        raise NativeTextSourceAccessIntegrityError("source record integrity failed") from exc
    verified_bodies: dict[int, tuple[str, str]] = {}
    for (index, evidence), source in zip(eligible, sources, strict=True):
        results[index] = _verify_opened_source(context, evidence, source, verified_bodies)
    return tuple(results)


def _verify_opened_source(
    context: NativeTextSourceAccessContext,
    evidence: ParsedEvidenceRef,
    source: StoredNativeTextSource | None,
    verified_bodies: dict[int, tuple[str, str]] | None = None,
) -> NativeTextSourceAccessV1:
    if source is None:
        return _unavailable()

    artifact = source.source_artifact
    revision = source.source_revision
    proof = source.span_proof
    if not _metadata_allowed(context, evidence, artifact, revision):
        return _unavailable()
    if proof.source_revision_id != revision.source_revision_id:
        raise NativeTextSourceAccessIntegrityError("span revision binding mismatch")
    if proof.evidence_ref_id != evidence.evidence_ref_id:
        raise NativeTextSourceAccessIntegrityError("span evidence binding mismatch")
    if proof.span_id != evidence.source_span_ref_id:
        raise NativeTextSourceAccessIntegrityError("span identity mismatch")

    body = source.body_bytes
    cached_body = None if verified_bodies is None else verified_bodies.get(id(body))
    try:
        if cached_body is None:
            body_digest = hashlib.sha256(body).hexdigest()
            body_text = body.decode("utf-8", errors="strict")
            if verified_bodies is not None:
                verified_bodies[id(body)] = (body_digest, body_text)
        else:
            body_digest, body_text = cached_body
        if body_digest != revision.content_sha256:
            raise NativeTextSourceAccessIntegrityError("body digest mismatch")
        if proof.end_byte > len(body):
            raise NativeTextSourceAccessIntegrityError("span exceeds body bounds")
        selected = body[proof.start_byte : proof.end_byte]
        selected.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise NativeTextSourceAccessIntegrityError(
            "stored body or span is not valid UTF-8"
        ) from exc
    if hashlib.sha256(selected).hexdigest() != proof.slice_sha256:
        raise NativeTextSourceAccessIntegrityError("span digest mismatch")

    return NativeTextSourceAccessV1(
        status="available",
        evidence_ref_id=evidence.evidence_ref_id,
        source_artifact_id=artifact.source_artifact_id,
        source_revision_id=revision.source_revision_id,
        body_sha256=body_digest,
        body_text=body_text,
        span_start_byte=proof.start_byte,
        span_end_byte=proof.end_byte,
        span_sha256=proof.slice_sha256,
        source_authority_epoch=source.authority_epoch,
    )
