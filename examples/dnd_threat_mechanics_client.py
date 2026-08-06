#!/usr/bin/env python3
"""Dependency-free client for exact-revision Threat mechanics hydration."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REQUEST_SCHEMA = "dmdnd_threat_mechanics_hydration_request_v1"
HYDRATION_SCHEMA = "dmdnd_threat_mechanics_hydration_v1"
HYDRATION_PATH = "/v1/dnd/threat-mechanics-hydrations"
TOKEN_ENVIRONMENT = "DUNGEONMIND_THREAT_MECHANICS_BEARER_TOKEN"
REQUEST_PATH_ENVIRONMENT = "DUNGEONMIND_THREAT_MECHANICS_REQUEST_PATH"
EXPECTED_HYDRATION_SHA256 = (
    "166dfe01ad0e2f4b57de3c74cfd50160e34a29591957f85b4a786c9f2edd6e16"
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Hydrate one exact D&D Threat mechanics resource."
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument(
        "--request-path",
        default=os.environ.get(REQUEST_PATH_ENVIRONMENT),
    )
    parser.add_argument("--verify-replay", action="store_true")
    return parser


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _load_request(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict) or value.get("schema_version") != REQUEST_SCHEMA:
        raise ValueError("request fixture schema is invalid")
    return value


def _validate_hydration(value: Any, request: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("hydration response is not an object")
    if value.get("schema_version") != HYDRATION_SCHEMA:
        raise ValueError("hydration response schema is invalid")
    binding = value.get("binding")
    if not isinstance(binding, dict):
        raise ValueError("hydration binding is missing")
    for field in ("world_id", "graph_revision_id", "object_id"):
        if binding.get(field) != request.get(field):
            raise ValueError(f"hydration {field} does not match the request")
    if binding.get("resource_ref") != request.get("resource_ref"):
        raise ValueError("hydration resource_ref does not match the request")
    if not isinstance(binding.get("binding_id"), str) or not binding["binding_id"]:
        raise ValueError("hydration binding_id is missing")
    if not isinstance(value.get("mechanics_payload"), dict):
        raise ValueError("hydration mechanics_payload is missing")
    return value


def _validate_error(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not isinstance(value.get("error"), dict):
        raise ValueError("error response envelope is invalid")
    error = value["error"]
    if not isinstance(error.get("code"), str) or not isinstance(
        error.get("message"), str
    ):
        raise ValueError("error response envelope is invalid")
    if not isinstance(error.get("details"), Mapping):
        raise ValueError("error response envelope is invalid")
    return value


def _post(
    base_url: str,
    body: dict[str, Any],
    token: str,
) -> tuple[dict[str, Any] | None, int]:
    request = Request(
        f"{base_url.rstrip('/')}{HYDRATION_PATH}",
        data=_canonical_json(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            if response.status != 200:
                raise ValueError("hydration service returned an unexpected status")
            if response.headers.get_content_type() != "application/json":
                raise ValueError("hydration service returned a non-JSON response")
            if response.headers.get("Cache-Control") != "no-store":
                raise ValueError("hydration response is not no-store")
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            envelope = _validate_error(json.loads(exc.read().decode("utf-8")))
        except (ValueError, json.JSONDecodeError):
            print("The hydration service returned an invalid error envelope.", file=sys.stderr)
            return None, 1
        print(json.dumps(envelope, sort_keys=True), file=sys.stderr)
        return None, 1
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return None, 1
    try:
        return _validate_hydration(payload, body), 0
    except (ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return None, 1


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    token = os.environ.get(TOKEN_ENVIRONMENT)
    if not token:
        print(f"{TOKEN_ENVIRONMENT} is required.", file=sys.stderr)
        return 1
    if not args.request_path:
        print(
            f"--request-path or {REQUEST_PATH_ENVIRONMENT} is required.",
            file=sys.stderr,
        )
        return 1
    try:
        body = _load_request(args.request_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    first, status = _post(args.base_url, body, token)
    if status != 0 or first is None:
        return status
    if _canonical_sha256(first) != EXPECTED_HYDRATION_SHA256:
        print("Hydration response digest did not match the expected fixture.", file=sys.stderr)
        return 1
    if args.verify_replay:
        second, replay_status = _post(args.base_url, body, token)
        if replay_status != 0 or second is None:
            return replay_status
        if _canonical_json(first) != _canonical_json(second):
            print("Replay response was not byte-equivalent JSON.", file=sys.stderr)
            return 1
    print(json.dumps(first, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
