"""Static import-boundary enforcement.

Three guarantees:
1. Layering: contracts ← domain ← application ← infrastructure/agents.
2. Core stays light: nothing under src/ imports web frameworks, database
   drivers, model frameworks, Hermes, DungeonMindBuddy ``apps.*``, or any
   sibling repository / UI package — except the explicit
   ``infrastructure.postgres`` adapter layer, which may import psycopg/pgvector
   and is never loaded by the core import path.
3. The semantic-profile dependency is one-way: the kernel never imports
   ``dungeonmind_dnd``, and the executable profile package imports only the
   narrow allowed kernel contract/canonical modules (ADR-0005).
"""

import ast
import importlib
import subprocess
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


# The D&D profile package is executable but narrow (ADR-0005 / ADR-0006 /
# ADR-0007). Most modules retain the B.2c contract/canonical allowlist. Only
# B.2d contribution-planning modules may import the expanded graph /
# contribution / identity / vocabulary / graph_snapshot surface. The B.2e
# review adapter has its own narrower generic-review allowlist. The B.3a
# mechanics binder may import only the graph snapshot, graph contract,
# semantic-profile contract, and canonical hashing surface. No blanket
# allowance exists for dungeonmind.application.* or any repository /
# infrastructure / service / agent.
DND_ALLOWED_KERNEL_MODULES = {
    "dungeonmind.contracts.base",
    "dungeonmind.contracts.evidence",
    "dungeonmind.contracts.semantic_profile",
    "dungeonmind.domain.canonical",
}

DND_PLANNING_MODULES = frozenset(
    {
        "dungeonmind_dnd.application.contribution_planning",
        "dungeonmind_dnd.contracts.contribution_planning",
    }
)

DND_PLANNING_ALLOWED_KERNEL_MODULES = DND_ALLOWED_KERNEL_MODULES | {
    "dungeonmind.application.graph_snapshot",
    "dungeonmind.contracts.contribution",
    "dungeonmind.contracts.graph",
    "dungeonmind.contracts.identity",
    "dungeonmind.contracts.vocabulary",
}

DND_REVIEW_MODULES = frozenset({"dungeonmind_dnd.application.contribution_review"})

DND_REVIEW_ALLOWED_KERNEL_MODULES = DND_ALLOWED_KERNEL_MODULES | {
    "dungeonmind.contracts.contribution",
    "dungeonmind.contracts.contribution_review",
    "dungeonmind.contracts.identity",
}

DND_MECHANICS_MODULES = frozenset({"dungeonmind_dnd.application.threat_mechanics"})

DND_MECHANICS_ALLOWED_KERNEL_MODULES = DND_ALLOWED_KERNEL_MODULES | {
    "dungeonmind.application.graph_snapshot",
    "dungeonmind.contracts.graph",
    "dungeonmind.contracts.projection",
    "dungeonmind.domain.revision_ids",
}

DND_FORBIDDEN_KERNEL_PREFIXES = (
    "dungeonmind.application.repositories",
    "dungeonmind.infrastructure",
    "dungeonmind.service",
    "dungeonmind.agents",
)


def _dnd_module_name(path: Path) -> tuple[str, bool]:
    is_init = path.name == "__init__.py"
    dotted = ".".join(path.relative_to(DND_SRC).with_suffix("").parts)
    module_name = (
        "dungeonmind_dnd"
        if is_init and dotted in {"", "__init__"}
        else f"dungeonmind_dnd.{dotted.removesuffix('.__init__')}"
    )
    if module_name.endswith("."):
        module_name = "dungeonmind_dnd"
    return module_name, is_init


def _dnd_allowed_for(module_name: str) -> set[str]:
    if module_name in DND_REVIEW_MODULES:
        return DND_REVIEW_ALLOWED_KERNEL_MODULES
    if module_name in DND_MECHANICS_MODULES:
        return DND_MECHANICS_ALLOWED_KERNEL_MODULES
    if module_name in DND_PLANNING_MODULES:
        return DND_PLANNING_ALLOWED_KERNEL_MODULES
    return DND_ALLOWED_KERNEL_MODULES


def test_dungeonmind_dnd_executable_profile_boundary() -> None:
    """Path-sensitive profile allowlist: B.2c narrow; B.2d planning expanded."""
    if not DND_SRC.exists():
        pytest.skip("dungeonmind_dnd package missing")
    stdlib = sys.stdlib_module_names
    violations: list[str] = []
    for path in sorted(DND_SRC.rglob("*.py")):
        module_name, is_init = _dnd_module_name(path)
        allowed = _dnd_allowed_for(module_name)
        for module in _imports_of(path, module_name, is_init):
            root = module.split(".")[0]
            if root in stdlib or root in ALLOWED_EXTERNAL:
                continue
            if root == "dungeonmind_dnd":
                continue
            if module in allowed:
                continue
            violations.append(f"{module_name} imports unallowed module {module}")
            forbidden = any(
                module == prefix or module.startswith(f"{prefix}.")
                for prefix in DND_FORBIDDEN_KERNEL_PREFIXES
            )
            if forbidden:
                violations.append(
                    f"{module_name} imports forbidden kernel surface {module}"
                )
    assert not violations, "dungeonmind_dnd boundary violations:\n" + "\n".join(
        violations
    )


def test_dnd_planning_modules_never_import_repositories_or_infra() -> None:
    """B.2d planning stays repository-blind even with its expanded allowlist."""
    if not DND_SRC.exists():
        pytest.skip("dungeonmind_dnd package missing")
    violations: list[str] = []
    for path in sorted(DND_SRC.rglob("*.py")):
        module_name, is_init = _dnd_module_name(path)
        for module in _imports_of(path, module_name, is_init):
            if any(
                module == prefix or module.startswith(f"{prefix}.")
                for prefix in DND_FORBIDDEN_KERNEL_PREFIXES
            ):
                violations.append(f"{module_name} imports {module}")
    assert not violations, "forbidden planner imports:\n" + "\n".join(violations)


def test_kernel_import_never_loads_dnd_package() -> None:
    code = (
        "import sys; import dungeonmind; "
        'assert "dungeonmind_dnd" not in sys.modules, '
        '"kernel import loaded dungeonmind_dnd"'
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_dnd_import_loads_no_optional_dependencies() -> None:
    code = (
        "import sys; import dungeonmind_dnd; "
        "import dungeonmind_dnd.contracts, dungeonmind_dnd.application.threat_candidates; "
        'forbidden = ("fastapi", "psycopg", "sqlalchemy", "openai", "anthropic"); '
        "loaded = [name for name in forbidden if name in sys.modules]; "
        'assert not loaded, f"profile import loaded {loaded}"'
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_dnd_planning_import_loads_no_optional_dependencies() -> None:
    code = (
        "import sys; "
        "import dungeonmind_dnd.application.contribution_planning; "
        'forbidden = ("fastapi", "psycopg", "sqlalchemy", "openai", "anthropic"); '
        "loaded = [name for name in forbidden if name in sys.modules]; "
        'assert not loaded, f"planning import loaded {loaded}"'
    )
    subprocess.run([sys.executable, "-c", code], check=True)


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
