# ruff: noqa: E501
"""Curated K0.1 dispositions. Derived facts stay in the scanner; this file records
evidence-backed classifications that AST cannot decide safely on its own.
"""

from __future__ import annotations

from typing import Any

# Path strings in overlays are repo-relative evidence locators.

# Repository protocol ids must match ClassDef names in application/repositories.py
# plus PostgresRepositoryBundle.
REPOSITORY_OVERLAY: dict[str, dict[str, Any]] = {
    "WorldGraphRepository": {
        "in_memory": "src/dungeonmind/infrastructure/memory/repositories.py:InMemoryWorldGraphRepository",
        "postgres": "src/dungeonmind/infrastructure/postgres/graph.py:PostgresWorldGraphRepository",
        "current_authority_paths": [
            "world_graph_read",
            "world_graph_write_publication",
            "reviewed_first_world_initialization",
            "existing_world_adoption",
        ],
        "founding_runtime_only_paths": [],
        "compatibility_only_paths": [],
        "disposition": "USED",
        "evidence": [
            "apps/live_control_server/integrations/dungeonmind/world_graph_reads.py",
            "src/dungeonmind/application/world_graph_projection.py",
            "src/dungeonmind/application/review_publication.py",
        ],
    },
    "SourceRepository": {
        "in_memory": "src/dungeonmind/infrastructure/memory/repositories.py:InMemorySourceRepository",
        "postgres": "src/dungeonmind/infrastructure/postgres/records.py:PostgresSourceRepository",
        "current_authority_paths": ["world_graph_read", "source_evidence", "world_graph_write_publication"],
        "founding_runtime_only_paths": [],
        "compatibility_only_paths": [],
        "disposition": "USED",
        "evidence": [
            "apps/live_control_server/integrations/dungeonmind/world_graph_source_admission_adapter.py",
            "src/dungeonmind/application/world_graph_retrieval.py",
        ],
    },
    "ContributionRepository": {
        "in_memory": "src/dungeonmind/infrastructure/memory/repositories.py:InMemoryContributionRepository",
        "postgres": "src/dungeonmind/infrastructure/postgres/records.py:PostgresContributionRepository",
        "current_authority_paths": ["world_graph_write_publication"],
        "founding_runtime_only_paths": [],
        "compatibility_only_paths": ["existing_world_adoption_membership"],
        "disposition": "USED",
        "evidence": [
            "apps/live_control_server/integrations/dungeonmind/world_graph_writes.py",
            "src/dungeonmind/application/review_publication.py",
        ],
    },
    "ContributionReviewRepository": {
        "in_memory": "src/dungeonmind/infrastructure/memory/repositories.py:InMemoryContributionReviewRepository",
        "postgres": "src/dungeonmind/infrastructure/postgres/records.py:PostgresContributionReviewRepository",
        "current_authority_paths": ["world_graph_write_publication"],
        "founding_runtime_only_paths": [],
        "compatibility_only_paths": [],
        "disposition": "USED",
        "evidence": [
            "apps/live_control_server/integrations/dungeonmind/world_graph_writes.py",
            "src/dungeonmind/application/contribution_review_v2.py",
        ],
    },
    "FinalizedReviewPublicationRepository": {
        "in_memory": "src/dungeonmind/infrastructure/memory/repositories.py:InMemoryFinalizedReviewPublicationRepository",
        "postgres": "src/dungeonmind/infrastructure/postgres/review_publication.py:PostgresFinalizedReviewPublicationRepository",
        "current_authority_paths": ["world_graph_write_publication"],
        "founding_runtime_only_paths": [],
        "compatibility_only_paths": [],
        "disposition": "USED",
        "evidence": [
            "apps/live_control_server/integrations/dungeonmind/world_graph_writes.py",
            "src/dungeonmind/application/review_publication.py",
        ],
    },
    "ExistingWorldAdoptionRepository": {
        "in_memory": "src/dungeonmind/infrastructure/memory/repositories.py:InMemoryExistingWorldAdoptionRepository",
        "postgres": "src/dungeonmind/infrastructure/postgres/existing_world_adoption.py:PostgresExistingWorldAdoptionRepository",
        "current_authority_paths": ["world_graph_read_genesis"],
        "founding_runtime_only_paths": [],
        "compatibility_only_paths": ["existing_world_adoption_write", "adoption_repair"],
        "disposition": "USED",
        "evidence": [
            "apps/live_control_server/integrations/dungeonmind/world_graph_reads.py",
            "src/dungeonmind/application/existing_world_adoption.py",
        ],
        "notes": (
            "Buddy production reads get_for_world to bind genesis. The adopt() write "
            "path is historical-compat; do not treat the whole port as UNUSED."
        ),
    },
    "ReviewedWorldInitializationRepository": {
        "in_memory": "src/dungeonmind/infrastructure/memory/repositories.py:InMemoryReviewedWorldInitializationRepository",
        "postgres": "src/dungeonmind/infrastructure/postgres/reviewed_world_initialization.py:PostgresReviewedWorldInitializationRepository",
        "current_authority_paths": [
            "reviewed_first_world_initialization",
            "world_graph_read_genesis",
        ],
        "founding_runtime_only_paths": [],
        "compatibility_only_paths": [],
        "disposition": "USED",
        "evidence": [
            "apps/live_control_server/integrations/dungeonmind/world_graph_initialization_adapter.py",
            "apps/live_control_server/integrations/dungeonmind/world_graph_reads.py",
        ],
    },
    "IdentityDecisionRepository": {
        "in_memory": "src/dungeonmind/infrastructure/memory/repositories.py:InMemoryIdentityDecisionRepository",
        "postgres": "src/dungeonmind/infrastructure/postgres/records.py:PostgresIdentityDecisionRepository",
        "current_authority_paths": ["world_graph_write_publication"],
        "founding_runtime_only_paths": [],
        "compatibility_only_paths": ["existing_world_adoption_membership"],
        "disposition": "USED",
        "evidence": [
            "apps/live_control_server/integrations/dungeonmind/world_graph_writes.py",
            "src/dungeonmind/contracts/identity.py",
        ],
    },
    "MindThreadRepository": {
        "in_memory": "src/dungeonmind/infrastructure/memory/repositories.py:InMemoryMindThreadRepository",
        "postgres": "src/dungeonmind/infrastructure/postgres/threads.py:PostgresMindThreadRepository",
        "current_authority_paths": [],
        "founding_runtime_only_paths": ["mind_turn_service", "demo_host"],
        "compatibility_only_paths": [],
        "disposition": "UNUSED",
        "evidence": [
            "src/dungeonmind/application/mind_turn.py",
            "src/dungeonmind/service/bootstrap.py",
        ],
        "notes": "Constructed by PostgresRepositoryBundle but not called by Buddy World paths.",
    },
    "RetrievalSessionRepository": {
        "in_memory": "src/dungeonmind/infrastructure/memory/repositories.py:InMemoryRetrievalSessionRepository",
        "postgres": "src/dungeonmind/infrastructure/postgres/records.py:PostgresRetrievalSessionRepository",
        "current_authority_paths": [],
        "founding_runtime_only_paths": ["mind_turn_service"],
        "compatibility_only_paths": [],
        "disposition": "UNUSED",
        "evidence": ["src/dungeonmind/application/mind_turn.py"],
    },
    "SemanticDocumentRepository": {
        "in_memory": "src/dungeonmind/infrastructure/memory/repositories.py:InMemorySemanticDocumentRepository",
        "postgres": "src/dungeonmind/infrastructure/postgres/semantic.py:PostgresSemanticDocumentRepository",
        "current_authority_paths": [],
        "founding_runtime_only_paths": ["mind_turn_semantic_projection"],
        "compatibility_only_paths": [],
        "disposition": "UNUSED",
        "evidence": ["src/dungeonmind/application/mind_turn.py"],
    },
    "SemanticSearchPort": {
        "in_memory": "src/dungeonmind/infrastructure/memory/repositories.py:InMemorySemanticSearch",
        "postgres": "src/dungeonmind/infrastructure/postgres/semantic.py:PostgresSemanticSearch",
        "current_authority_paths": [],
        "founding_runtime_only_paths": ["mind_turn_semantic_projection"],
        "compatibility_only_paths": [],
        "disposition": "UNUSED",
        "evidence": ["src/dungeonmind/application/mind_turn.py"],
    },
    "EmbeddingRunRepository": {
        "in_memory": "src/dungeonmind/infrastructure/memory/repositories.py:InMemoryEmbeddingRunRepository",
        "postgres": "src/dungeonmind/infrastructure/postgres/semantic.py:PostgresEmbeddingRunRepository",
        "current_authority_paths": [],
        "founding_runtime_only_paths": ["mind_turn_semantic_projection"],
        "compatibility_only_paths": [],
        "disposition": "UNUSED",
        "evidence": ["src/dungeonmind/application/mind_turn.py"],
    },
    "PostgresRepositoryBundle": {
        "in_memory": None,
        "postgres": "src/dungeonmind/infrastructure/postgres/__init__.py:PostgresRepositoryBundle",
        "current_authority_paths": ["world_graph_read", "world_graph_write_publication"],
        "founding_runtime_only_paths": [],
        "compatibility_only_paths": [],
        "disposition": "USED",
        "evidence": [
            "apps/live_control_server/integrations/dungeonmind/world_graph_reads.py"
        ],
        "notes": (
            "Buddy constructs the full bundle, including unused semantic/thread "
            "adapters. Bundle construction is not by itself USE evidence for those ports."
        ),
    },
}

