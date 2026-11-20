"""Cold current entry points must not initialize historical graph runtimes."""

from __future__ import annotations

import importlib
import importlib.util
import os
import pickle
import subprocess
import sys
import textwrap

import pytest

CLASSIC_RUNTIMES = (
    "dungeonmind.application.graph_snapshot",
    "dungeonmind.application.world_graph_projection",
    "dungeonmind.application.world_graph_retrieval",
    "dungeonmind.application.review_publication",
    "dungeonmind.application.contribution_review",
    "dungeonmind.application.contribution_review_v2",
    "dungeonmind.application.contribution_review_v3",
    "dungeonmind.application.contribution_review_v4",
    "dungeonmind.application.existing_world_adoption",
    "dungeonmind.application.reviewed_world_initialization",
    "dungeonmind.infrastructure.postgres.graph",
    "dungeonmind.infrastructure.postgres.review_publication",
    "dungeonmind.infrastructure.postgres.existing_world_adoption",
)


def _cold(code: str, denied=CLASSIC_RUNTIMES) -> None:
    script = (
        f"""
import importlib.abc
import sys
blocked = {denied!r}
class RejectClassic(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + '.') for name in blocked):
            raise AssertionError('Cold current import opened ' + fullname)
sys.meta_path.insert(0, RejectClassic())
"""
        + textwrap.dedent(code)
        + """
assert not any(name == prefix or name.startswith(prefix + '.')
               for name in sys.modules for prefix in blocked)
"""
    )
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-B", "-c", script], env=env, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "entry",
    [
        "contracts",
        "application",
        "contract_models",
        "application_services",
        "contract_submodule",
        "application_submodule",
    ],
)
def test_cold_current_entry_points_do_not_load_classic_runtime(entry):
    statements = {
        "contracts": (
            "import dungeonmind.contracts as facade; assert 'WorldGraphRevision' not in dir(facade)"
        ),
        "application": (
            "import dungeonmind.application as facade; "
            "assert 'WorldGraphProjectionService' not in dir(facade)"
        ),
        "contract_models": (
            "from dungeonmind.contracts.vnext import KnowledgeRevision as Model; "
            "assert callable(Model)"
        ),
        "application_services": (
            "from dungeonmind.application.vnext import EntityReadService as Reader; "
            "assert callable(Reader)"
        ),
        "contract_submodule": (
            "from dungeonmind.contracts.vnext.knowledge import KnowledgeRevision as Model; "
            "assert callable(Model)"
        ),
        "application_submodule": (
            "from dungeonmind.application.vnext.entity_reads import EntityReadService as Reader; "
            "assert callable(Reader)"
        ),
    }
    _cold(statements[entry] + "\nassert 'psycopg' not in sys.modules\n")


@pytest.mark.skipif(importlib.util.find_spec("psycopg") is None, reason="optional postgres extra")
@pytest.mark.parametrize("native_entry", ["database", "adapter", "direct_submodule"])
def test_cold_native_postgres_adapter_does_not_load_classic_aggregate(native_entry):
    entry = {
        "database": "from dungeonmind.infrastructure.postgres import PostgresDatabase",
        "adapter": (
            "from dungeonmind.infrastructure.postgres import PostgresNativeSourceEvidenceRepository"
        ),
        "direct_submodule": (
            "from dungeonmind.infrastructure.postgres.vnext_sources "
            "import PostgresNativeSourceEvidenceRepository"
        ),
    }[native_entry]
    connection_fence = textwrap.dedent("""
        import psycopg
        def forbidden(*args, **kwargs):
            raise AssertionError('Import attempted a PostgreSQL connection')
        psycopg.connect = forbidden
    """)
    _cold(
        connection_fence
        + entry
        + "\n"
        + textwrap.dedent("""
        from dungeonmind.infrastructure import postgres
        from dungeonmind.infrastructure.postgres import PostgresDatabase
        database = PostgresDatabase('postgresql://unused.invalid/never_opened')
        if 'PostgresNativeSourceEvidenceRepository' in globals():
            repository = PostgresNativeSourceEvidenceRepository(database)
            assert repository is not None
        else:
            assert 'dungeonmind.infrastructure.postgres.vnext_sources' not in sys.modules
        assert 'PostgresRepositoryBundle' in dir(postgres)
        assert 'PostgresRepositoryBundle' not in vars(postgres)
    """)
    )


