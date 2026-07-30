"""PostgreSQL connection and transaction boundary (Psycopg 3).

No client, pool, or environment lookup occurs at module import time.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg import Connection, sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ...domain.errors import PersistenceIntegrityError, PersistenceUnavailableError

SCHEMA = "dungeonmind"


def _map_driver_error(exc: BaseException) -> None:
    """Re-raise domain persistence errors; never leak Psycopg types upward."""
    if isinstance(exc, (PersistenceUnavailableError, PersistenceIntegrityError)):
        raise exc
    if isinstance(exc, (psycopg.OperationalError, psycopg.InterfaceError)):
        raise PersistenceUnavailableError(str(exc)) from exc
    if isinstance(exc, psycopg.Error):
        raise PersistenceIntegrityError(str(exc)) from exc


class PostgresDatabase:
    """Explicit connection factory. Constructed by callers with a DSN string."""

    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ValueError("database_url must be a non-empty PostgreSQL DSN")
        self._database_url = database_url

    def connect(self) -> Connection[Any]:
        try:
            conn = psycopg.connect(self._database_url, row_factory=dict_row)
        except Exception as exc:
            _map_driver_error(exc)
            raise
        return conn

    @contextmanager
    def transaction(self) -> Iterator[Connection[Any]]:
        try:
            with self.connect() as conn, conn.transaction():
                yield conn
        except Exception as exc:
            _map_driver_error(exc)
            raise


def jsonb(value: Any) -> Jsonb:
    return Jsonb(value)


def ensure_world(conn: Connection[Any], world_id: str, *, created_at: datetime) -> None:
    conn.execute(
        sql.SQL(
            """
            INSERT INTO {}.worlds (world_id, created_at)
            VALUES (%s, %s)
            ON CONFLICT (world_id) DO NOTHING
            """
        ).format(sql.Identifier(SCHEMA)),
        (world_id, created_at),
    )


def ensure_campaign(
    conn: Connection[Any],
    world_id: str,
    campaign_id: str,
    *,
    created_at: datetime,
) -> None:
    ensure_world(conn, world_id, created_at=created_at)
    conn.execute(
        sql.SQL(
            """
            INSERT INTO {}.campaigns (world_id, campaign_id, created_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (world_id, campaign_id) DO NOTHING
            """
        ).format(sql.Identifier(SCHEMA)),
        (world_id, campaign_id, created_at),
    )


def lock_world(conn: Connection[Any], world_id: str, *, created_at: datetime) -> None:
    """Per-world lock anchor used by graph publication and rollback."""
    ensure_world(conn, world_id, created_at=created_at)
    row = conn.execute(
        sql.SQL(
            """
            SELECT world_id FROM {}.worlds
            WHERE world_id = %s
            FOR UPDATE
            """
        ).format(sql.Identifier(SCHEMA)),
        (world_id,),
    ).fetchone()
    if row is None:
        raise PersistenceIntegrityError(f"world row missing after ensure: {world_id!r}")


def utcnow() -> datetime:
    return datetime.now(tz=UTC)