TABLE_OVERLAY: dict[str, dict[str, Any]] = {
    "worlds": {
        "adapters": ["PostgresWorldGraphRepository", "PostgresDatabase"],
        "current_authority_paths": ["world_graph_read", "world_graph_write_publication"],
        "historical_compatibility_obligation": None,
        "founding_runtime_only_ownership": None,
        "disposition": "USED",
        "k1_code_demolition_while_table_remains": False,
        "evidence": ["migrations/versions/0001_postgres_substrate.py"],
    },
    "campaigns": {
        "adapters": ["PostgresWorldGraphRepository"],
        "current_authority_paths": ["world_graph_read", "world_graph_write_publication"],
        "historical_compatibility_obligation": None,
        "founding_runtime_only_ownership": None,
        "disposition": "USED",
        "k1_code_demolition_while_table_remains": False,
        "evidence": ["migrations/versions/0001_postgres_substrate.py"],
    },
    "graph_revisions": {
        "adapters": ["PostgresWorldGraphRepository"],
        "current_authority_paths": ["world_graph_read", "world_graph_write_publication"],
        "historical_compatibility_obligation": "historical revision pins remain readable",
        "founding_runtime_only_ownership": None,
        "disposition": "USED",
        "k1_code_demolition_while_table_remains": False,
        "evidence": ["migrations/versions/0001_postgres_substrate.py"],
    },
    "world_graph_heads": {
        "adapters": ["PostgresWorldGraphRepository"],
        "current_authority_paths": ["world_graph_read", "world_graph_write_publication"],
        "historical_compatibility_obligation": None,
        "founding_runtime_only_ownership": None,
        "disposition": "USED",
        "k1_code_demolition_while_table_remains": False,
        "evidence": ["migrations/versions/0001_postgres_substrate.py"],
    },
    "world_graph_head_events": {
        "adapters": ["PostgresWorldGraphRepository"],
        "current_authority_paths": ["world_graph_write_publication"],
        "historical_compatibility_obligation": "auditable head movement history",
        "founding_runtime_only_ownership": None,
        "disposition": "USED",
        "k1_code_demolition_while_table_remains": False,
        "evidence": ["migrations/versions/0001_postgres_substrate.py"],
    },
    "source_artifacts": {
        "adapters": ["PostgresSourceRepository", "PostgresExistingWorldAdoptionRepository"],
        "current_authority_paths": ["source_evidence", "world_graph_read"],
        "historical_compatibility_obligation": "adopted membership identity",
        "founding_runtime_only_ownership": None,
        "disposition": "USED",
        "k1_code_demolition_while_table_remains": False,
        "evidence": ["migrations/versions/0001_postgres_substrate.py"],
    },
    "source_revisions": {
        "adapters": ["PostgresSourceRepository"],
        "current_authority_paths": ["source_evidence", "world_graph_read"],
        "historical_compatibility_obligation": None,
        "founding_runtime_only_ownership": None,
        "disposition": "USED",
        "k1_code_demolition_while_table_remains": False,
        "evidence": ["migrations/versions/0001_postgres_substrate.py"],
    },
    "evidence_refs": {
        "adapters": ["PostgresSourceRepository"],
        "current_authority_paths": ["source_evidence", "world_graph_read"],
        "historical_compatibility_obligation": None,
        "founding_runtime_only_ownership": None,
        "disposition": "USED",
        "k1_code_demolition_while_table_remains": False,
        "evidence": ["migrations/versions/0001_postgres_substrate.py"],
    },
    "graph_contributions": {
        "adapters": ["PostgresContributionRepository"],
        "current_authority_paths": ["world_graph_write_publication"],
        "historical_compatibility_obligation": "adopted membership family",
        "founding_runtime_only_ownership": None,
        "disposition": "USED",
        "k1_code_demolition_while_table_remains": False,
        "evidence": ["migrations/versions/0001_postgres_substrate.py"],
    },
    "identity_decisions": {
        "adapters": ["PostgresIdentityDecisionRepository"],
        "current_authority_paths": ["world_graph_write_publication"],
        "historical_compatibility_obligation": "adopted membership family",
        "founding_runtime_only_ownership": None,
        "disposition": "USED",
        "k1_code_demolition_while_table_remains": False,
        "evidence": ["migrations/versions/0001_postgres_substrate.py"],
    },
    "retrieval_sessions": {
        "adapters": ["PostgresRetrievalSessionRepository"],
        "current_authority_paths": [],
        "historical_compatibility_obligation": (
            "physical table may hold founding-era rows; live Eldyrwild contents unknown"
        ),
        "founding_runtime_only_ownership": "MindTurn retrieval sessions",
        "disposition": "HISTORICAL-COMPAT",
        "k1_code_demolition_while_table_remains": True,
        "evidence": ["migrations/versions/0001_postgres_substrate.py"],
    },
    "mind_threads": {
        "adapters": ["PostgresMindThreadRepository"],
        "current_authority_paths": [],
        "historical_compatibility_obligation": (
            "physical table may hold founding-era rows; live Eldyrwild contents unknown"
        ),
        "founding_runtime_only_ownership": "MindTurn threads",
        "disposition": "HISTORICAL-COMPAT",
        "k1_code_demolition_while_table_remains": True,
        "evidence": ["migrations/versions/0001_postgres_substrate.py"],
    },
    "mind_turns": {
        "adapters": ["PostgresMindThreadRepository"],
        "current_authority_paths": [],
        "historical_compatibility_obligation": (
            "physical table may hold founding-era rows; live Eldyrwild contents unknown"
        ),
        "founding_runtime_only_ownership": "MindTurn turns",
        "disposition": "HISTORICAL-COMPAT",
        "k1_code_demolition_while_table_remains": True,
        "evidence": ["migrations/versions/0001_postgres_substrate.py"],
    },
    "embedding_runs": {
        "adapters": ["PostgresEmbeddingRunRepository"],
        "current_authority_paths": [],
        "historical_compatibility_obligation": (
            "physical table/pgvector run provenance may exist in living databases"
        ),
        "founding_runtime_only_ownership": "semantic document materialization",
        "disposition": "HISTORICAL-COMPAT",
        "k1_code_demolition_while_table_remains": True,
        "evidence": ["migrations/versions/0001_postgres_substrate.py"],
    },
    "active_embedding_runs": {
        "adapters": ["PostgresEmbeddingRunRepository"],
        "current_authority_paths": [],
        "historical_compatibility_obligation": "active-run pointer for semantic search",
        "founding_runtime_only_ownership": "semantic document materialization",
        "disposition": "HISTORICAL-COMPAT",
        "k1_code_demolition_while_table_remains": True,
        "evidence": ["migrations/versions/0001_postgres_substrate.py"],
    },
    "semantic_documents": {
        "adapters": ["PostgresSemanticDocumentRepository", "PostgresSemanticSearch"],
        "current_authority_paths": [],
        "historical_compatibility_obligation": (
            "pgvector/FTS derived documents may exist in living databases"
        ),
        "founding_runtime_only_ownership": "semantic search runtime",
        "disposition": "HISTORICAL-COMPAT",
        "k1_code_demolition_while_table_remains": True,
        "evidence": ["migrations/versions/0001_postgres_substrate.py"],
    },
    "contribution_reviews": {
        "adapters": ["PostgresContributionReviewRepository"],
        "current_authority_paths": ["world_graph_write_publication"],
        "historical_compatibility_obligation": None,
        "founding_runtime_only_ownership": None,
        "disposition": "USED",
        "k1_code_demolition_while_table_remains": False,
        "evidence": ["migrations/versions/0002_contribution_reviews.py"],
    },
    "finalized_review_publications": {
        "adapters": ["PostgresFinalizedReviewPublicationRepository"],
        "current_authority_paths": ["world_graph_write_publication"],
        "historical_compatibility_obligation": "idempotent publication recovery receipts",
        "founding_runtime_only_ownership": None,
        "disposition": "USED",
        "k1_code_demolition_while_table_remains": False,
        "evidence": ["migrations/versions/0003_finalized_review_publications.py"],
    },
    "existing_world_adoptions": {
        "adapters": ["PostgresExistingWorldAdoptionRepository"],
        "current_authority_paths": ["world_graph_read_genesis"],
        "historical_compatibility_obligation": (
            "Eldyrwild V4 adoption receipt is durable authority for D_A genesis"
        ),
        "founding_runtime_only_ownership": None,
        "disposition": "USED",
        "k1_code_demolition_while_table_remains": False,
        "evidence": ["migrations/versions/0006_existing_world_adoptions.py"],
    },
    "reviewed_world_initializations": {
        "adapters": ["PostgresReviewedWorldInitializationRepository"],
        "current_authority_paths": [
            "reviewed_first_world_initialization",
            "world_graph_read_genesis",
        ],
        "historical_compatibility_obligation": "D0 genesis provenance receipts",
        "founding_runtime_only_ownership": None,
        "disposition": "USED",
        "k1_code_demolition_while_table_remains": False,
        "evidence": ["migrations/versions/0007_reviewed_world_init.py"],
    },
}