def test_cold_historical_reader_does_not_load_fresh_publishers_or_require_postgres():
    _cold(
        """
        from dungeonmind.application.compatibility import (
            read_historical_finalized_publication, load_legacy_world_compat_manifest,
        )
        from dungeonmind.application.compatibility.publication_recovery import (
            read_historical_finalized_publication as implementation,
        )
        assert read_historical_finalized_publication is implementation
        assert load_legacy_world_compat_manifest() is not None
        assert 'psycopg' not in sys.modules
    """,
        denied=(
            "dungeonmind.application.review_publication",
            "dungeonmind.application.existing_world_adoption",
            "dungeonmind.application.contribution_review_v4",
        ),
    )


@pytest.mark.parametrize(
    "namespace,alias,implementation",
    [
        ("contracts", "GraphContributionV4", "dungeonmind.contracts.contribution"),
        (
            "application",
            "finalize_contribution_review_v4",
            "dungeonmind.application.contribution_review_v4",
        ),
    ],
)
def test_explicit_legacy_alias_is_original_cached_object(namespace, alias, implementation):
    facade = importlib.import_module("dungeonmind." + namespace)
    original = getattr(importlib.import_module(implementation), alias)
    assert getattr(facade, alias) is original
    assert getattr(facade, alias) is original
    assert alias in dir(facade)
    assert pickle.loads(pickle.dumps(original)) is original
    with pytest.raises(AttributeError, match="not_a_public_export"):
        _ = facade.not_a_public_export


@pytest.mark.parametrize("namespace", ["contracts", "application"])
def test_explicit_star_import_keeps_advertised_aliases(namespace):
    facade = importlib.import_module("dungeonmind." + namespace)
    imported: dict[str, object] = {}
    exec(f"from dungeonmind.{namespace} import *", imported)
    assert all(imported[name] is getattr(facade, name) for name in facade.__all__)


@pytest.mark.skipif(importlib.util.find_spec("psycopg") is None, reason="optional postgres extra")
def test_cold_legacy_bundle_preserves_reflection_and_root_factories():
    _cold(
        """
        import inspect
        import pickle
        import typing
        import psycopg
        from dungeonmind.application.publication_admission import PublicationAdmissionRegistry
        from dungeonmind.infrastructure import postgres
        def forbidden(*args, **kwargs):
            raise AssertionError('Aggregate construction attempted a PostgreSQL connection')
        psycopg.connect = forbidden
        bundle_type = postgres.PostgresRepositoryBundle
        assert bundle_type.__module__ == 'dungeonmind.infrastructure.postgres'
        assert bundle_type.__name__ == bundle_type.__qualname__ == 'PostgresRepositoryBundle'
        assert pickle.loads(pickle.dumps(bundle_type)) is bundle_type
        assert 'class PostgresRepositoryBundle' in inspect.getsource(bundle_type)
        assert 'def __init__' in inspect.getsource(bundle_type.__init__)
        assert list(inspect.signature(bundle_type).parameters) == ['database', 'admission_registry']
        hints = typing.get_type_hints(bundle_type.__init__)
        assert hints['database'] is postgres.PostgresDatabase
        assert hints['admission_registry'] == PublicationAdmissionRegistry | None
        database = postgres.PostgresDatabase('postgresql://unused.invalid/never_opened')
        registry = PublicationAdmissionRegistry()
        sentinel = object()
        calls = []
        postgres.PostgresWorldGraphRepository = lambda db: sentinel if db is database else None
        def review_repository(db, *, admission_registry=None):
            calls.append((db, admission_registry))
            return sentinel
        postgres.PostgresFinalizedReviewPublicationRepository = review_repository
        bundle = bundle_type(database, admission_registry=registry)
        assert bundle.database is database and bundle.world_graph is sentinel
        assert bundle.finalized_review_publications is sentinel
        assert calls == [(database, registry)]
        """,
        denied=(),
    )


