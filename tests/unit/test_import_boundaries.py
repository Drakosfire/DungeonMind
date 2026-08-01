"""Static import-boundary enforcement.

Two guarantees:
1. Layering: contracts ← domain ← application ← infrastructure/agents.
2. Core stays light: nothing under src/ imports web frameworks, database
   drivers, model frameworks, Hermes, DungeonMindBuddy ``apps.*``, or any
   sibling repository / UI package — except the explicit
   ``infrastructure.postgres`` adapter layer, which may import psycopg/pgvector
   and is never loaded by the core import path.
"""

import ast
import importlib
import sys
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
SRC = SRC_ROOT / "dungeonmind"
DND_SRC = SRC_ROOT / "dungeonmind_dnd"

FORBIDDEN_ROOTS = {
    "apps",  # DungeonMindBuddy application layer
    "torch",
    "sentence_transformers",
    "psycopg2",
    "pymongo",
    "motor",
    "openai",
    "hermes",
    "landingpage",
    "cardgenerator",
    "ruleslawyer",
    "statblockgenerator",
    "graph_memory",  # DungeonMindBuddy package: adapt, never import
    "retrieval_lab",  # RulesIngestion package: eval-only vendoring, never runtime import
    "alembic",  # migration runner only; never under src/
    "sqlalchemy",  # Alembic dependency; never under src/
}

# Allowed only inside dungeonmind.infrastructure.postgres.
POSTGRES_ONLY_ROOTS = {"psycopg", "pgvector"}

# Allowed only inside dungeonmind.service (optional ``api`` extra).
API_ONLY_ROOTS = {"fastapi", "uvicorn", "starlette"}

ALLOWED_EXTERNAL = {"pydantic"}

LAYER_RULES: dict[str, set[str]] = {
    "dungeonmind": set(),
    "dungeonmind.contracts": set(),
    "dungeonmind.domain": {"dungeonmind.contracts"},
    "dungeonmind.application": {
        "dungeonmind.contracts",
        "dungeonmind.domain",
        # AgentAdapter / sanitize_agent_input are application-facing ports hosted
        # under agents/ until a later extraction; MindTurnService depends on them.
        "dungeonmind.agents",
    },
    "dungeonmind.agents": {
        "dungeonmind.contracts",
        "dungeonmind.domain",
        "dungeonmind.application",
    },
    "dungeonmind.infrastructure": {
        "dungeonmind.contracts",
        "dungeonmind.domain",
        "dungeonmind.application",
    },
    "dungeonmind.infrastructure.memory": {
        "dungeonmind.contracts",
        "dungeonmind.domain",
        "dungeonmind.application",
    },
    "dungeonmind.infrastructure.postgres": {
        "dungeonmind.contracts",
        "dungeonmind.domain",
        "dungeonmind.application",
    },
    "dungeonmind.infrastructure.fixtures": {
        "dungeonmind.contracts",
        "dungeonmind.domain",
        "dungeonmind.application",
    },
    "dungeonmind.infrastructure.semantic_profiles": {
        "dungeonmind.contracts",
        "dungeonmind.domain",
        "dungeonmind.application",
    },
    "dungeonmind.service": {
        "dungeonmind.contracts",
        "dungeonmind.domain",
        "dungeonmind.application",
        "dungeonmind.agents",
        "dungeonmind.infrastructure",
        "dungeonmind.infrastructure.fixtures",
        "dungeonmind.infrastructure.postgres",
        "dungeonmind.infrastructure.memory",
        "dungeonmind.infrastructure.semantic_profiles",
    },
}


def _layer(module: str) -> str:
    parts = module.split(".")
    if len(parts) >= 3 and parts[:2] == ["dungeonmind", "infrastructure"]:
        return ".".join(parts[:3])
    return ".".join(parts[:2]) if len(parts) >= 2 else parts[0]