EXCEPTION_OVERLAY: dict[str, dict[str, Any]] = {
    "application_agents_mutual_allowance": {
        "protects": "HISTORICAL_OR_FOUNDING",
        "reason": (
            "MindTurnService depends on AgentAdapter hosted under agents/; "
            "ADR-0022 places the harness outside the library."
        ),
    },
    "postgres_only_roots": {
        "protects": "CURRENT_REQUIRED",
        "reason": "Durable PostgreSQL adapters are the current Eldyrwild authority substrate.",
    },
    "api_only_roots": {
        "protects": "UNKNOWN",
        "reason": (
            "service/api.py hosts MindTurn demo together with publication and "
            "fictional-time HTTP. Cannot treat the whole FastAPI extra as founding-only."
        ),
        "blocking_question": (
            "If K1 excises MindTurn from the FastAPI host, which publication and "
            "fictional-time routes remain a current library obligation?"
        ),
    },
    "forbidden_roots": {
        "protects": "CURRENT_REQUIRED",
        "reason": "Keeps the kernel free of Buddy apps, model frameworks, and sibling repos.",
    },
    "dnd_planning_allowlist": {
        "protects": "CURRENT_REQUIRED",
        "reason": "B.2d contribution planning is current dungeonmind_dnd application logic.",
    },
    "dnd_review_allowlist": {
        "protects": "CURRENT_REQUIRED",
        "reason": "B.2e review adapter is current dungeonmind_dnd application logic.",
    },
    "dnd_mechanics_allowlist": {
        "protects": "CURRENT_REQUIRED",
        "reason": "B.3a mechanics binders are current dungeonmind_dnd application logic.",
    },
    "dnd_transport_allowlist": {
        "protects": "UNKNOWN",
        "reason": (
            "FastAPI/httpx transport is an optional extra. Buddy uses a separate "
            "dungeonmind_statblocks client, not this module."
        ),
        "blocking_question": (
            "Does any current deployment host dungeonmind_dnd.integration.threat_mechanics_api, "
            "or is that surface only a founding/example extra?"
        ),
    },
    "dnd_resource_allowlist": {
        "protects": "UNKNOWN",
        "reason": "httpx statblock resource resolver is optional and unused by the Buddy pin.",
        "blocking_question": (
            "Is dungeonmind_dnd.integration.statblock_resource_resolver invoked by any "
            "current non-Buddy consumer (for example DungeonMindServer)?"
        ),
    },
}


