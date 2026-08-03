"""
Agent 0 – RAG Knowledge Base Ingestion
Runs once at the start of the workflow to populate ChromaDB with SAP migration
knowledge documents. Subsequent agents (07, 08) retrieve relevant chunks from
this vector store to ground their LLM prompts.
"""
from __future__ import annotations

from app.models.schemas import AgentState
from app.services import get_logger
from app.services.rag_service import ingest_knowledge_base

log = get_logger(__name__)


def run_rag_ingestion(state: AgentState) -> AgentState:
    """LangGraph node: ingest SAP knowledge base into ChromaDB (idempotent)."""
    log.info("Agent 0 – RAG Ingestion started", assessment_id=state.assessment_id)
    try:
        total_chunks = ingest_knowledge_base(force=False)
        state.rag_chunks_ingested = total_chunks
        state.steps_completed.append("rag_ingestion")
        log.info("Agent 0 – RAG Ingestion complete", chunks_in_db=total_chunks)
    except Exception as exc:
        # RAG failure must not block the rest of the pipeline
        log.warning("Agent 0 – RAG Ingestion failed, continuing without RAG",
                    error=str(exc))
        state.error_messages.append(f"RAG Ingestion (non-fatal): {exc}")
    return state