def _imports_of(path: Path, module_name: str, is_init: bool) -> list[str]:
    """Absolute names of everything ``path`` imports, resolving relative imports."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package_parts = module_name.split(".") if is_init else module_name.split(".")[:-1]
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    modules.append(node.module)
                continue
            base = package_parts[: len(package_parts) - (node.level - 1)]
            if node.module:
                base = [*base, *node.module.split(".")]
            if base:
                modules.append(".".join(base))
    return modules


def _all_source_files() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def _module_name(path: Path) -> tuple[str, bool]:
    is_init = path.name == "__init__.py"
    dotted = ".".join(path.relative_to(SRC).with_suffix("").parts)
    module_name = f"dungeonmind.{dotted}"
    if is_init:
        suffix = ".__init__"
        module_name = module_name[: -len(suffix)] if module_name.endswith(suffix) else "dungeonmind"
    return module_name, is_init


def test_no_forbidden_imports_anywhere() -> None:
    violations: list[str] = []
    for path in _all_source_files():
        module_name, is_init = _module_name(path)
        layer = _layer(module_name)
        for module in _imports_of(path, module_name, is_init):
            root = module.split(".")[0]
            if root in FORBIDDEN_ROOTS:
                violations.append(f"{path.relative_to(SRC)} imports {module}")
            if root in POSTGRES_ONLY_ROOTS and layer != "dungeonmind.infrastructure.postgres":
                violations.append(
                    f"{path.relative_to(SRC)} imports {module} outside infrastructure.postgres"
                )
            if root in API_ONLY_ROOTS and layer != "dungeonmind.service":
                violations.append(
                    f"{path.relative_to(SRC)} imports {module} outside service"
                )
    assert not violations, "forbidden imports:\n" + "\n".join(violations)


def test_layer_rules_hold() -> None:
    stdlib = sys.stdlib_module_names
    violations: list[str] = []
    for path in _all_source_files():
        module_name, is_init = _module_name(path)
        importer_layer = _layer(module_name)
        allowed = LAYER_RULES.get(importer_layer)
        assert allowed is not None, f"no layer rule for {module_name}; extend LAYER_RULES"
        for module in _imports_of(path, module_name, is_init):
            root = module.split(".")[0]
            if root in stdlib or root in ALLOWED_EXTERNAL:
                continue
            if root in POSTGRES_ONLY_ROOTS and importer_layer == (
                "dungeonmind.infrastructure.postgres"
            ):
                continue
            if root in API_ONLY_ROOTS and importer_layer == "dungeonmind.service":
                continue
            if not module.startswith("dungeonmind"):
                violations.append(f"{module_name} imports unvetted third-party {module}")
                continue
            target_layer = _layer(module)
            if target_layer != importer_layer and target_layer not in allowed:
                violations.append(f"{module_name} illegally imports {module}")
    assert not violations, "layer violations:\n" + "\n".join(violations)


def test_dungeonmind_does_not_import_dungeonmind_dnd() -> None:
    violations: list[str] = []
    for path in _all_source_files():
        module_name, is_init = _module_name(path)
        for module in _imports_of(path, module_name, is_init):
            if module == "dungeonmind_dnd" or module.startswith("dungeonmind_dnd."):
                violations.append(f"{module_name} imports {module}")
    assert not violations, "kernel imported dungeonmind_dnd:\n" + "\n".join(violations)


def test_dungeonmind_dnd_stays_data_only() -> None:
    """Sibling package may not import application/infrastructure/service layers."""
    if not DND_SRC.exists():
        pytest.skip("dungeonmind_dnd package missing")
    forbidden_prefixes = (
        "dungeonmind.application",
        "dungeonmind.infrastructure",
        "dungeonmind.service",
        "dungeonmind.agents",
    )
    violations: list[str] = []
    for path in sorted(DND_SRC.rglob("*.py")):
        is_init = path.name == "__init__.py"
        dotted = ".".join(path.relative_to(DND_SRC).with_suffix("").parts)
        module_name = (
            "dungeonmind_dnd"
            if is_init and dotted in {"", "__init__"}
            else f"dungeonmind_dnd.{dotted.removesuffix('.__init__')}"
        )
        if module_name.endswith("."):
            module_name = "dungeonmind_dnd"
        for module in _imports_of(path, module_name, is_init):
            blocked = any(
                module == prefix or module.startswith(f"{prefix}.")
                for prefix in forbidden_prefixes
            )
            if blocked:
                violations.append(f"{module_name} imports {module}")
    assert not violations, "dungeonmind_dnd layer violations:\n" + "\n".join(
        violations
    )


def test_every_module_imports_cleanly_without_optional_extras() -> None:
    # Import by source file so pkgutil.walk_packages cannot pull in the
    # optional postgres package (which requires the postgres extra).
    # Clear any prior optional-extra residue from collecting integration tests
    # when the postgres extra is installed in the same pytest process.
    for name in list(sys.modules):
        if name == "dungeonmind.infrastructure.postgres" or name.startswith(
            "dungeonmind.infrastructure.postgres."
        ):
            del sys.modules[name]
        if name == "dungeonmind.service.api" or name == "dungeonmind.service.bootstrap":
            del sys.modules[name]
        root = name.split(".", 1)[0]
        if root in POSTGRES_ONLY_ROOTS or root in API_ONLY_ROOTS:
            del sys.modules[name]

    for path in _all_source_files():
        module_name, _is_init = _module_name(path)
        if module_name == "dungeonmind.infrastructure.postgres" or module_name.startswith(
            "dungeonmind.infrastructure.postgres."
        ):
            continue
        # Optional FastAPI host modules require the ``api`` (and for bootstrap,
        # ``postgres``) extras; they must not load on the core import path.
        if module_name in {"dungeonmind.service.api", "dungeonmind.service.bootstrap"}:
            continue
        importlib.import_module(module_name)
    for forbidden in FORBIDDEN_ROOTS | POSTGRES_ONLY_ROOTS | API_ONLY_ROOTS:
        assert forbidden not in sys.modules, f"{forbidden} imported as a side effect"
