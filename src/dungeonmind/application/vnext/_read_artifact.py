"""Private immutable parser for fully source-bound native read artifacts.

No repositories, source admission, global patches or runtime reflection. Every
primary record validates through the same Python-mode contracts as the ordinary
parser; shared mutable validation models never escape this function.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from json.encoder import encode_basestring
from typing import Annotated, Any

from pydantic import Field, TypeAdapter, ValidationError

from dungeonmind.contracts.vnext.domain import (
    Assertion,
    AssertionMetadata,
    Entity,
    EntityRefValue,
    LiteralValue,
    TermRefValue,
)
from dungeonmind.contracts.vnext.knowledge import IdentityAlias
from dungeonmind.contracts.vnext.source import EvidenceRefV3
from dungeonmind.domain.errors import PersistenceIntegrityError

from ._source_wire import _decode_source_wire
from .builder import (
    _build_parsed_knowledge_revision_from_records,
    _parse_alias,
    _parse_assertion_metadata,
    _parse_evidence,
    _parse_revision_identity,
)
from .frozen_json import canonical_json_text, freeze_json_value
from .model import ParsedKnowledgeRevision
from .records import (
    ParsedAssertion,
    ParsedAssertionMetadata,
    ParsedAssertionValue,
    ParsedEntity,
    ParsedEntityRefValue,
    ParsedEvidenceRef,
    ParsedIdentityAlias,
    ParsedLiteralValue,
    ParsedTermRefValue,
    StoredKnowledgeRevision,
)

_VALUE_ADAPTER = TypeAdapter(
    Annotated[EntityRefValue | LiteralValue | TermRefValue, Field(discriminator="kind")]
)


def decode_read_artifact(
    data: bytes,
    source: StoredKnowledgeRevision,
) -> ParsedKnowledgeRevision | None:
    """Verify, contract-validate, freeze and rebuild all indexes/digests from facts.

    Absence/version fallback belongs to the ordinary source parser. Malformed
    matching artifacts and invalid source facts fail closed as persistence errors.
    Full ordinary repository verification must precede this optional accelerator.
    """
    return _build_parsed_rows(
        source, lambda consume: _decode_source_wire(data, source, consume) is not None
    )


def parse_verified_source_rows(
    source: StoredKnowledgeRevision, rows: dict[str, Any],
    *, _verified_indexes: Mapping[str, Mapping] | None = None,
) -> ParsedKnowledgeRevision | None:
    """Consume a request-owned decoded payload already bound by the source verifier."""
    if set(rows) != {"entities", "assertions", "aliases", "evidence"} or any(
        type(table) is not list for table in rows.values()
    ):
        return None

    def feed(consume: _ConsumeRow) -> bool:
        metadata_pool: dict[str, Any] = {}
        value_pool: dict[str, Any] = {}
        for key, table in rows.items():
            for row in table:
                if type(row) is not dict:
                    raise ValueError("expected native source object")
                if key == "assertions":
                    # The verifier supplies only built-in JSON values. Their repr
                    # preserves scalar types and signed zero. Different key order
                    # may miss the pool, but cannot conflate different values.
                    meta, value = row["metadata"], row["value"]
                    row["metadata"] = metadata_pool.setdefault(repr(meta), meta)
                    row["value"] = value_pool.setdefault(repr(value), value)
                consume(key, row, False, False)
        # The repository hands off ownership for this one parse. Release the
        # mutable graph before building indexes over the frozen records.
        rows.clear()
        return True

    return _build_parsed_rows(source, feed, _verified_indexes=_verified_indexes)


_ConsumeRow = Callable[[str, dict[str, Any], bool, bool], None]


def _build_parsed_rows(
    source: StoredKnowledgeRevision, feed: Callable[[_ConsumeRow], bool],
    *, _verified_indexes: Mapping[str, Mapping] | None = None,
) -> ParsedKnowledgeRevision | None:
    try:
        entities: list[ParsedEntity] = []
        aliases: list[ParsedIdentityAlias] = []
        evidence: list[ParsedEvidenceRef] = []
        metadata: dict[int, tuple[AssertionMetadata, ParsedAssertionMetadata]] = {}
        values: dict[
            int, tuple[EntityRefValue | LiteralValue | TermRefValue, ParsedAssertionValue]
        ] = {}
        assertions: list[ParsedAssertion] = []

        def consume(
            key: str, row: dict[str, Any], last_value: bool, last_metadata: bool
        ) -> None:
            if key == "entities":
                entities.append(ParsedEntity(Entity.model_validate(row).entity_id))
            elif key == "aliases":
                aliases.append(_parse_alias(IdentityAlias.model_validate(row)))
            elif key == "evidence":
                evidence.append(_parse_evidence(EvidenceRefV3.model_validate(row)))
            else:
                # Pooled raw JSON objects stay alive in payload throughout this call.
                # Their identity follows exact canonical bytes, never Python equality.
                meta_key = id(row["metadata"])
                if meta_key not in metadata:
                    public_meta = AssertionMetadata.model_validate(row["metadata"])
                    metadata[meta_key] = (
                        public_meta,
                        _parse_assertion_metadata(public_meta, assertion_id=row["assertion_id"]),
                    )
                value_key = id(row["value"])
                if value_key not in values:
                    public_value = _VALUE_ADAPTER.validate_python(row["value"])
                    if isinstance(public_value, EntityRefValue):
                        frozen_value: ParsedAssertionValue = ParsedEntityRefValue(
                            public_value.entity_id
                        )
                    elif isinstance(public_value, TermRefValue):
                        frozen_value = ParsedTermRefValue(public_value.term)
                    else:
                        frozen_value = ParsedLiteralValue(
                            freeze_json_value(public_value.value),
                            (
                                encode_basestring(public_value.value)
                                if isinstance(public_value.value, str)
                                else canonical_json_text(public_value.value)
                            ),
                        )
                    values[value_key] = (public_value, frozen_value)
                public_meta, frozen_meta = metadata[meta_key]
                public_value, frozen_value = values[value_key]
                validated = Assertion.model_validate(
                    {**row, "metadata": public_meta, "value": public_value}
                )
                assertions.append(
                    ParsedAssertion(
                        validated.assertion_id,
                        validated.subject_entity_id,
                        validated.predicate,
                        frozen_value,
                        frozen_meta,
                    )
                )
                # Frozen records remain in assertions; mutable public models are
                # useful only until this exact source chunk's last assertion use.
                if last_value:
                    del values[value_key]
                if last_metadata:
                    del metadata[meta_key]

        # Consume the proof's exact rows into local immutable records rather than
        # retaining a second whole mutable graph. Only a completed proof can
        # proceed to structural validation and return a parsed result.
        if not feed(consume):
            return None
        metadata.clear()
        values.clear()
        return _build_parsed_knowledge_revision_from_records(
            _parse_revision_identity(source.revision),
            entities=entities,
            assertions=assertions,
            aliases=aliases,
            evidence=evidence,
            _stream_digest=True,
            _verified_indexes=_verified_indexes,
        )
    except (ValidationError, TypeError, ValueError, KeyError) as exc:
        raise PersistenceIntegrityError(
            f"native read artifact contract validation failed: {exc}"
        ) from exc
