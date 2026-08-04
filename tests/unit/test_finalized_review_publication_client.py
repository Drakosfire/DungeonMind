"""Contract tests for the dependency-free external publication client."""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

CLIENT_PATH = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "finalized_review_publication_client"
    / "client.py"
)
REQUEST_PATH = CLIENT_PATH.with_name("request.json")


def _client_module():
    spec = importlib.util.spec_from_file_location("publication_client", CLIENT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_client_has_only_standard_library_imports() -> None:
    tree = ast.parse(CLIENT_PATH.read_text())
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module.split(".")[0])
    assert "dungeonmind" not in imported
    assert "dungeonmind_dnd" not in imported
    assert "fastapi" not in imported
    assert "psycopg" not in imported
    assert "sqlalchemy" not in imported
    assert "pydantic" not in imported


def test_checked_in_request_is_exactly_the_three_field_wire_body() -> None:
    assert json.loads(REQUEST_PATH.read_text()) == {
        "schema_version": "dm_finalized_review_publication_request_v1",
        "world_id": "world:synthetic-gatewatch",
        "review_id": "review:cff0162637b428e634e8cccaa9958dc2",
    }


def test_client_validates_publication_identity_and_status() -> None:
    client = _client_module()
    valid = {
        "schema_version": "dm_finalized_review_publication_v1",
        "world_id": "world:test",
        "review_id": "review:test",
        "status": "published",
        "published_revision_id": "rev:test",
    }
    assert client._validate_publication(
        valid,
        world_id="world:test",
        review_id="review:test",
    ) == valid
    for key, value in (
        ("schema_version", "wrong"),
        ("world_id", "world:other"),
        ("review_id", "review:other"),
        ("status", "pending"),
        ("published_revision_id", ""),
    ):
        invalid = dict(valid)
        invalid[key] = value
        try:
            client._validate_publication(
                invalid,
                world_id="world:test",
                review_id="review:test",
            )
        except ValueError:
            pass
        else:
            raise AssertionError(f"{key} was not validated")


def test_unknown_error_is_a_temporary_failure_without_request_mutation(monkeypatch) -> None:
    client = _client_module()
    body = client._request_body("world:test", "review:test")
    captured: list[dict[str, str]] = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def close(self):
            return None

        def read(self):
            return json.dumps(
                {
                    "error": {
                        "code": "finalized_review_publication_outcome_unknown",
                        "message": (
                            "Publication outcome is unknown. "
                            "Retrying the same request is safe."
                        ),
                        "details": {"retry_safe": True},
                    }
                }
            ).encode()

    def fake_urlopen(request, timeout):
        captured.append(dict(body))
        raise client.HTTPError(
            request.full_url,
            503,
            "unknown",
            {},
            Response(),
        )

    monkeypatch.setattr(client, "urlopen", fake_urlopen)
    response, status = client._post("http://127.0.0.1:8001", body, "sentinel-token")
    assert response is None
    assert status == 75
    assert captured == [
        {
            "schema_version": "dm_finalized_review_publication_request_v1",
            "world_id": "world:test",
            "review_id": "review:test",
        }
    ]
    assert body == captured[0]


def test_missing_environment_token_is_not_accepted_as_a_cli_value() -> None:
    env = os.environ.copy()
    env.pop("DUNGEONMIND_PUBLICATION_BEARER_TOKEN", None)
    result = subprocess.run(
        [
            sys.executable,
            str(CLIENT_PATH),
            "--base-url",
            "http://127.0.0.1:8001",
            "--world-id",
            "world:test",
            "--review-id",
            "review:test",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "DUNGEONMIND_PUBLICATION_BEARER_TOKEN is required." in result.stderr