@pytest.mark.skipif(importlib.util.find_spec("psycopg") is None, reason="optional postgres extra")
@pytest.mark.parametrize("replace_first", [True, False])
@pytest.mark.parametrize("registry_mode", ["omitted", "none", "explicit"])
def test_cold_bundle_resolves_public_factories_at_construction(replace_first, registry_mode):
    _cold(
        f"""
        import psycopg
        from dungeonmind.infrastructure import postgres
        from dungeonmind.application.publication_admission import PublicationAdmissionRegistry
        def no_connection(*args, **kwargs):
            raise AssertionError('Unexpected database connection')
        psycopg.connect = no_connection
        seen = []
        sentinel = object()
        def world_factory(database):
            seen.append(database)
            return sentinel
        if {replace_first!r}:
            postgres.PostgresWorldGraphRepository = world_factory
        bundle_type = postgres.PostgresRepositoryBundle
        if not {replace_first!r}:
            postgres.PostgresWorldGraphRepository = world_factory
        database = postgres.PostgresDatabase('postgresql://unused.invalid/never_opened')
        registry = PublicationAdmissionRegistry() if {registry_mode!r} == 'explicit' else None
        def review_factory(database, *, admission_registry=None):
            assert admission_registry is registry
            return sentinel
        postgres.PostgresFinalizedReviewPublicationRepository = review_factory
        if {registry_mode!r} == 'omitted':
            bundle = bundle_type(database)
        else:
            bundle = bundle_type(database, admission_registry=registry)
        assert bundle.world_graph is sentinel and bundle.finalized_review_publications is sentinel
        assert seen == [database]
    """,
        denied=(),
    )


def test_cold_native_contracts_do_not_compile_classic_world_graph_models():
    _cold(
        "from dungeonmind.contracts.vnext import KnowledgeRevision; "
        "assert callable(KnowledgeRevision)",
        denied=(
            "dungeonmind.contracts.graph",
            "dungeonmind.contracts.projection",
            "dungeonmind.contracts.projection_v2",
            "dungeonmind.contracts.contribution",
        ),
    )


@pytest.mark.parametrize(
    "name,leaf",
    [
        ("WorldGraphHead", "graph"),
        ("WorldGraphRevision", "graph"),
        ("WorldGraphProjectionRequestV2", "projection_v2"),
        ("ScopeModeV2", "projection_v2"),
    ],
)
def test_retired_classic_contract_is_available_only_from_explicit_leaf(name, leaf):
    facade = importlib.import_module("dungeonmind.contracts")
    assert name not in dir(facade)
    assert name not in facade.__all__
    with pytest.raises(AttributeError):
        getattr(facade, name)
    definition = getattr(importlib.import_module(f"dungeonmind.contracts.{leaf}"), name)
    assert definition.__name__ == name


@pytest.mark.parametrize(
    "name,leaf",
    [
        ("WorldGraphProjectionService", "world_graph_projection"),
        ("WorldGraphRetrievalService", "world_graph_retrieval"),
        ("publish_finalized_review", "review_publication"),
        ("publish_identity_reconciliation", "world_identity_reconciliation"),
    ],
)
def test_retired_classic_service_is_available_only_from_explicit_leaf(name, leaf):
    facade = importlib.import_module("dungeonmind.application")
    assert name not in dir(facade)
    assert name not in facade.__all__
    with pytest.raises(AttributeError):
        getattr(facade, name)
    definition = getattr(importlib.import_module(f"dungeonmind.application.{leaf}"), name)
    assert definition.__name__ == name
