"""Static asset integrity for the curated Mind Turn browser consumer."""

from __future__ import annotations

import importlib.util
import re
import socket
import threading
from http.client import HTTPConnection
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_ROOT = REPO_ROOT / "examples" / "curated_mind_turn_surface"
CANONICAL_REQUEST = REPO_ROOT / "tests" / "fixtures" / "requests" / "who-safeguards-ledger.json"
SERVER_SCRIPT = REPO_ROOT / "scripts" / "serve_curated_mind_turn_surface.py"

REQUIRED_FILES = (
    "index.html",
    "app.js",
    "styles.css",
    "demo-request.json",
)

# Reject CDN/font/script loads. Loopback API defaults (127.0.0.1) are allowed.
EXTERNAL_PATTERN = re.compile(
    r"""(?ix)
    //cdn
    | fonts\.googleapis
    | fonts\.gstatic
    | unpkg\.com
    | jsdelivr\.net
    | cdnjs\.cloudflare
    | @import\s+url
    | <script[^>]+src=["']https?://(?!127\.0\.0\.1)
    | <link[^>]+href=["']https?://(?!127\.0\.0\.1)
    | src=["']https?://(?!127\.0\.0\.1)
    | href=["']https?://(?!127\.0\.0\.1\b)
    """
)

PRODUCT_VOCAB = re.compile(
    r"(?i)\b(LandingPage|PlanSurface|PlaySurface|BuildSurface|drawer|pane-rail)\b"
)


def _load_server_module():
    spec = importlib.util.spec_from_file_location(
        "serve_curated_mind_turn_surface",
        SERVER_SCRIPT,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_required_assets_exist() -> None:
    for name in REQUIRED_FILES:
        path = EXAMPLE_ROOT / name
        assert path.is_file(), f"missing {path}"


def test_demo_request_is_byte_identical_to_canonical_fixture() -> None:
    demo = (EXAMPLE_ROOT / "demo-request.json").read_bytes()
    canonical = CANONICAL_REQUEST.read_bytes()
    assert demo == canonical


def test_assets_have_no_external_network_dependencies() -> None:
    for name in ("index.html", "app.js", "styles.css"):
        text = (EXAMPLE_ROOT / name).read_text(encoding="utf-8")
        assert EXTERNAL_PATTERN.search(text) is None, f"external dependency in {name}"


def test_html_and_docs_avoid_product_surface_ownership_vocab() -> None:
    text = (EXAMPLE_ROOT / "index.html").read_text(encoding="utf-8")
    assert PRODUCT_VOCAB.search(text) is None
    assert "curated Mind Turn" in text or "Mind Turn" in text


def test_app_js_uses_text_content_and_projection_kinds() -> None:
    text = (EXAMPLE_ROOT / "app.js").read_text(encoding="utf-8")
    assert "textContent" in text
    assert "innerHTML" not in text
    assert 'kind === "entity_brief"' in text or "entity_brief" in text
    assert "relationship_list" in text
    assert "evidence_summary" in text
    assert "/readyz" in text
    assert "/v1/mind-turn" in text
    assert "Exact replay matched" in text
    # Replay record is captured before fetch and bound to the submission host.
    assert "submittedPayload" in text
    assert "submittedApiBase" in text
    assert "responseBaseline" in text
    assert "historyBody" in text
    assert "Exact submitted request was retried" in text
    assert "canonicalize" in text
    assert "responsesEqual" in text


def test_server_module_import_does_not_bind_port() -> None:
    module = _load_server_module()
    assert module.DEFAULT_HOST == "127.0.0.1"
    assert module.DEFAULT_PORT == 8081
    assert module.example_root(REPO_ROOT) == EXAMPLE_ROOT.resolve()


def test_server_rejects_missing_root(tmp_path: Path) -> None:
    module = _load_server_module()
    code = module.main(["--root", str(tmp_path / "missing"), "--port", "8099"])
    assert code != 0


def test_server_rejects_incomplete_root(tmp_path: Path) -> None:
    module = _load_server_module()
    incomplete = tmp_path / "surface"
    incomplete.mkdir()
    (incomplete / "index.html").write_text("<html></html>\n", encoding="utf-8")
    code = module.main(["--root", str(incomplete), "--port", "8099"])
    assert code != 0


def test_server_help_exits_zero() -> None:
    module = _load_server_module()
    with pytest.raises(SystemExit) as excinfo:
        module.build_parser().parse_args(["--help"])
    # argparse --help exits via parser; main wraps SystemExit.
    assert excinfo.value.code == 0


def test_server_refuses_path_traversal(tmp_path: Path) -> None:
    module = _load_server_module()
    root = tmp_path / "surface"
    root.mkdir()
    for name in REQUIRED_FILES:
        (root / name).write_text(f"{name}\n", encoding="utf-8")
    secret = tmp_path / "secret.txt"
    secret.write_text("top-secret\n", encoding="utf-8")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    from functools import partial
    from http.server import ThreadingHTTPServer

    handler = partial(module._RootOnlyRequestHandler, directory=str(root.resolve()))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = HTTPConnection("127.0.0.1", port, timeout=2)
        conn.request("GET", "/index.html")
        ok = conn.getresponse()
        assert ok.status == 200
        assert ok.read() == b"index.html\n"
        conn.close()

        conn = HTTPConnection("127.0.0.1", port, timeout=2)
        conn.request("GET", "/../secret.txt")
        denied = conn.getresponse()
        body = denied.read()
        assert denied.status in {404, 403}
        assert b"top-secret" not in body
        conn.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
