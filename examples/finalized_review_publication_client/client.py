#!/usr/bin/env python3
"""Dependency-free example client for the finalized-review publication service."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REQUEST_SCHEMA = "dm_finalized_review_publication_request_v1"
PUBLICATION_SCHEMA = "dm_finalized_review_publication_v1"
PUBLICATION_PATH = "/v1/finalized-review-publications"
TOKEN_ENVIRONMENT = "DUNGEONMIND_PUBLICATION_BEARER_TOKEN"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish one finalized review through the DungeonMind service."
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--world-id", required=True)
    parser.add_argument("--review-id", required=True)
    parser.add_argument("--verify-replay", action="store_true")
    return parser


def _request_body(world_id: str, review_id: str) -> dict[str, str]:
    return {
        "schema_version": REQUEST_SCHEMA,
        "world_id": world_id,
        "review_id": review_id,
    }


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _validate_publication(value: Any, *, world_id: str, review_id: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("publication response is not an object")
    if value.get("schema_version") != PUBLICATION_SCHEMA:
        raise ValueError("publication response schema is invalid")
    if value.get("world_id") != world_id or value.get("review_id") != review_id:
        raise ValueError("publication response identity is invalid")
    if value.get("status") != "published":
        raise ValueError("publication response status is invalid")
    if not isinstance(value.get("published_revision_id"), str) or not value[
        "published_revision_id"
    ]:
        raise ValueError("publication response revision identity is missing")
    return value


def _validate_error(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not isinstance(value.get("error"), dict):
        raise ValueError("error response envelope is invalid")
    error = value["error"]
    if not isinstance(error.get("code"), str) or not isinstance(error.get("message"), str):
        raise ValueError("error response envelope is invalid")
    if not isinstance(error.get("details"), Mapping):
        raise ValueError("error response envelope is invalid")
    return value


def _post(base_url: str, body: dict[str, str], token: str) -> tuple[dict[str, Any] | None, int]:
    request = Request(
        f"{base_url.rstrip('/')}{PUBLICATION_PATH}",
        data=_canonical_json(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            envelope = _validate_error(json.loads(exc.read().decode("utf-8")))
        except (ValueError, json.JSONDecodeError):
            print("The publication service returned an invalid error envelope.", file=sys.stderr)
            return None, 1
        print(json.dumps(envelope, sort_keys=True), file=sys.stderr)
        error = envelope["error"]
        if (
            error.get("code") == "finalized_review_publication_outcome_unknown"
            and error["details"].get("retry_safe") is True
        ):
            return None, 75
        return None, 1
    except (URLError, TimeoutError, OSError):
        print("The publication service could not be reached.", file=sys.stderr)
        return None, 1
    try:
        return _validate_publication(
            payload,
            world_id=body["world_id"],
            review_id=body["review_id"],
        ), 0
    except (ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return None, 1


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    token = os.environ.get(TOKEN_ENVIRONMENT)
    if not token:
        print(f"{TOKEN_ENVIRONMENT} is required.", file=sys.stderr)
        return 1
    body = _request_body(args.world_id, args.review_id)
    first, status = _post(args.base_url, body, token)
    if status != 0 or first is None:
        return status
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
