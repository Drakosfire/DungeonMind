import pytest
from pydantic import ValidationError

from dungeonmind.application.world_campaign_ingest_context import (
    WorldCampaignMembershipNotFoundError,
    WorldGraphNotInitializedError,
    query_world_campaign_ingest_context,
)
from dungeonmind.contracts.world_campaign_ingest_context import (
    WorldCampaignIngestContextRequestV1,
    WorldCampaignIngestContextV1,
)
from dungeonmind.domain.errors import (
    CapabilityDeniedError,
    PersistenceIntegrityError,
    PersistenceUnavailableError,
)
from dungeonmind.service.publication_access import (
    PublicationAccessBinding,
    authorize_publication_world,
)


def _context(**changes):
    values = dict(
        world_id="world:synthetic", campaign_id="campaign:synthetic",
        head_revision_id="rev:synthetic", graph_schema="dm_union_graph_v6",
        graph_payload_sha256="a" * 64,
    )
    values.update(changes)
    return WorldCampaignIngestContextV1(**values)


def test_contract_accepts_only_membership_and_head_metadata() -> None:
    assert set(_context().model_dump()) == {
        "schema_version", "world_id", "campaign_id", "membership",
        "head_revision_id", "graph_schema", "graph_payload_sha256",
    }
    with pytest.raises(ValidationError):
        WorldCampaignIngestContextV1.model_validate({
            **_context().model_dump(), "graph_payload": {"prose": "synthetic"},
        })


@pytest.mark.parametrize("field", ["world_id", "campaign_id", "head_revision_id"])
def test_context_rejects_blank_or_padded_identity(field) -> None:
    with pytest.raises(ValidationError):
        _context(**{field: " padded "})


def test_application_rejects_adapter_scope_drift() -> None:
    class WrongScopeReader:
        def read_ingest_context(self, *, world_id, campaign_id):
            return _context(world_id="world:other")

    with pytest.raises(PersistenceIntegrityError):
        query_world_campaign_ingest_context(
            WorldCampaignIngestContextRequestV1(
                world_id="world:synthetic", campaign_id="campaign:synthetic"
            ),
            reader=WrongScopeReader(),
        )


def test_read_uses_existing_exact_world_credential() -> None:
    binding = PublicationAccessBinding.from_secret("world:synthetic", "synthetic-secret")
    authorize_publication_world(
        "world:synthetic", authorization_header="Bearer synthetic-secret", binding=binding
    )
    for world_id, header in (
        ("world:other", "Bearer synthetic-secret"),
        ("world:synthetic", None),
        ("world:synthetic", "Bearer incorrect"),
    ):
        with pytest.raises(CapabilityDeniedError):
            authorize_publication_world(world_id, authorization_header=header, binding=binding)


def _client(reader):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from dungeonmind.service.api import create_publication_app

    return TestClient(create_publication_app(
        review_repository=None, world_graph_repository=None, publication_repository=None,
        graph_reader=None, clock=None,
        access_binding=PublicationAccessBinding.from_secret("world:synthetic", "synthetic-secret"),
        readiness_probe=lambda: {"status": "ready"}, ingest_context_reader=reader,
    ))


def test_api_authorizes_before_read_and_returns_only_metadata() -> None:
    class CountingReader:
        calls = 0

        def read_ingest_context(self, *, world_id, campaign_id):
            self.calls += 1
            return _context(world_id=world_id, campaign_id=campaign_id)

    reader = CountingReader()
    client = _client(reader)
    url = "/v1/worlds/world:synthetic/campaigns/campaign:synthetic/ingest-context"
    headers = {"Authorization": "Bearer synthetic-secret"}
    for target, auth in (
        (url, {}), (url, {"Authorization": "Bearer incorrect"}),
        (url.replace("world:synthetic", "world:other"), headers),
    ):
        assert client.get(target, headers=auth).status_code == 403
    assert reader.calls == 0
    response = client.get(url, headers=headers)
    assert response.status_code == 200
    assert response.json() == _context().model_dump()
    assert response.headers["cache-control"] == "no-store"
    assert reader.calls == 1


@pytest.mark.parametrize("error,status,code", [
    (WorldCampaignMembershipNotFoundError(), 404, "world_campaign_membership_not_found"),
    (WorldGraphNotInitializedError(), 409, "world_graph_not_initialized"),
    (PersistenceUnavailableError("sentinel-private-connection"), 503, "persistence_unavailable"),
])
def test_api_fails_closed_on_reader_errors(error, status, code) -> None:
    class FailingReader:
        def read_ingest_context(self, **kwargs):
            raise error

    response = _client(FailingReader()).get(
        "/v1/worlds/world:synthetic/campaigns/campaign:synthetic/ingest-context",
        headers={"Authorization": "Bearer synthetic-secret"},
    )
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert "sentinel-private-connection" not in response.text
