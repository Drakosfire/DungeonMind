"""Shared contract cases for read-only authority enumeration repository ports."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dungeonmind.application.existing_world_adoption import adopt_existing_world
from dungeonmind.application.reviewed_world_initialization import initialize_reviewed_world
from dungeonmind.contracts.existing_world_adoption import (
    existing_world_adoption_bundle_canonical_bytes,
)
from tests.conftest import make_publish
from tests.unit.test_existing_world_adoption import graph_reader as adoption_graph_reader
from tests.unit.test_existing_world_adoption import make_isolated_bundle
from tests.unit.test_reviewed_world_initialization_materialization_v6 import (
    NOW,
)
from tests.unit.test_reviewed_world_initialization_materialization_v6 import (
    _artifact as init_artifact,
)
from tests.unit.test_reviewed_world_initialization_materialization_v6 import (
    _contribution as init_contribution,
)
from tests.unit.test_reviewed_world_initialization_materialization_v6 import (
    _edge as init_edge,
)
from tests.unit.test_reviewed_world_initialization_materialization_v6 import (
    _node as init_node,
)
from tests.unit.test_reviewed_world_initialization_materialization_v6 import (
    _revision as init_revision,
)
from tests.unit.test_reviewed_world_initialization_materialization_v6 import (
    graph_reader as init_graph_reader,
)
from tests.unit.test_reviewed_world_initialization_materialization_v6 import (
    make_command as make_init_command,
)


@dataclass(frozen=True)
class EnumerationBundle:
    world_graph: Any
    existing_world_adoptions: Any
    reviewed_world_initializations: Any


def list_heads_empty(bundle: EnumerationBundle) -> None:
    assert bundle.world_graph.list_heads() == []


def list_heads_sorted_deterministic_copy_safe(bundle: EnumerationBundle) -> None:
    for world_id in ("world:alpha", "world:zebra", "world:mid"):
        bundle.world_graph.publish_revision(
            make_publish(world_id=world_id, payload={"world_id": world_id, "nodes": []})
        )
    heads = bundle.world_graph.list_heads()
    assert [head.world_id for head in heads] == ["world:alpha", "world:mid", "world:zebra"]
    first = heads[0]
    canonical = bundle.world_graph.get_head(first.world_id)
    assert canonical is not None
    first.head_revision_id = "rev:mutated"
    again = bundle.world_graph.get_head(first.world_id)
    assert again is not None
    assert again.head_revision_id == canonical.head_revision_id


def existing_world_list_world_ids_empty(bundle: EnumerationBundle) -> None:
    assert bundle.existing_world_adoptions.list_world_ids() == []


def _adopt_world(bundle: EnumerationBundle, *, world_id: str, token: str) -> None:
    isolated = make_isolated_bundle(
        world_id=world_id,
        adoption_id=f"adopt:{token}",
        token=token,
    )
    adopt_existing_world(
        existing_world_adoption_bundle_canonical_bytes(isolated),
        adopted_at=NOW,
        adoption_repository=bundle.existing_world_adoptions,
        graph_reader=adoption_graph_reader(),
    )


def existing_world_list_world_ids_sorted_repeatable_readonly(
    bundle: EnumerationBundle,
) -> None:
    _adopt_world(bundle, world_id="world:zebra", token="zebra")
    _adopt_world(bundle, world_id="world:alpha", token="alpha")
    first = bundle.existing_world_adoptions.list_world_ids()
    second = bundle.existing_world_adoptions.list_world_ids()
    assert first == second == ["world:alpha", "world:zebra"]
    first.append("world:intruder")
    assert bundle.existing_world_adoptions.list_world_ids() == ["world:alpha", "world:zebra"]


def reviewed_init_list_world_ids_empty(bundle: EnumerationBundle) -> None:
    assert bundle.reviewed_world_initializations.list_world_ids() == []


def _initialize_world(bundle: EnumerationBundle, *, world_id: str, token: str) -> None:
    art_id = f"src:notes-{token}"
    rev_id = f"srcrev:notes-{token}-v1"
    artifact = init_artifact(world_id=world_id).model_copy(
        update={"source_artifact_id": art_id, "current_revision_id": rev_id}
    )
    revision = init_revision().model_copy(
        update={"source_revision_id": rev_id, "source_artifact_id": art_id}
    )
    contribution = init_contribution(
        [
            init_node(
                assertion_id=f"asrt:college:{token}",
                object_id=f"obj:college:{token}",
                source_artifact_id=art_id,
                source_revision_id=rev_id,
            ),
            init_node(
                assertion_id=f"asrt:headmaster:{token}",
                object_id=f"obj:headmaster:{token}",
                kind="test:person",
                label="Headmaster",
                source_artifact_id=art_id,
                source_revision_id=rev_id,
            ),
            init_edge(
                assertion_id=f"asrt:leads:{token}",
                subject=f"obj:headmaster:{token}",
                target=f"obj:college:{token}",
                edge_id=f"rel:leads:{token}",
                source_artifact_id=art_id,
                source_revision_id=rev_id,
            ),
        ],
        world_id=world_id,
    ).model_copy(
        update={
            "contribution_id": f"contrib:init:{token}",
            "source_artifact_id": art_id,
            "source_revision_id": rev_id,
        }
    )
    initialize_reviewed_world(
        make_init_command(
            world_id=world_id,
            initialization_id=f"init:{token}",
            artifacts=[artifact],
            revisions=[revision],
            contribution=contribution,
        ),
        initialization_repository=bundle.reviewed_world_initializations,
        graph_reader=init_graph_reader(),
    )


def reviewed_init_list_world_ids_sorted_repeatable_readonly(
    bundle: EnumerationBundle,
) -> None:
    _initialize_world(bundle, world_id="world:zebra", token="zebra")
    _initialize_world(bundle, world_id="world:alpha", token="alpha")
    first = bundle.reviewed_world_initializations.list_world_ids()
    second = bundle.reviewed_world_initializations.list_world_ids()
    assert first == second == ["world:alpha", "world:zebra"]
    first.append("world:intruder")
    assert bundle.reviewed_world_initializations.list_world_ids() == [
        "world:alpha",
        "world:zebra",
    ]


CASES: list[tuple[str, Callable[[EnumerationBundle], None]]] = [
    ("list_heads_empty", list_heads_empty),
    ("list_heads_sorted_deterministic_copy_safe", list_heads_sorted_deterministic_copy_safe),
    ("existing_world_list_world_ids_empty", existing_world_list_world_ids_empty),
    (
        "existing_world_list_world_ids_sorted_repeatable_readonly",
        existing_world_list_world_ids_sorted_repeatable_readonly,
    ),
    ("reviewed_init_list_world_ids_empty", reviewed_init_list_world_ids_empty),
    (
        "reviewed_init_list_world_ids_sorted_repeatable_readonly",
        reviewed_init_list_world_ids_sorted_repeatable_readonly,
    ),
]
