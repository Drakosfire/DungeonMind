"""PostgreSQL and loopback HTTP proof for exact historical hydration."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, cast

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("uvicorn")
from dungeonmind_dnd.contracts.mechanics_resources import (
    DndMechanicsResourceEnvelope,
    DndMechanicsResourceRef,
)
from dungeonmind_dnd.integration.threat_mechanics_api import (
    ThreatMechanicsAccessBinding,
    create_threat_mechanics_app,
)
from tests.integration.test_postgres_review_publication import (
    PUBLISHED_REVISION_ID,
    WORLD_ID,
    _publish_descendant,
    _publish_exact_predecessor,
    _reader,
    _seed_parent,
)
from tests.unit.test_dnd_threat_mechanics import _resource

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "dungeonmind_dnd"
REQUEST_PATH = FIXTURES / "tripod-null-calf-threat-mechanics-request-v1.json"
CLIENT_PATH = (
    Path(__file__).resolve().parents[2] / "examples" / "dnd_threat_mechanics_client.py"
)
TOKEN = "sentinel-threat-mechanics-loopback-token"
HYDRATION_SHA256 = "166dfe01ad0e2f4b57de3c74cfd50160e34a29591957f85b4a786c9f2edd6e16"

pytestmark = pytest.mark.integration


class _CountingGraphRepository:
    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.get_revision_calls: list[tuple[str, str]] = []
        self.get_head_calls = 0

    def get_revision(self, world_id: str, revision_id: str):
        self.get_revision_calls.append((world_id, revision_id))
        return self.inner.get_revision(world_id, revision_id)

    def get_head(self, *_args: Any, **_kwargs: Any) -> None:
        self.get_head_calls += 1
        raise AssertionError("transport must not read current head")


class _CountingResolver:
    def __init__(self, envelope: DndMechanicsResourceEnvelope) -> None:
        self.envelope = envelope
        self.calls: list[DndMechanicsResourceRef] = []

    def resolve(self, resource_ref: DndMechanicsResourceRef):
        self.calls.append(resource_ref.model_copy(deep=True))
        return self.envelope.model_copy(deep=True)


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _wait_for_server(port: int) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return
        except OSError:
            time.sleep(0.05)
    raise AssertionError("loopback server did not start")


def test_postgres_historical_revision_survives_head_advance_and_client_replay(
    pg,
) -> None:
    import uvicorn

    _seed_parent(pg)
    _publish_exact_predecessor(pg)
    repository = _CountingGraphRepository(pg.world_graph)
    resolver = _CountingResolver(_resource())
    app = create_threat_mechanics_app(
        graph_repository=cast(Any, repository),
        graph_reader=_reader(),
        resource_resolver=resolver,
        access_binding=ThreatMechanicsAccessBinding.from_secret(WORLD_ID, TOKEN),
        readiness_probe=lambda: {"status": "ready"},
    )

    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="critical",
            lifespan="off",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        _wait_for_server(port)
        env = {
            **os.environ,
            "DUNGEONMIND_THREAT_MECHANICS_BEARER_TOKEN": TOKEN,
        }
        command = [
            sys.executable,
            str(CLIENT_PATH),
            "--base-url",
            f"http://127.0.0.1:{port}",
            "--request-path",
            str(REQUEST_PATH),
            "--verify-replay",
        ]
        first = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert first.returncode == 0, first.stderr
        assert TOKEN not in first.stdout
        assert PUBLISHED_REVISION_ID in first.stdout
        assert "mechbind:872167afbc6e6a6b242c6d93036767ab" in first.stdout
        assert HYDRATION_SHA256 in first.stdout

        _publish_descendant(pg, PUBLISHED_REVISION_ID)

        second = subprocess.run(
            [
                item
                for item in command
                if item != "--verify-replay"
            ],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert second.returncode == 0, second.stderr
        assert TOKEN not in second.stdout
        assert HYDRATION_SHA256 in second.stdout
    finally:
        server.should_exit = True
        thread.join(timeout=10)

    assert not thread.is_alive()
    assert repository.get_revision_calls == [
        (WORLD_ID, PUBLISHED_REVISION_ID),
        (WORLD_ID, PUBLISHED_REVISION_ID),
        (WORLD_ID, PUBLISHED_REVISION_ID),
    ]
    assert repository.get_head_calls == 0
    assert len(resolver.calls) == 3
