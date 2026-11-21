"""Immutable scoped facts for selective search, complete entities and citations."""

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import TypeVar

from dungeonmind.application.vnext._read_artifact import _DecodedFacts
from dungeonmind.application.vnext.records import (
    ParsedAssertion,
    ParsedDomainContractRef,
    ParsedEntity,
    ParsedEntityRefValue,
    ParsedEvidenceRef,
    ParsedIdentityAlias,
    ParsedKnowledgeRevisionIdentity,
    ParsedSemanticProfileRef,
)
from dungeonmind.domain.errors import PersistenceIntegrityError

_T = TypeVar("_T")
_Postings = Mapping[tuple[str, str], tuple[str, ...]]


def _records(values: Sequence[_T], key: Callable[[_T], str]) -> Mapping[str, _T]:
    by_id = {key(value): value for value in values}
    if len(by_id) != len(values):
        raise PersistenceIntegrityError("selective query records have duplicate identities")
    return MappingProxyType(by_id)


def _freeze(groups: Mapping[str, list[_T]]) -> Mapping[str, tuple[_T, ...]]:
    return MappingProxyType({key: tuple(items) for key, items in groups.items()})


@dataclass(frozen=True, slots=True)
class _SelectiveQueryFacts:
    identity: ParsedKnowledgeRevisionIdentity
    _entities: Mapping[str, ParsedEntity]
    _assertions: Mapping[str, ParsedAssertion]
    _evidence: Mapping[str, ParsedEvidenceRef]
    assertion_evidence: Mapping[str, tuple[str, ...]]
    _subjects: Mapping[str, tuple[str, ...]]
    _outgoing: Mapping[str, tuple[str, ...]]
    _incoming: Mapping[str, tuple[str, ...]]
    _aliases: Mapping[str, tuple[ParsedIdentityAlias, ...]]
    _postings: _Postings

    @classmethod
    def from_decoded(
        cls,
        identity: ParsedKnowledgeRevisionIdentity,
        decoded: _DecodedFacts,
        postings: _Postings,
    ) -> "_SelectiveQueryFacts":
        entities = _records(decoded.entities, lambda value: value.entity_id)
        assertions = _records(decoded.assertions, lambda value: value.assertion_id)
        evidence = _records(decoded.evidence, lambda value: value.evidence_ref_id)
        aliases = _records(decoded.aliases, lambda value: value.alias_id)
        subjects: dict[str, list[str]] = defaultdict(list)
        outgoing: dict[str, list[str]] = defaultdict(list)
        incoming: dict[str, list[str]] = defaultdict(list)
        aliases_by_entity: dict[str, list[ParsedIdentityAlias]] = defaultdict(list)
        assertion_evidence: dict[str, tuple[str, ...]] = {}
        for key in sorted(assertions):
            assertion = assertions[key]
            subject = assertion.subject_entity_id
            evidence_ids = assertion.metadata.evidence_ref_ids
            if subject not in entities or any(item not in evidence for item in evidence_ids):
                raise PersistenceIntegrityError("selective assertion dependencies are missing")
            subjects[subject].append(key)
            assertion_evidence[key] = evidence_ids
            if isinstance(assertion.value, ParsedEntityRefValue):
                target = assertion.value.entity_id
                if target not in entities:
                    raise PersistenceIntegrityError("selective assertion target is missing")
                outgoing[subject].append(key)
                incoming[target].append(key)
        for key in sorted(aliases):
            alias = aliases[key]
            if alias.entity_id not in entities or any(
                item not in evidence for item in alias.evidence_ref_ids
            ):
                raise PersistenceIntegrityError("selective alias dependencies are missing")
            aliases_by_entity[alias.entity_id].append(alias)
        return cls(
            identity, entities, assertions, evidence, MappingProxyType(assertion_evidence),
            _freeze(subjects), _freeze(outgoing), _freeze(incoming), _freeze(aliases_by_entity),
            MappingProxyType(dict(postings)),
        )

    @property
    def space_id(self) -> str:
        return self.identity.space_id

    @property
    def revision_id(self) -> str:
        return self.identity.revision_id

    @property
    def domain_contract_ref(self) -> ParsedDomainContractRef:
        return self.identity.domain_contract_ref

    @property
    def semantic_profile_ref(self) -> ParsedSemanticProfileRef:
        return self.identity.semantic_profile_ref

    def get_entity(self, identity: str) -> ParsedEntity | None:
        return self._entities.get(identity)

    def get_assertion(self, identity: str) -> ParsedAssertion | None:
        return self._assertions.get(identity)

    def get_evidence(self, identity: str) -> ParsedEvidenceRef | None:
        return self._evidence.get(identity)

    def get_subject_assertion_ids(self, identity: str) -> tuple[str, ...]:
        return self._subjects.get(identity, ())

    def get_incoming_entity_ref_assertion_ids(self, identity: str) -> tuple[str, ...]:
        return self._incoming.get(identity, ())

    def get_outgoing_entity_ref_assertion_ids(self, identity: str) -> tuple[str, ...]:
        return self._outgoing.get(identity, ())

    def get_entity_aliases(self, identity: str) -> tuple[ParsedIdentityAlias, ...]:
        return self._aliases.get(identity, ())

    def lookup_predicate_assertions(self, key: str) -> tuple[str, ...]:
        return self._postings[("predicate", key)]

    def lookup_term_ref_assertions(self, key: str) -> tuple[str, ...]:
        return self._postings[("term", key)]

    def lookup_lexical_assertions(self, key: str) -> tuple[str, ...]:
        return self._postings[("lexical", key)]
