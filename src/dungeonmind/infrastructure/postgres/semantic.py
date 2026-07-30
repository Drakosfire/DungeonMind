"""PostgreSQL adapters for embedding runs, semantic documents, and search."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pgvector.psycopg import register_vector
from psycopg import Connection, sql

from ...contracts.semantic import (
    CandidateChannel,
    EmbeddingRun,
    EmbeddingRunStatus,
    SemanticCandidate,
    SemanticDocument,
    SemanticQuery,
)
from ...contracts.vocabulary import Visibility
from ...domain.errors import (
    DocumentNotFoundError,
    IdempotencyConflictError,
    InvalidLifecycleTransitionError,
    PersistenceIntegrityError,
    ScopeResolutionError,
)
from .database import SCHEMA, PostgresDatabase, jsonb, utcnow
from .serialization import dump_payload, immutable_run_fingerprint, model_fingerprint, reconstruct


def _row_to_embedding_run(row: dict[str, Any]) -> EmbeddingRun:
    return reconstruct(
        EmbeddingRun,
        dict(row["payload"]),
        expected_fingerprint=row["record_fingerprint"],
        identity={"run_id": row["run_id"]},
    )


def _lock_embedding_run(conn: Connection[Any], run_id: str) -> dict[str, Any] | None:
    return conn.execute(
        sql.SQL(
            """
            SELECT *
            FROM {}.embedding_runs
            WHERE run_id = %s
            FOR UPDATE
            """
        ).format(sql.Identifier(SCHEMA)),
        (run_id,),
    ).fetchone()


def _persist_embedding_run(conn: Connection[Any], run: EmbeddingRun) -> None:
    conn.execute(
        sql.SQL(
            """
            UPDATE {}.embedding_runs
            SET status = %s,
                completed_at = %s,
                record_fingerprint = %s,
                payload = %s
            WHERE run_id = %s
            """
        ).format(sql.Identifier(SCHEMA)),
        (
            run.status.value,
            run.completed_at,
            model_fingerprint(run),
            jsonb(dump_payload(run)),
            run.run_id,
        ),
    )


def _assert_run_compatible(doc: SemanticDocument, run: EmbeddingRun) -> None:
    if doc.embedding_model != run.embedding_model:
        raise IdempotencyConflictError(
            f"document {doc.semantic_document_id!r} embedding_model mismatches run"
        )
    if doc.embedding_model_revision != run.embedding_model_revision:
        raise IdempotencyConflictError(
            f"document {doc.semantic_document_id!r} embedding_model_revision "
            "mismatches run"
        )
    if doc.embedding_dimensions != run.embedding_dimensions:
        raise IdempotencyConflictError(
            f"document {doc.semantic_document_id!r} embedding_dimensions mismatches run"
        )
    if doc.embedding_recipe != run.embedding_recipe:
        raise IdempotencyConflictError(
            f"document {doc.semantic_document_id!r} embedding_recipe mismatches run"
        )
    if run.world_id is not None and doc.world_id != run.world_id:
        raise IdempotencyConflictError(
            f"document {doc.semantic_document_id!r} world_id incompatible with run"
        )


def _embedding_to_list(embedding: Any) -> list[float]:
    """Normalize a pgvector Vector / sequence into a plain float list."""
    if embedding is None:
        return []
    if hasattr(embedding, "to_list"):
        return [float(x) for x in embedding.to_list()]
    if hasattr(embedding, "tolist"):
        return [float(x) for x in embedding.tolist()]
    return [float(x) for x in embedding]


def _row_to_semantic_document(row: dict[str, Any]) -> SemanticDocument:
    payload = dict(row["payload"])
    if row["embedding"] is not None:
        payload["embedding"] = _embedding_to_list(row["embedding"])
    return reconstruct(
        SemanticDocument,
        payload,
        expected_fingerprint=row["record_fingerprint"],
        identity={"semantic_document_id": row["semantic_document_id"]},
    )


def _doc_filter_sql(
    query: SemanticQuery, run_id: str
) -> tuple[sql.Composable, list[Any]]:
    conditions: list[sql.Composable] = [
        sql.SQL("world_id = %s"),
        sql.SQL("materialization_run_id = %s"),
    ]
    params: list[Any] = [query.world_id, run_id]
    if query.campaign_scope is not None:
        conditions.append(sql.SQL("(campaign_scope IS NULL OR campaign_scope = %s)"))
        params.append(query.campaign_scope)
    else:
        conditions.append(sql.SQL("campaign_scope IS NULL"))
    if query.visibility is Visibility.PLAYER:
        conditions.append(sql.SQL("visibility = %s"))
        params.append(Visibility.PLAYER.value)
    if query.document_kind is not None:
        conditions.append(sql.SQL("document_kind = %s"))
        params.append(query.document_kind.value)
    if query.graph_revision_id is not None:
        conditions.append(sql.SQL("graph_revision_id = %s"))
        params.append(query.graph_revision_id)
    return sql.SQL(" AND ").join(conditions), params


class PostgresEmbeddingRunRepository:
    """Materialization run lifecycle with row-level locking."""

    def __init__(self, database: PostgresDatabase) -> None:
        self._db = database

    def begin(self, run: EmbeddingRun) -> EmbeddingRun:
        if run.status is not EmbeddingRunStatus.RUNNING:
            raise InvalidLifecycleTransitionError(
                record_type="embedding_run",
                record_id=run.run_id,
                current_status=run.status.value,
                requested_status=EmbeddingRunStatus.RUNNING.value,
            )
        if run.completed_at is not None:
            raise InvalidLifecycleTransitionError(
                "begin rejects terminal timestamps on input",
                record_type="embedding_run",
                record_id=run.run_id,
                current_status=run.status.value,
                requested_status=EmbeddingRunStatus.RUNNING.value,
            )
        immutable_fp = immutable_run_fingerprint(run)
        with self._db.transaction() as conn:
            existing = _lock_embedding_run(conn, run.run_id)
            if existing is not None:
                if existing["immutable_fingerprint"] != immutable_fp:
                    raise IdempotencyConflictError(
                        f"embedding run {run.run_id!r} replayed with different "
                        "immutable creation metadata"
                    )
                return _row_to_embedding_run(existing)
            conn.execute(
                sql.SQL(
                    """
                    INSERT INTO {}.embedding_runs (
                        run_id,
                        world_id,
                        embedding_model,
                        embedding_model_revision,
                        embedding_dimensions,
                        embedding_recipe,
                        corpus_fingerprint,
                        benchmark_projection_id,
                        status,
                        created_at,
                        completed_at,
                        schema_version,
                        immutable_fingerprint,
                        record_fingerprint,
                        payload
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """
                ).format(sql.Identifier(SCHEMA)),
                (
                    run.run_id,
                    run.world_id,
                    run.embedding_model,
                    run.embedding_model_revision,
                    run.embedding_dimensions,
                    run.embedding_recipe,
                    run.corpus_fingerprint,
                    run.benchmark_projection_id,
                    run.status.value,
                    run.created_at,
                    run.completed_at,
                    run.schema_version,
                    immutable_fp,
                    model_fingerprint(run),
                    jsonb(dump_payload(run)),
                ),
            )
            return run.model_copy(deep=True)

    def complete(self, run_id: str, *, completed_at: datetime) -> EmbeddingRun:
        with self._db.transaction() as conn:
            row = _lock_embedding_run(conn, run_id)
            if row is None:
                raise DocumentNotFoundError(f"embedding run {run_id!r} not found")
            existing = _row_to_embedding_run(row)
            if existing.status is EmbeddingRunStatus.COMPLETED:
                return existing
            if existing.status is not EmbeddingRunStatus.RUNNING:
                raise InvalidLifecycleTransitionError(
                    record_type="embedding_run",
                    record_id=run_id,
                    current_status=existing.status.value,
                    requested_status=EmbeddingRunStatus.COMPLETED.value,
                )
            updated = existing.model_copy(
                update={
                    "status": EmbeddingRunStatus.COMPLETED,
                    "completed_at": completed_at,
                }
            )
            _persist_embedding_run(conn, updated)
            return updated

    def fail(self, run_id: str, *, completed_at: datetime) -> EmbeddingRun:
        with self._db.transaction() as conn:
            row = _lock_embedding_run(conn, run_id)
            if row is None:
                raise DocumentNotFoundError(f"embedding run {run_id!r} not found")
            existing = _row_to_embedding_run(row)
            if existing.status is EmbeddingRunStatus.FAILED:
                return existing
            if existing.status is not EmbeddingRunStatus.RUNNING:
                raise InvalidLifecycleTransitionError(
                    record_type="embedding_run",
                    record_id=run_id,
                    current_status=existing.status.value,
                    requested_status=EmbeddingRunStatus.FAILED.value,
                )
            updated = existing.model_copy(
                update={
                    "status": EmbeddingRunStatus.FAILED,
                    "completed_at": completed_at,
                }
            )
            _persist_embedding_run(conn, updated)
            return updated

    def supersede(self, run_id: str, *, completed_at: datetime) -> EmbeddingRun:
        with self._db.transaction() as conn:
            row = _lock_embedding_run(conn, run_id)
            if row is None:
                raise DocumentNotFoundError(f"embedding run {run_id!r} not found")
            existing = _row_to_embedding_run(row)
            if existing.status is EmbeddingRunStatus.SUPERSEDED:
                return existing
            if existing.status not in (
                EmbeddingRunStatus.COMPLETED,
                EmbeddingRunStatus.FAILED,
            ):
                raise InvalidLifecycleTransitionError(
                    record_type="embedding_run",
                    record_id=run_id,
                    current_status=existing.status.value,
                    requested_status=EmbeddingRunStatus.SUPERSEDED.value,
                )
            updated = existing.model_copy(
                update={
                    "status": EmbeddingRunStatus.SUPERSEDED,
                    "completed_at": completed_at,
                }
            )
            _persist_embedding_run(conn, updated)
            if existing.world_id is not None:
                conn.execute(
                    sql.SQL(
                        """
                        DELETE FROM {}.active_embedding_runs
                        WHERE world_id = %s AND run_id = %s
                        """
                    ).format(sql.Identifier(SCHEMA)),
                    (existing.world_id, run_id),
                )
            return updated

    def activate(self, run_id: str) -> EmbeddingRun:
        with self._db.transaction() as conn:
            row = _lock_embedding_run(conn, run_id)
            if row is None:
                raise DocumentNotFoundError(f"embedding run {run_id!r} not found")
            existing = _row_to_embedding_run(row)
            if existing.status is not EmbeddingRunStatus.COMPLETED:
                raise InvalidLifecycleTransitionError(
                    (
                        "activate requires a COMPLETED embedding run; "
                        f"{run_id!r} is {existing.status.value}"
                    ),
                    record_type="embedding_run",
                    record_id=run_id,
                    current_status=existing.status.value,
                    requested_status="activate",
                )
            if existing.world_id is None:
                raise ScopeResolutionError(
                    f"embedding run {run_id!r} has no world_id; cannot activate",
                    details={"run_id": run_id, "reason": "missing_world_id"},
                )
            conn.execute(
                sql.SQL(
                    """
                    INSERT INTO {}.active_embedding_runs (world_id, run_id, activated_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (world_id) DO UPDATE
                    SET run_id = EXCLUDED.run_id,
                        activated_at = EXCLUDED.activated_at
                    """
                ).format(sql.Identifier(SCHEMA)),
                (existing.world_id, run_id, utcnow()),
            )
            return existing

    def get_active_run_id(self, world_id: str) -> str | None:
        with self._db.transaction() as conn:
            row = conn.execute(
                sql.SQL(
                    """
                    SELECT run_id FROM {}.active_embedding_runs
                    WHERE world_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (world_id,),
            ).fetchone()
            return None if row is None else row["run_id"]

    def get(self, run_id: str) -> EmbeddingRun | None:
        with self._db.transaction() as conn:
            row = conn.execute(
                sql.SQL(
                    """
                    SELECT * FROM {}.embedding_runs WHERE run_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (run_id,),
            ).fetchone()
            return None if row is None else _row_to_embedding_run(row)


class PostgresSemanticDocumentRepository:
    """Provenance-complete semantic document store backed by pgvector."""

    def __init__(self, database: PostgresDatabase) -> None:
        self._db = database

    def upsert_batch(self, documents: list[SemanticDocument]) -> int:
        if not documents:
            return 0
        with self._db.transaction() as conn:
            register_vector(conn)
            run_ids = sorted({doc.materialization_run_id for doc in documents})
            locked_runs: dict[str, EmbeddingRun] = {}
            for run_id in run_ids:
                row = _lock_embedding_run(conn, run_id)
                if row is None:
                    raise DocumentNotFoundError(f"materialization run {run_id!r} not found")
                locked_runs[run_id] = _row_to_embedding_run(row)

            to_insert: list[SemanticDocument] = []
            for doc in documents:
                _assert_run_compatible(doc, locked_runs[doc.materialization_run_id])
                existing = conn.execute(
                    sql.SQL(
                        """
                        SELECT
                            semantic_document_id,
                            record_fingerprint,
                            payload,
                            embedding
                        FROM {}.semantic_documents
                        WHERE semantic_document_id = %s
                        FOR UPDATE
                        """
                    ).format(sql.Identifier(SCHEMA)),
                    (doc.semantic_document_id,),
                ).fetchone()
                if existing is not None:
                    stored = _row_to_semantic_document(existing)
                    if model_fingerprint(stored) != model_fingerprint(doc):
                        raise IdempotencyConflictError(
                            f"semantic document {doc.semantic_document_id!r} re-ingested with "
                            "different payload; re-embedding must create a new run and new "
                            "document ids (ADR-0003)"
                        )
                    continue
                run = locked_runs[doc.materialization_run_id]
                if run.status is not EmbeddingRunStatus.RUNNING:
                    raise InvalidLifecycleTransitionError(
                        (
                            "new semantic documents require a RUNNING materialization "
                            f"run; {run.run_id!r} is {run.status.value}"
                        ),
                        record_type="embedding_run",
                        record_id=run.run_id,
                        current_status=run.status.value,
                        requested_status="accept_document",
                    )
                to_insert.append(doc)

            if not to_insert:
                return 0

            for doc in to_insert:
                run = locked_runs[doc.materialization_run_id]
                if run.status is not EmbeddingRunStatus.RUNNING:
                    raise InvalidLifecycleTransitionError(
                        (
                            "new semantic documents require a RUNNING materialization "
                            f"run; {run.run_id!r} is {run.status.value}"
                        ),
                        record_type="embedding_run",
                        record_id=run.run_id,
                        current_status=run.status.value,
                        requested_status="accept_document",
                    )
                if doc.embedding is not None and len(doc.embedding) != doc.embedding_dimensions:
                    raise PersistenceIntegrityError(
                        f"document {doc.semantic_document_id!r} embedding length "
                        f"{len(doc.embedding)} != embedding_dimensions "
                        f"{doc.embedding_dimensions}"
                    )
                fingerprint = model_fingerprint(doc)
                conn.execute(
                    sql.SQL(
                        """
                        INSERT INTO {}.semantic_documents (
                            semantic_document_id,
                            document_kind,
                            world_id,
                            campaign_scope,
                            graph_revision_id,
                            graph_object_id,
                            source_artifact_id,
                            source_revision_id,
                            session_id,
                            visibility,
                            content,
                            content_sha256,
                            embedding_model,
                            embedding_model_revision,
                            embedding_dimensions,
                            embedding_recipe,
                            materialization_run_id,
                            created_at,
                            schema_version,
                            record_fingerprint,
                            payload,
                            embedding
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        """
                    ).format(sql.Identifier(SCHEMA)),
                    (
                        doc.semantic_document_id,
                        doc.document_kind.value,
                        doc.world_id,
                        doc.campaign_scope,
                        doc.graph_revision_id,
                        doc.graph_object_id,
                        doc.source_artifact_id,
                        doc.source_revision_id,
                        doc.session_id,
                        doc.visibility.value,
                        doc.content,
                        doc.content_sha256,
                        doc.embedding_model,
                        doc.embedding_model_revision,
                        doc.embedding_dimensions,
                        doc.embedding_recipe,
                        doc.materialization_run_id,
                        doc.created_at,
                        doc.schema_version,
                        fingerprint,
                        jsonb(dump_payload(doc, exclude={"embedding"})),
                        doc.embedding,
                    ),
                )
            return len(to_insert)

    def get(self, semantic_document_id: str) -> SemanticDocument | None:
        with self._db.transaction() as conn:
            register_vector(conn)
            row = conn.execute(
                sql.SQL(
                    """
                    SELECT
                        semantic_document_id,
                        record_fingerprint,
                        payload,
                        embedding
                    FROM {}.semantic_documents
                    WHERE semantic_document_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (semantic_document_id,),
            ).fetchone()
            if row is None:
                return None
            doc = _row_to_semantic_document(row)
            return doc.model_copy(deep=True)

    def delete_run_documents(self, materialization_run_id: str) -> int:
        with self._db.transaction() as conn:
            row = _lock_embedding_run(conn, materialization_run_id)
            if row is None:
                raise DocumentNotFoundError(
                    f"embedding run {materialization_run_id!r} not found"
                )
            run = _row_to_embedding_run(row)
            if run.status not in (
                EmbeddingRunStatus.FAILED,
                EmbeddingRunStatus.SUPERSEDED,
            ):
                raise InvalidLifecycleTransitionError(
                    (
                        "delete_run_documents requires a FAILED or SUPERSEDED "
                        f"run; {materialization_run_id!r} is {run.status.value}"
                    ),
                    record_type="embedding_run",
                    record_id=materialization_run_id,
                    current_status=run.status.value,
                    requested_status="delete_documents",
                )
            result = conn.execute(
                sql.SQL(
                    """
                    DELETE FROM {}.semantic_documents
                    WHERE materialization_run_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (materialization_run_id,),
            )
            return result.rowcount

    def count(self, *, world_id: str | None = None) -> int:
        with self._db.transaction() as conn:
            if world_id is None:
                row = conn.execute(
                    sql.SQL(
                        """
                        SELECT COUNT(*) AS n FROM {}.semantic_documents
                        """
                    ).format(sql.Identifier(SCHEMA)),
                ).fetchone()
            else:
                row = conn.execute(
                    sql.SQL(
                        """
                        SELECT COUNT(*) AS n FROM {}.semantic_documents
                        WHERE world_id = %s
                        """
                    ).format(sql.Identifier(SCHEMA)),
                    (world_id,),
                ).fetchone()
            return int(row["n"]) if row is not None else 0


class PostgresSemanticSearch:
    """Candidate retrieval over semantic documents (no fusion)."""

    def __init__(self, database: PostgresDatabase) -> None:
        self._db = database

    def search(self, query: SemanticQuery) -> list[SemanticCandidate]:
        with self._db.transaction() as conn:
            register_vector(conn)
            run_id = self._resolve_retrieval_run(conn, query)
            candidates: list[SemanticCandidate] = []
            where_clause, params = _doc_filter_sql(query, run_id)

            if query.text:
                exact_rows = conn.execute(
                    sql.SQL(
                        """
                        SELECT semantic_document_id, content, graph_object_id
                        FROM {}.semantic_documents
                        WHERE {}
                        """
                    ).format(sql.Identifier(SCHEMA), where_clause),
                    params,
                ).fetchall()
                exact = [
                    (row["semantic_document_id"], 1.0)
                    for row in exact_rows
                    if query.text.casefold() in row["content"].casefold()
                    or query.text == row["semantic_document_id"]
                    or query.text == row["graph_object_id"]
                ]
                candidates.extend(
                    _ranked(exact, CandidateChannel.EXACT, query.top_k)
                )

            if query.text:
                lexical_rows = conn.execute(
                    sql.SQL(
                        """
                        SELECT semantic_document_id,
                               ts_rank_cd(
                                   search_tsv,
                                   plainto_tsquery('simple', %s)
                               ) AS score
                        FROM {}.semantic_documents
                        WHERE {}
                          AND search_tsv @@ plainto_tsquery('simple', %s)
                        ORDER BY score DESC, semantic_document_id ASC
                        LIMIT %s
                        """
                    ).format(sql.Identifier(SCHEMA), where_clause),
                    [query.text, *params, query.text, query.top_k],
                ).fetchall()
                lexical_scored = [
                    (row["semantic_document_id"], float(row["score"]))
                    for row in lexical_rows
                ]
                candidates.extend(
                    _ranked(lexical_scored, CandidateChannel.LEXICAL, query.top_k)
                )

            if query.embedding:
                run_row = conn.execute(
                    sql.SQL(
                        """
                        SELECT embedding_dimensions
                        FROM {}.embedding_runs
                        WHERE run_id = %s
                        """
                    ).format(sql.Identifier(SCHEMA)),
                    (run_id,),
                ).fetchone()
                dimensions = run_row["embedding_dimensions"] if run_row is not None else None
                if dimensions is not None and len(query.embedding) == dimensions:
                    dense_rows = conn.execute(
                        sql.SQL(
                            """
                            SELECT semantic_document_id,
                                   1 - (embedding <=> %s::vector) AS score
                            FROM {}.semantic_documents
                            WHERE {}
                              AND embedding IS NOT NULL
                            ORDER BY score DESC, semantic_document_id ASC
                            LIMIT %s
                            """
                        ).format(sql.Identifier(SCHEMA), where_clause),
                        [query.embedding, *params, query.top_k],
                    ).fetchall()
                    candidates.extend(
                        _ranked(
                            [
                                (row["semantic_document_id"], float(row["score"]))
                                for row in dense_rows
                            ],
                            CandidateChannel.DENSE,
                            query.top_k,
                        )
                    )

            return candidates

    def _resolve_retrieval_run(self, conn: Connection[Any], query: SemanticQuery) -> str:
        run_id = query.materialization_run_id
        if run_id is None:
            active = conn.execute(
                sql.SQL(
                    """
                    SELECT run_id FROM {}.active_embedding_runs
                    WHERE world_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (query.world_id,),
            ).fetchone()
            if active is None:
                raise ScopeResolutionError(
                    f"no materialization run bound for world {query.world_id!r}",
                    details={
                        "world_id": query.world_id,
                        "reason": "missing_active_materialization_run",
                    },
                )
            run_id = active["run_id"]

        row = _lock_embedding_run(conn, run_id)
        if row is None:
            raise DocumentNotFoundError(f"embedding run {run_id!r} not found")
        run = _row_to_embedding_run(row)
        if run.status is not EmbeddingRunStatus.COMPLETED:
            raise ScopeResolutionError(
                (
                    f"retrieval requires a COMPLETED materialization run; "
                    f"{run_id!r} is {run.status.value}"
                ),
                details={
                    "world_id": query.world_id,
                    "run_id": run_id,
                    "status": run.status.value,
                    "reason": "materialization_run_not_retrieval_eligible",
                },
            )
        if run.world_id is not None and run.world_id != query.world_id:
            raise ScopeResolutionError(
                (
                    f"materialization run {run_id!r} world {run.world_id!r} "
                    f"does not match query world {query.world_id!r}"
                ),
                details={
                    "world_id": query.world_id,
                    "run_id": run_id,
                    "run_world_id": run.world_id,
                    "reason": "materialization_run_world_mismatch",
                },
            )
        return run_id


def _ranked(
    scored: list[tuple[str, float]], channel: CandidateChannel, top_k: int
) -> list[SemanticCandidate]:
    ordered = sorted(scored, key=lambda kv: (-kv[1], kv[0]))[:top_k]
    return [
        SemanticCandidate(
            semantic_document_id=doc_id, channel=channel, rank=rank, score=score
        )
        for rank, (doc_id, score) in enumerate(ordered, start=1)
    ]
