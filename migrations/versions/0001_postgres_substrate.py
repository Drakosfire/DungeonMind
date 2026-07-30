"""Initial DungeonMind PostgreSQL/pgvector substrate schema.

Revision ID: 0001_postgres_substrate
Revises:
Create Date: 2026-07-30
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001_postgres_substrate"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "dungeonmind"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.worlds (
            world_id text PRIMARY KEY,
            created_at timestamptz NOT NULL
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.campaigns (
            world_id text NOT NULL REFERENCES {SCHEMA}.worlds (world_id),
            campaign_id text NOT NULL,
            created_at timestamptz NOT NULL,
            PRIMARY KEY (world_id, campaign_id)
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.graph_revisions (
            world_id text NOT NULL REFERENCES {SCHEMA}.worlds (world_id),
            revision_id text NOT NULL,
            parent_revision_id text,
            created_at timestamptz NOT NULL,
            graph_schema text NOT NULL,
            graph_payload_sha256 text NOT NULL,
            schema_version text NOT NULL,
            record_fingerprint text NOT NULL,
            revision_payload jsonb NOT NULL,
            graph_payload jsonb NOT NULL,
            PRIMARY KEY (world_id, revision_id)
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.world_graph_heads (
            world_id text PRIMARY KEY REFERENCES {SCHEMA}.worlds (world_id),
            head_revision_id text NOT NULL,
            updated_at timestamptz NOT NULL,
            schema_version text NOT NULL,
            FOREIGN KEY (world_id, head_revision_id)
                REFERENCES {SCHEMA}.graph_revisions (world_id, revision_id)
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.world_graph_head_events (
            event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            world_id text NOT NULL REFERENCES {SCHEMA}.worlds (world_id),
            event_kind text NOT NULL CHECK (event_kind IN ('publish', 'rollback')),
            previous_revision_id text,
            target_revision_id text NOT NULL,
            occurred_at timestamptz NOT NULL
        )
        """
    )
    op.execute(
        f"CREATE INDEX world_graph_head_events_world_idx "
        f"ON {SCHEMA}.world_graph_head_events (world_id, event_id)"
    )

    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.source_artifacts (
            source_artifact_id text PRIMARY KEY,
            world_id text NOT NULL REFERENCES {SCHEMA}.worlds (world_id),
            campaign_id text,
            session_id text,
            source_domain text NOT NULL,
            status text NOT NULL,
            visibility text NOT NULL,
            current_revision_id text,
            created_at timestamptz NOT NULL,
            schema_version text NOT NULL,
            record_fingerprint text NOT NULL,
            payload jsonb NOT NULL
        )
        """
    )
    op.execute(
        f"CREATE INDEX source_artifacts_world_idx "
        f"ON {SCHEMA}.source_artifacts (world_id)"
    )

    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.source_revisions (
            source_revision_id text PRIMARY KEY,
            source_artifact_id text NOT NULL,
            content_sha256 text NOT NULL,
            body_storage text NOT NULL,
            locator text,
            created_at timestamptz NOT NULL,
            schema_version text NOT NULL,
            record_fingerprint text NOT NULL,
            payload jsonb NOT NULL
        )
        """
    )
    op.execute(
        f"CREATE INDEX source_revisions_artifact_idx "
        f"ON {SCHEMA}.source_revisions (source_artifact_id, source_revision_id)"
    )

    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.evidence_refs (
            evidence_ref_id text PRIMARY KEY,
            source_artifact_id text NOT NULL,
            source_revision_id text,
            source_domain text NOT NULL,
            evidence_role text NOT NULL,
            schema_version text NOT NULL,
            record_fingerprint text NOT NULL,
            payload jsonb NOT NULL
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.graph_contributions (
            world_id text NOT NULL REFERENCES {SCHEMA}.worlds (world_id),
            contribution_id text NOT NULL,
            source_kind text NOT NULL,
            status text NOT NULL,
            campaign_scope text,
            produced_at timestamptz NOT NULL,
            schema_version text NOT NULL,
            record_fingerprint text NOT NULL,
            payload jsonb NOT NULL,
            PRIMARY KEY (world_id, contribution_id)
        )
        """
    )
    op.execute(
        f"CREATE INDEX graph_contributions_world_status_idx "
        f"ON {SCHEMA}.graph_contributions (world_id, status, contribution_id)"
    )

    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.identity_decisions (
            world_id text NOT NULL REFERENCES {SCHEMA}.worlds (world_id),
            decision_id text NOT NULL,
            decision_kind text NOT NULL,
            status text NOT NULL,
            created_at timestamptz NOT NULL,
            schema_version text NOT NULL,
            record_fingerprint text NOT NULL,
            payload jsonb NOT NULL,
            PRIMARY KEY (world_id, decision_id)
        )
        """
    )
    op.execute(
        f"CREATE INDEX identity_decisions_world_idx "
        f"ON {SCHEMA}.identity_decisions (world_id, decision_id)"
    )

    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.retrieval_sessions (
            session_id text PRIMARY KEY,
            thread_id text,
            world_id text NOT NULL,
            revision_id text NOT NULL,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            schema_version text NOT NULL,
            record_fingerprint text NOT NULL,
            payload jsonb NOT NULL
        )
        """
    )
    op.execute(
        f"CREATE INDEX retrieval_sessions_world_idx "
        f"ON {SCHEMA}.retrieval_sessions (world_id, session_id)"
    )

    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.mind_threads (
            thread_id text PRIMARY KEY,
            world_id text NOT NULL,
            campaign_id text,
            caller_id text NOT NULL,
            tenant_id text,
            created_at timestamptz NOT NULL,
            binding_fingerprint text NOT NULL
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.mind_turns (
            thread_id text NOT NULL REFERENCES {SCHEMA}.mind_threads (thread_id),
            turn_id text NOT NULL,
            request_id text NOT NULL,
            ordinal bigint GENERATED ALWAYS AS IDENTITY,
            request_fingerprint text NOT NULL,
            response_fingerprint text NOT NULL,
            request_payload jsonb NOT NULL,
            response_payload jsonb NOT NULL,
            PRIMARY KEY (thread_id, turn_id),
            UNIQUE (thread_id, request_id)
        )
        """
    )
    op.execute(
        f"CREATE INDEX mind_turns_ordinal_idx "
        f"ON {SCHEMA}.mind_turns (thread_id, ordinal)"
    )

    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.embedding_runs (
            run_id text PRIMARY KEY,
            world_id text,
            embedding_model text NOT NULL,
            embedding_model_revision text NOT NULL,
            embedding_dimensions integer NOT NULL CHECK (embedding_dimensions > 0),
            embedding_recipe text NOT NULL,
            corpus_fingerprint text,
            benchmark_projection_id text,
            status text NOT NULL CHECK (
                status IN ('running', 'completed', 'failed', 'superseded')
            ),
            created_at timestamptz NOT NULL,
            completed_at timestamptz,
            schema_version text NOT NULL,
            immutable_fingerprint text NOT NULL,
            record_fingerprint text NOT NULL,
            payload jsonb NOT NULL,
            CHECK (
                (status = 'running' AND completed_at IS NULL)
                OR (status <> 'running' AND completed_at IS NOT NULL)
            )
        )
        """
    )
    op.execute(
        f"CREATE INDEX embedding_runs_world_status_idx "
        f"ON {SCHEMA}.embedding_runs (world_id, status)"
    )

    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.active_embedding_runs (
            world_id text PRIMARY KEY,
            run_id text NOT NULL UNIQUE REFERENCES {SCHEMA}.embedding_runs (run_id),
            activated_at timestamptz NOT NULL
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.semantic_documents (
            semantic_document_id text PRIMARY KEY,
            document_kind text NOT NULL,
            world_id text NOT NULL,
            campaign_scope text,
            graph_revision_id text,
            graph_object_id text,
            source_artifact_id text,
            source_revision_id text,
            session_id text,
            visibility text NOT NULL,
            content text NOT NULL,
            content_sha256 text NOT NULL,
            embedding_model text NOT NULL,
            embedding_model_revision text NOT NULL,
            embedding_dimensions integer NOT NULL CHECK (embedding_dimensions > 0),
            embedding_recipe text NOT NULL,
            materialization_run_id text NOT NULL
                REFERENCES {SCHEMA}.embedding_runs (run_id),
            created_at timestamptz NOT NULL,
            schema_version text NOT NULL,
            record_fingerprint text NOT NULL,
            payload jsonb NOT NULL,
            embedding vector,
            search_tsv tsvector GENERATED ALWAYS AS (
                to_tsvector('simple', coalesce(content, ''))
            ) STORED
        )
        """
    )
    op.execute(
        f"CREATE INDEX semantic_documents_run_idx "
        f"ON {SCHEMA}.semantic_documents (materialization_run_id)"
    )
    op.execute(
        f"CREATE INDEX semantic_documents_world_run_idx "
        f"ON {SCHEMA}.semantic_documents (world_id, materialization_run_id)"
    )
    op.execute(
        f"CREATE INDEX semantic_documents_campaign_idx "
        f"ON {SCHEMA}.semantic_documents (world_id, campaign_scope)"
    )
    op.execute(
        f"CREATE INDEX semantic_documents_visibility_idx "
        f"ON {SCHEMA}.semantic_documents (world_id, visibility)"
    )
    op.execute(
        f"CREATE INDEX semantic_documents_kind_idx "
        f"ON {SCHEMA}.semantic_documents (document_kind)"
    )
    op.execute(
        f"CREATE INDEX semantic_documents_graph_revision_idx "
        f"ON {SCHEMA}.semantic_documents (graph_revision_id)"
    )
    op.execute(
        f"CREATE INDEX semantic_documents_graph_object_idx "
        f"ON {SCHEMA}.semantic_documents (graph_object_id)"
    )
    op.execute(
        f"CREATE INDEX semantic_documents_search_tsv_idx "
        f"ON {SCHEMA}.semantic_documents USING GIN (search_tsv)"
    )


def downgrade() -> None:
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.semantic_documents CASCADE")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.active_embedding_runs CASCADE")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.embedding_runs CASCADE")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.mind_turns CASCADE")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.mind_threads CASCADE")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.retrieval_sessions CASCADE")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.identity_decisions CASCADE")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.graph_contributions CASCADE")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.evidence_refs CASCADE")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.source_revisions CASCADE")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.source_artifacts CASCADE")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.world_graph_head_events CASCADE")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.world_graph_heads CASCADE")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.graph_revisions CASCADE")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.campaigns CASCADE")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.worlds CASCADE")
    # Leave the schema (and alembic_version inside it) so downgrade can update
    # the version table. Leave the vector extension installed — DROP EXTENSION
    # is shared-cluster unsafe.
