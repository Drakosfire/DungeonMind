"""Mandatory durable profile policy/use authority under one profile fence."""

from __future__ import annotations

from typing import Any

from psycopg import Connection, errors, sql

from ...application.publication_admission import denied, profile_fence_key, profile_ref
from ...contracts.publication_admission import PublicationAdmissionPolicyV1, strict_contract_payload
from ...contracts.semantic_profile import SemanticProfileRef
from .database import SCHEMA, PostgresDatabase, jsonb


def _rows(conn: Connection[Any], ref: SemanticProfileRef) -> dict[str, Any] | None:
    try:
        rows = conn.execute(
            sql.SQL(
                "SELECT descriptor_sha256, policy_payload, protected_use "
                "FROM {}.publication_admission_profiles WHERE profile_id=%s AND profile_revision=%s"
            ).format(sql.Identifier(SCHEMA)),
            (ref.profile_id, ref.profile_revision),
        ).fetchone()
    except errors.UndefinedTable:
        denied("admission_policy_unavailable")
    if rows is not None and rows["descriptor_sha256"] != ref.descriptor_sha256:
        denied("admission_profile_conflict")
    return rows


def get_policy(
    conn: Connection[Any], ref: SemanticProfileRef | None
) -> PublicationAdmissionPolicyV1 | None:
    if ref is None:
        # Missing schema must never turn into an unprotected fallback even for
        # legacy input: the migration is a deployment prerequisite.
        try:
            conn.execute(
                sql.SQL("SELECT 1 FROM {}.publication_admission_profiles LIMIT 0").format(
                    sql.Identifier(SCHEMA)
                )
            )
        except errors.UndefinedTable:
            denied("admission_policy_unavailable")
        return None
    ref = profile_ref(ref)
    row = _rows(conn, ref)
    if row is None:
        return None
    raw = row["policy_payload"]
    if raw is None:
        if row["protected_use"] is True:
            denied("admission_policy_unavailable")
        return None
    try:
        policy = PublicationAdmissionPolicyV1.model_validate(raw)
    except Exception:
        denied("admission_policy_corrupt")
    if policy.profile_ref != ref:
        denied("admission_profile_conflict")
    return policy


def lock_profile(conn: Connection[Any], ref: SemanticProfileRef | None) -> None:
    if ref is not None:
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (profile_fence_key(ref),))


def record_profile_use(conn: Connection[Any], ref: SemanticProfileRef | None) -> None:
    lock_profile(conn, ref)
    policy = get_policy(conn, ref)
    if ref is None:
        return
    conn.execute(
        sql.SQL("""
        INSERT INTO {}.publication_admission_profiles
            (profile_id, profile_revision, descriptor_sha256, policy_payload, protected_use)
        VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT (profile_id, profile_revision) DO UPDATE
        SET protected_use=EXCLUDED.protected_use
    """).format(sql.Identifier(SCHEMA)),
        (
            ref.profile_id,
            ref.profile_revision,
            ref.descriptor_sha256,
            jsonb(policy.model_dump(mode="json")) if policy is not None else None,
            policy is not None,
        ),
    )


class PostgresPublicationAdmissionRepository:
    """Operator/bootstrap registration port; no mutation or override methods."""

    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def get(self, ref: SemanticProfileRef | None) -> PublicationAdmissionPolicyV1 | None:
        with self._database.transaction() as conn:
            return get_policy(conn, ref)

    def register(self, policy: PublicationAdmissionPolicyV1) -> PublicationAdmissionPolicyV1:
        policy = PublicationAdmissionPolicyV1.model_validate(strict_contract_payload(policy))
        ref = policy.profile_ref
        with self._database.transaction() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
            lock_profile(conn, ref)
            existing = get_policy(conn, ref)
            if existing is not None:
                if existing != policy:
                    denied("admission_policy_conflict")
                return existing
            if _rows(conn, ref) is not None:
                denied("admission_profile_already_used")
            conn.execute(
                sql.SQL("""
                INSERT INTO {}.publication_admission_profiles
                (profile_id,profile_revision,descriptor_sha256,policy_payload,protected_use)
                VALUES (%s,%s,%s,%s,NULL)
            """).format(sql.Identifier(SCHEMA)),
                (
                    ref.profile_id,
                    ref.profile_revision,
                    ref.descriptor_sha256,
                    jsonb(policy.model_dump(mode="json")),
                ),
            )
            return get_policy(conn, ref)
