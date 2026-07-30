"""Static import-boundary enforcement.

Two guarantees:
1. Layering: contracts ← domain ← application ← infrastructure/agents.
2. Core stays light: nothing under src/ imports web frameworks, database
   drivers, model frameworks, Hermes, DungeonMindBuddy ``apps.*``, or any
   sibling repository / UI package.

When PR B adds ``infrastructure/postgres``, extend ALLOWED_EXTERNAL_PER_LAYER
for that layer (e.g. psycopg/pgvector) — the test forces that choice to be
explicit and reviewable.
"""

import ast
import importlib
import pkgutil
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "dungeonmind"



FORBIDDEN_ROOTS = {
    "apps",  # DungeonMindBuddy application layer
    "fastapi",
    "uvicorn",
    "torch",
    "sentence_transformers",
    "psycopg",
    "psycopg2",
    "pgvector",
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
}

ALLOWED_EXTERNAL = {"pydantic"}

LAYER_RULES: dict[str, set[str]] = {
    "dungeonmind": set(),
    "dungeonmind.contracts": set(),
    "dungeonmind.domain": {"dungeonmind.contracts"},
    "dungeonmind.application": {"dungeonmind.contracts", "dungeonmind.domain"},
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
        for module in _imports_of(path, module_name, is_init):
            root = module.split(".")[0]
            if root in FORBIDDEN_ROOTS:
                violations.append(f"{path.relative_to(SRC)} imports {module}")
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
            if not module.startswith("dungeonmind"):
                violations.append(f"{module_name} imports unvetted third-party {module}")
                continue
            target_layer = _layer(module)
            if target_layer != importer_layer and target_layer not in allowed:
                violations.append(f"{module_name} illegally imports {module}")
    assert not violations, "layer violations:\n" + "\n".join(violations)


def test_every_module_imports_cleanly_without_optional_extras() -> None:
    import dungeonmind

    for module_info in pkgutil.walk_packages(dungeonmind.__path__, prefix="dungeonmind."):
        importlib.import_module(module_info.name)
    for forbidden in FORBIDDEN_ROOTS:
        assert forbidden not in sys.modules, f"{forbidden} imported as a side effect"
