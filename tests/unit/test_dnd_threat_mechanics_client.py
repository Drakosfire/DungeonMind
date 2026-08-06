"""Contract tests for the standard-library Threat mechanics client."""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

CLIENT_PATH = Path(__file__).resolve().parents[2] / "examples" / "dnd_threat_mechanics_client.py"
REQUEST_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures/dungeonmind_dnd/tripod-null-calf-threat-mechanics-request-v1.json"
)
HYDRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures/dungeonmind_dnd/tripod-null-calf-threat-mechanics-hydration-v1.json"
)


def _client_module():
    spec = importlib.util.spec_from_file_location("threat_mechanics_client", CLIENT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_client_uses_only_standard_library_imports() -> None:
    tree = ast.parse(CLIENT_PATH.read_text(encoding="utf-8"))
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
    assert "pydantic" not in imported


def test_checked_in_request_matches_the_canonical_fixture() -> None:
    client = _client_module()
    request = client._load_request(str(REQUEST_PATH))

    assert client._canonical_sha256(request) == (
        "a78a1648fae75937b5b775d6ef0d385ab620eace249a6b618334ab1868ae134e"
    )


def test_client_validates_hydration_identity_and_digest() -> None:
    client = _client_module()
    request = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
    hydration = json.loads(HYDRATION_PATH.read_text(encoding="utf-8"))

    assert client._validate_hydration(hydration, request) == hydration
    assert client._canonical_sha256(hydration) == client.EXPECTED_HYDRATION_SHA256

    for key, value in (
        ("schema_version", "wrong"),
        ("binding", {}),
        ("mechanics_payload", "not-an-object"),
    ):
        invalid = json.loads(json.dumps(hydration))
        invalid[key] = value
        with pytest.raises(ValueError):
            client._validate_hydration(invalid, request)


def test_missing_environment_token_is_not_accepted_as_a_cli_value() -> None:
    env = os.environ.copy()
    env.pop("DUNGEONMIND_THREAT_MECHANICS_BEARER_TOKEN", None)
    result = subprocess.run(
        [
            sys.executable,
            str(CLIENT_PATH),
            "--base-url",
            "http://127.0.0.1:8001",
            "--request-path",
            str(REQUEST_PATH),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "DUNGEONMIND_THREAT_MECHANICS_BEARER_TOKEN is required." in result.stderr
