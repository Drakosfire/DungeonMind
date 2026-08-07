"""Transport-neutral exact-revision Threat mechanics service proofs."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest

from dungeonmind.contracts.graph import StoredGraphRevision
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.revision_ids import compute_revision_id
from dungeonmind_dnd.application.threat_mechanics_transport import (
    DndThreatMechanicsTransportError,
    hydrate_threat_mechanics_request,
)
from dungeonmind_dnd.contracts.mechanics_resources import (
    DndMechanicsResourceEnvelope,
    DndMechanicsResourceRef,
)
from dungeonmind_dnd.contracts.mechanics_transport import (
    DndThreatMechanicsHydrationRequest,
)
from tests.unit.test_dnd_threat_mechanics import (
    _reader,
    _resource,
    _resource_ref,
    _stored_revision,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "dungeonmind_dnd"
REQUEST_FIXTURE = FIXTURES / "tripod-null-calf-threat-mechanics-request-v1.json"
HYDRATION_FIXTURE = FIXTURES / "tripod-null-calf-threat-mechanics-hydration-v1.json"
HYDRATION_SHA256 = "166dfe01ad0e2f4b57de3c74cfd50160e34a29591957f85b4a786c9f2edd6e16"


def _request() -> DndThreatMechanicsHydrationRequest:
    return DndThreatMechanicsHydrationRequest.model_validate(
        json.loads(REQUEST_FIXTURE.read_text(encoding="utf-8"))
    )


class _Repository:
    def __init__(self, stored: StoredGraphRevision | None) -> None:
        self.stored = stored
        self.get_revision_calls: list[tuple[str, str]] = []
        self.get_head_calls = 0

    def get_revision(self, world_id: str, revision_id: str) -> StoredGraphRevision | None:
        self.get_revision_calls.append((world_id, revision_id))
        return None if self.stored is None else self.stored.model_copy(deep=True)

    def get_head(self, *_args: Any, **_kwargs: Any) -> None:
        self.get_head_calls += 1
        raise AssertionError("get_head must not be called")


class _Resolver:
    def __init__(self, envelope: DndMechanicsResourceEnvelope | None) -> None:
        self.envelope = envelope
        self.calls: list[DndMechanicsResourceRef] = []

    def resolve(
        self, resource_ref: DndMechanicsResourceRef
    ) -> DndMechanicsResourceEnvelope | None:
        self.calls.append(resource_ref.model_copy(deep=True))
        return None if self.envelope is None else self.envelope.model_copy(deep=True)


def _invoke(
    request: DndThreatMechanicsHydrationRequest,
    repository: _Repository,
    resolver: _Resolver,
):
    return hydrate_threat_mechanics_request(
        request,
        graph_repository=cast(Any, repository),
        graph_reader=_reader(),
        resource_resolver=resolver,
    )


def test_success_reads_exact_revision_once_and_resolves_once() -> None:
    repository = _Repository(_stored_revision())
    resolver = _Resolver(_resource())

    actual = _invoke(_request(), repository, resolver)
    expected = json.loads(HYDRATION_FIXTURE.read_text(encoding="utf-8"))

    assert repository.get_revision_calls == [
        ("world:synthetic-gatewatch", "rev:6e02bd224f6b5616534f10026c8b9679")
    ]
    assert repository.get_head_calls == 0
    assert len(resolver.calls) == 1
    assert actual.model_dump(mode="json") == expected
    assert canonical_sha256(actual.model_dump(mode="json")) == HYDRATION_SHA256


def test_missing_revision_is_closed_and_does_not_call_resolver() -> None:
    repository = _Repository(None)
    resolver = _Resolver(_resource())

    with pytest.raises(DndThreatMechanicsTransportError) as raised:
        _invoke(_request(), repository, resolver)

    assert raised.value.reason == "graph_revision_not_found"
    assert repository.get_revision_calls == [
        ("world:synthetic-gatewatch", "rev:6e02bd224f6b5616534f10026c8b9679")
    ]
    assert resolver.calls == []


def test_unexpected_repository_exception_is_internal_and_does_not_call_resolver() -> None:
    secret = "postgresql://user:secret@db.invalid/path"

    class _UnavailableRepository(_Repository):
        def get_revision(self, world_id: str, revision_id: str) -> None:
            self.get_revision_calls.append((world_id, revision_id))
            raise RuntimeError(secret)

    repository = _UnavailableRepository(_stored_revision())
    resolver = _Resolver(_resource())

    with pytest.raises(DndThreatMechanicsTransportError) as raised:
        _invoke(_request(), repository, resolver)

    assert raised.value.reason == "internal_error"
    assert secret not in str(raised.value)
    assert secret not in repr(raised.value)
    assert secret not in str(raised.value.details)
    assert resolver.calls == []


def test_valid_alternate_revision_is_rejected_before_resolver_access() -> None:
    original = _stored_revision()
    alternate_world = "world:alternate-gatewatch"
    alternate_payload = copy.deepcopy(original.graph_payload)
    alternate_payload["world_id"] = alternate_world
    alternate_payload_sha256 = canonical_sha256(alternate_payload)
    alternate_revision = original.revision.model_copy(
        update={
            "world_id": alternate_world,
            "revision_id": compute_revision_id(
                world_id=alternate_world,
                parent_revision_id=original.revision.parent_revision_id,
                operation_ids=original.revision.operation_ids,
                graph_schema=original.revision.graph_schema,
                graph_payload_sha256=alternate_payload_sha256,
            ),
            "graph_payload_sha256": alternate_payload_sha256,
        }
    )
    repository = _Repository(
        StoredGraphRevision(
            revision=alternate_revision,
            graph_payload=alternate_payload,
        )
    )
    resolver = _Resolver(_resource())

    with pytest.raises(DndThreatMechanicsTransportError) as raised:
        _invoke(_request(), repository, resolver)

    assert raised.value.reason == "threat_mechanics_binding_invalid"
    assert len(repository.get_revision_calls) == 1
    assert resolver.calls == []


@pytest.mark.parametrize(
    "mutation",
    [
        lambda revision: revision.model_copy(
            update={"revision_id": "rev:" + ("0" * 32)}
        ),
        lambda revision: revision.model_copy(update={"parent_revision_id": None}),
        lambda revision: revision.model_copy(
            update={"operation_ids": ["op:transport-forged"]}
        ),
    ],
)
def test_revision_mutations_fail_before_resolver_access(mutation) -> None:
    original = _stored_revision()
    forged = StoredGraphRevision(
        revision=mutation(original.revision),
        graph_payload=copy.deepcopy(original.graph_payload),
    )
    repository = _Repository(forged)
    resolver = _Resolver(_resource())

    with pytest.raises(DndThreatMechanicsTransportError) as raised:
        _invoke(_request(), repository, resolver)

    assert raised.value.reason == "threat_mechanics_binding_invalid"
    assert len(repository.get_revision_calls) == 1
    assert resolver.calls == []


def test_resolver_payload_isolated_from_service_response() -> None:
    repository = _Repository(_stored_revision())
    resource = _resource()
    resolver = _Resolver(resource)

    result = _invoke(_request(), repository, resolver)
    result.mechanics_payload["name"] = "client mutation"

    assert resource.mechanics_payload["name"] == "Tripod Null-Calf"
    assert resolver.calls[0] == _resource_ref()


def test_resource_miss_and_provider_failure_are_closed() -> None:
    repository = _Repository(_stored_revision())
    for resolver in (_Resolver(None),):
        with pytest.raises(DndThreatMechanicsTransportError) as raised:
            _invoke(_request(), repository, resolver)
        assert raised.value.reason == "mechanics_resource_not_found"
        assert len(resolver.calls) == 1

    class _ExplodingResolver(_Resolver):
        def resolve(self, _: DndMechanicsResourceRef) -> None:
            self.calls.append(_)
            raise RuntimeError("provider-url-sentinel")

    exploding = _ExplodingResolver(_resource())
    with pytest.raises(DndThreatMechanicsTransportError) as raised:
        _invoke(_request(), _Repository(_stored_revision()), exploding)
    assert raised.value.reason == "mechanics_resource_unavailable"
    assert len(exploding.calls) == 1
    assert "provider-url-sentinel" not in str(raised.value)


def test_resource_identity_and_payload_failures_are_integrity_failures() -> None:
    resource = _resource()
    changed_ref = resource.resource_ref.model_copy(update={"resource_id": "other:id"})
    changed = DndMechanicsResourceEnvelope(
        resource_ref=changed_ref,
        mechanics_payload=copy.deepcopy(resource.mechanics_payload),
    )
    resolver = _Resolver(changed)

    with pytest.raises(DndThreatMechanicsTransportError) as raised:
        _invoke(_request(), _Repository(_stored_revision()), resolver)

    assert raised.value.reason == "mechanics_resource_integrity_failure"
    assert len(resolver.calls) == 1
