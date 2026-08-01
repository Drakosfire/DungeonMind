#!/usr/bin/env python3
"""Loopback static server for the curated Mind Turn browser example.

stdlib only. Serves solely ``examples/curated_mind_turn_surface/``.
Does not import DungeonMind application code, open a database, or seed data.
Safe to import without starting a server.
"""

from __future__ import annotations

import argparse
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8081
EXAMPLE_RELATIVE = Path("examples") / "curated_mind_turn_surface"
REQUIRED_ASSETS = (
    "index.html",
    "app.js",
    "styles.css",
    "demo-request.json",
)


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def example_root(repo_root: Path | None = None) -> Path:
    root = (repo_root or repository_root()).resolve()
    return (root / EXAMPLE_RELATIVE).resolve()


def validate_example_root(root: Path) -> None:
    if not root.is_dir():
        raise FileNotFoundError(f"example root missing: {root}")
    missing = [name for name in REQUIRED_ASSETS if not (root / name).is_file()]
    if missing:
        raise FileNotFoundError(
            f"example root incomplete at {root}; missing: {', '.join(missing)}"
        )


class _RootOnlyRequestHandler(SimpleHTTPRequestHandler):
    """Serve files under one directory; refuse path traversal escapes."""

    def __init__(
        self,
        *args: object,
        directory: str,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, directory=directory, **kwargs)

    def translate_path(self, path: str) -> str:
        translated = super().translate_path(path)
        root = Path(self.directory).resolve()
        candidate = Path(translated).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            # Map escapes to a non-existent path under the root (404), never
            # outside it. Do not call send_error here — the request cycle owns
            # the response.
            return str(root / ".traversal-rejected")
        return str(candidate)

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write(f"{self.address_string()} - {fmt % args}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Serve the curated Mind Turn browser example on loopback. "
            "Run the API with DUNGEONMIND_CORS_ORIGIN matching this origin."
        )
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="bind host (default: 127.0.0.1)")
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="bind port (default: 8081)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="optional override for the example directory (tests only)",
    )
    return parser


def serve(host: str, port: int, root: Path) -> int:
    validate_example_root(root)
    handler = partial(_RootOnlyRequestHandler, directory=str(root))
    try:
        server = ThreadingHTTPServer((host, port), handler)
    except OSError as exc:
        print(f"error: cannot bind {host}:{port}: {exc}", file=sys.stderr)
        return 1

    origin = f"http://{host}:{port}"
    print(f"Serving curated Mind Turn surface from {root}")
    print(f"Open browser at: {origin}/")
    print(f"Required API CORS origin: DUNGEONMIND_CORS_ORIGIN={origin}")
    print("This process performs no writes and initializes no DungeonMind service.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return int(code) if isinstance(code, int) else 1

    root = args.root.resolve() if args.root is not None else example_root()
    try:
        validate_example_root(root)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.port <= 0 or args.port > 65535:
        print(f"error: invalid port {args.port}", file=sys.stderr)
        return 1

    return serve(args.host, args.port, root)


if __name__ == "__main__":
    raise SystemExit(main())
