"""PostgreSQL proofs for read-only authority enumeration repository ports."""

from __future__ import annotations

import pytest

from tests.conformance.authority_enumeration_contract_cases import CASES, EnumerationBundle
from tests.conftest import make_publish

pytestmark = pytest.mark.integration


def _enumeration_bundle(pg) -> EnumerationBundle:
    return EnumerationBundle(
        world_graph=pg.world_graph,
        existing_world_adoptions=pg.existing_world_adoptions,
        reviewed_world_initializations=pg.reviewed_world_initializations,
    )


def _table_counts(conn, *, world_ids: tuple[str, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for world_id in world_ids:
        for table, column in (
            ("world_graph_heads", "world_id"),
            ("world_graph_head_events", "world_id"),
            ("graph_revisions", "world_id"),
            ("existing_world_adoptions", "world_id"),
            ("reviewed_world_initializations", "world_id"),
        ):
            key = f"{table}:{world_id}"
            row = conn.execute(
                f"SELECT COUNT(*) AS count FROM dungeonmind.{table} WHERE {column} = %s",
                (world_id,),
            ).fetchone()
            counts[key] = int(row["count"])
    return counts


@pytest.mark.conformance
@pytest.mark.parametrize("case_name,case_fn", CASES, ids=[name for name, _ in CASES])
def test_postgres_authority_enumeration_conformance(case_name: str, case_fn, pg) -> None:
    del case_name
    case_fn(_enumeration_bundle(pg))


def test_postgres_enumeration_ports_are_read_only_witness(pg) -> None:
    """Enumeration calls must not mutate durable rows."""
    bundle = _enumeration_bundle(pg)

    from tests.conformance.authority_enumeration_contract_cases import (
        _adopt_world,
        _initialize_world,
    )

    # Separate worlds per enumeration surface: heads require published revisions,
    # while adoption and reviewed-init require pristine targets.
    head_worlds = ("world:head-alpha", "world:head-zebra")
    adopt_world = "world:adopt-alpha"
    init_world = "world:init-zebra"
    world_ids = (*head_worlds, adopt_world, init_world)

    for world_id in head_worlds:
        bundle.world_graph.publish_revision(
            make_publish(world_id=world_id, payload={"world_id": world_id, "nodes": []})
        )
    _adopt_world(bundle, world_id=adopt_world, token="adopt-alpha")
    _initialize_world(bundle, world_id=init_world, token="init-zebra")

    with pg.database.connect() as conn:
        before = _table_counts(conn, world_ids=world_ids)

    heads = bundle.world_graph.list_heads()
    assert [head.world_id for head in heads] == sorted(head_worlds)
    assert bundle.existing_world_adoptions.list_world_ids() == [adopt_world]
    assert bundle.reviewed_world_initializations.list_world_ids() == [init_world]

    with pg.database.connect() as conn:
        after = _table_counts(conn, world_ids=world_ids)
    assert before == after