def subsystem_dispositions() -> list[dict[str, Any]]:
    return [
        {
            "id": "mind_turn_contracts_and_service",
            "disposition": "UNUSED",
            "covers": [
                "dungeonmind.application.mind_turn",
                "dungeonmind.contracts.mind_turn",
            ],
            "evidence": [
                "src/dungeonmind/application/mind_turn.py",
                "src/dungeonmind/contracts/mind_turn.py",
                "src/dungeonmind/service/api.py",
                "Docs/Decisions/ADR-0022-independent-library-and-agent-harness-boundary.md",
            ],
            "falsification_note": (
                "Sought Buddy production, test, and Hermes imports of "
                "dungeonmind.application.mind_turn / contracts.mind_turn and "
                "MindTurnService. None exist at a9d4c61. World projection/retrieval/"
                "publication modules do not import mind_turn. Remaining callers are "
                "the optional FastAPI demo host, curated seed scripts, and DungeonMind "
                "unit tests — tests alone do not make a subsystem USED."
            ),
        },
        {
            "id": "agents_protocol_and_fixture",
            "disposition": "UNUSED",
            "covers": ["dungeonmind.agents"],
            "evidence": [
                "src/dungeonmind/agents/protocol.py",
                "src/dungeonmind/agents/fixture.py",
                "src/dungeonmind/application/mind_turn.py",
            ],
            "falsification_note": (
                "Sought Buddy/Hermes imports of dungeonmind.agents. None at the Buddy "
                "anchor. The only runtime importer is MindTurnService / fixture adapter."
            ),
        },
        {
            "id": "capability_policy_agent_visible_tool_authority",
            "disposition": "UNUSED",
            "covers": [
                "dungeonmind.domain.capability",
                "dungeonmind.agents.protocol",
            ],
            "evidence": [
                "src/dungeonmind/contracts/capability.py",
                "src/dungeonmind/domain/capability.py",
                "src/dungeonmind/application/mind_turn.py",
            ],
            "falsification_note": (
                "Sought Buddy imports of permitted_tool_names / evaluate_capability / "
                "AgentTurnContext tool authority. None found. Buddy Hermes owns the "
                "product tool loop. CapabilityPolicy itself is NOT covered here because "
                "Buddy does import it for contribution-review authorization."
            ),
        },
        {
            "id": "capability_policy_contribution_review_authorization",
            "disposition": "USED",
            "covers": [
                "dungeonmind.contracts.capability:CapabilityPolicy",
                "dungeonmind.contracts.capability:ToolCapabilityRule",
            ],
            "evidence": [
                "apps/live_control_server/integrations/dungeonmind/world_graph_writes.py",
                "src/dungeonmind/application/contribution_review_v2.py",
            ],
        },
        {
            "id": "context_assembly_mind_turn_budgeting",
            "disposition": "UNUSED",
            "covers": ["dungeonmind.application.context_assembly"],
            "evidence": ["src/dungeonmind/application/context_assembly.py"],
            "falsification_note": (
                "assemble_agent_context is imported only by MindTurnService. Buddy "
                "World adapters do not import it. No dynamic loader found."
            ),
        },
        {
            "id": "claim_answer_validation_mind_turn_retrieval",
            "disposition": "UNKNOWN",
            "covers": ["dungeonmind.application.mind_turn"],
            "evidence": [
                "src/dungeonmind/contracts/retrieval.py",
                "src/dungeonmind/application/mind_turn.py",
                "src/dungeonmind/application/world_graph_retrieval.py",
            ],
            "blocking_question": (
                "Claim/answer-validation types live in contracts/retrieval.py beside "
                "ResolvedReferent, which current WorldGraphRetrievalService imports. "
                "K1 must split that module before treating the Claim ledger as UNUSED."
            ),
        },
        {
            "id": "mind_thread_persistence_runtime",
            "disposition": "UNUSED",
            "covers": [
                "dungeonmind.infrastructure.postgres.threads",
                "dungeonmind.application.repositories:MindThreadRepository",
            ],
            "evidence": [
                "src/dungeonmind/application/repositories.py",
                "src/dungeonmind/infrastructure/postgres/threads.py",
            ],
            "falsification_note": (
                "No Buddy call to create_thread/append_turn/list_turns. Bundle "
                "construction is not use. Tables remain HISTORICAL-COMPAT."
            ),
        },
        {
            "id": "retrieval_session_persistence_runtime",
            "disposition": "UNUSED",
            "covers": ["dungeonmind.application.repositories:RetrievalSessionRepository"],
            "evidence": ["src/dungeonmind/application/repositories.py"],
            "falsification_note": (
                "No Buddy import or World-path call of RetrievalSessionRepository. "
                "MindTurnService is the remaining runtime owner. Table stays."
            ),
        },
        {
            "id": "semantic_document_persistence_runtime",
            "disposition": "UNUSED",
            "covers": ["dungeonmind.application.repositories:SemanticDocumentRepository"],
            "evidence": [
                "src/dungeonmind/application/repositories.py",
                "src/dungeonmind/infrastructure/postgres/semantic.py",
            ],
            "falsification_note": (
                "Buddy World adapters do not call SemanticDocumentRepository. Native "
                "graph retrieval is graph-only. Table/pgvector rows remain protected."
            ),
        },
        {
            "id": "embedding_run_persistence_runtime",
            "disposition": "UNUSED",
            "covers": ["dungeonmind.application.repositories:EmbeddingRunRepository"],
            "evidence": ["src/dungeonmind/application/repositories.py"],
            "falsification_note": (
                "No Buddy import of EmbeddingRunRepository. MindTurn semantic "
                "projection is the remaining runtime owner."
            ),
        },
        {
            "id": "semantic_search_pgvector_runtime",
            "disposition": "UNUSED",
            "covers": [
                "dungeonmind.application.repositories:SemanticSearchPort",
                "dungeonmind.domain.fusion",
                "dungeonmind.application.query_embedding",
            ],
            "evidence": [
                "src/dungeonmind/application/mind_turn.py",
                "src/dungeonmind/domain/fusion.py",
                "src/dungeonmind/infrastructure/postgres/semantic.py",
            ],
            "falsification_note": (
                "Sought Buddy imports of SemanticSearchPort, fusion, query embedding, "
                "and pgvector search. None at the Buddy pin. World retrieval does not "
                "import them. Physical semantic_documents/embedding tables stay."
            ),
        },
        {
            "id": "demo_access_curated_mind_turn_host",
            "disposition": "UNUSED",
            "covers": [
                "dungeonmind.service.demo_access",
                "dungeonmind.infrastructure.fixtures",
            ],
            "evidence": [
                "src/dungeonmind/service/demo_access.py",
                "src/dungeonmind/service/api.py",
                "scripts/serve_curated_mind_turn_surface.py",
            ],
            "falsification_note": (
                "No Buddy import of demo_access or curated MindTurn fixtures. Callers "
                "are the optional FastAPI host and DungeonMind seed/serve scripts."
            ),
        },
        {
            "id": "world_graph_projection_retrieval",
            "disposition": "USED",
            "covers": [
                "dungeonmind.application.world_graph_projection",
                "dungeonmind.application.world_graph_retrieval",
            ],
            "evidence": [
                "apps/live_control_server/integrations/dungeonmind/world_graph_reads.py",
                "src/dungeonmind/application/world_graph_projection.py",
                "src/dungeonmind/application/world_graph_retrieval.py",
            ],
        },
        {
            "id": "source_evidence_repositories",
            "disposition": "USED",
            "covers": ["dungeonmind.application.repositories:SourceRepository"],
            "evidence": [
                "apps/live_control_server/integrations/dungeonmind/world_graph_source_admission_adapter.py",
                "apps/live_control_server/integrations/dungeonmind/world_graph_reads.py",
            ],
        },
        {
            "id": "contribution_review_publication",
            "disposition": "USED",
            "covers": [
                "dungeonmind.application.contribution_review_v2",
                "dungeonmind.application.review_publication",
            ],
            "evidence": [
                "apps/live_control_server/integrations/dungeonmind/world_graph_writes.py"
            ],
        },
        {
            "id": "reviewed_first_world_initialization",
            "disposition": "USED",
            "covers": ["dungeonmind.application.reviewed_world_initialization"],
            "evidence": [
                "apps/live_control_server/integrations/dungeonmind/world_graph_initialization_adapter.py"
            ],
        },
        {
            "id": "existing_world_adoption_receipt_read",
            "disposition": "USED",
            "covers": [
                "dungeonmind.application.repositories:ExistingWorldAdoptionRepository"
            ],
            "evidence": [
                "apps/live_control_server/integrations/dungeonmind/world_graph_reads.py"
            ],
        },
        {
            "id": "existing_world_adoption_write_command",
            "disposition": "HISTORICAL-COMPAT",
            "covers": ["dungeonmind.application.existing_world_adoption"],
            "evidence": [
                "src/dungeonmind/application/existing_world_adoption.py",
                "Docs/Architecture/AUTHORITY.md",
            ],
            "historical_obligation": (
                "The Eldyrwild adopted world is living state. adopt() and v1-v4 receipt "
                "codecs remain required to reconstruct/verify that genesis. New clients "
                "should not learn the write path, but K1 must not delete it."
            ),
        },
        {
            "id": "adoption_repair",
            "disposition": "HISTORICAL-COMPAT",
            "covers": ["dungeonmind.application.existing_world_adoption_repair"],
            "evidence": [
                "src/dungeonmind/application/existing_world_adoption_repair.py",
                "Docs/Architecture/AUTHORITY.md",
            ],
            "historical_obligation": (
                "The single accepted V4 source-classification repair is durable "
                "authority (M0 vs M1). Repair code and contracts reconstruct that fact."
            ),
        },
        {
            "id": "correspondence",
            "disposition": "HISTORICAL-COMPAT",
            "covers": ["dungeonmind.application.existing_world_correspondence"],
            "evidence": ["src/dungeonmind/application/existing_world_correspondence.py"],
            "historical_obligation": (
                "Correspondence re-proofs adopted membership against sealed receipts. "
                "No Buddy production import, but living adoption integrity uses it."
            ),
        },
        {
            "id": "versioned_union_graph_snapshot_dispatch",
            "disposition": "USED",
            "covers": [
                "dungeonmind.application.graph_snapshot:VersionedUnionGraphSnapshotReader"
            ],
            "evidence": [
                "apps/live_control_server/integrations/dungeonmind/world_graph_reads.py",
                "src/dungeonmind/application/graph_snapshot.py",
            ],
        },
        {
            "id": "v1_v5_historical_graph_schema_codecs",
            "disposition": "HISTORICAL-COMPAT",
            "covers": [
                "dungeonmind.application.graph_snapshot_v4",
                "dungeonmind.application.graph_snapshot_v5",
            ],
            "evidence": [
                "src/dungeonmind/application/graph_snapshot.py",
                "src/dungeonmind/application/graph_snapshot_v4.py",
                "src/dungeonmind/application/graph_snapshot_v6.py",
            ],
            "historical_obligation": (
                "VersionedUnionGraphSnapshotReader currently dispatches v1-v6 on the "
                "hot read path so exact historical pins remain readable. V1-V3 live in "
                "graph_snapshot.py beside current types. K1 may hide codecs behind a "
                "compatibility boundary but must not drop decoding of stored schemas."
            ),
        },
        {
            "id": "semantic_profile_registry",
            "disposition": "USED",
            "covers": [
                "dungeonmind.application.semantic_profiles",
                "dungeonmind.infrastructure.semantic_profiles",
                "dungeonmind.contracts.semantic_profile",
            ],
            "evidence": [
                "apps/live_control_server/integrations/dungeonmind/world_graph_reads.py",
                "apps/live_control_server/integrations/dungeonmind/world_graph_writes.py",
            ],
        },
        {
            "id": "dnd_profile_planning_mechanics_packages",
            "disposition": "USED",
            "covers": ["dungeonmind_dnd"],
            "evidence": [
                "apps/live_control_server/integrations/dungeonmind/world_graph_reads.py",
                "apps/live_control_server/integrations/dungeonmind/assertion_qualification.py",
                "src/dungeonmind_dnd/application/world_object_vocabulary.py",
            ],
            "notes": (
                "Buddy production imports load_builtin_v3_descriptor. Planning/mechanics "
                "modules are current profile-owned application logic even when Buddy "
                "does not import every submodule."
            ),
        },
        {
            "id": "dnd_optional_fastapi_httpx_transport",
            "disposition": "UNKNOWN",
            "covers": [
                "dungeonmind_dnd.application.threat_mechanics_transport",
                "dungeonmind_dnd.integration",
            ],
            "evidence": [
                "src/dungeonmind_dnd/application/threat_mechanics_transport.py",
                "src/dungeonmind_dnd/integration/threat_mechanics_api.py",
                "src/dungeonmind_dnd/integration/statblock_resource_resolver.py",
            ],
            "blocking_question": (
                "Is the optional FastAPI/httpx D&D transport a current deployment "
                "surface, or only an in-repo extra with no current consumer? Buddy at "
                "the pin uses dungeonmind_statblocks instead. K1 must not guess."
            ),
        },
    ]
