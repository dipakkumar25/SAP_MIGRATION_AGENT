"""
RAG Service — Retrieval-Augmented Generation for SAP Migration Knowledge.

Responsibilities:
  1. Ingest SAP domain knowledge documents into ChromaDB on first use.
  2. Expose retrieve(query, k) to fetch the most relevant document chunks.
  3. Used by Agent 7 (Recommendations) and Agent 8 (Runbook) to ground LLM
     prompts with authoritative SAP migration context.

Backend:  ChromaDB (already in requirements.txt)
Embedder: langchain_community.embeddings.SentenceTransformerEmbeddings
          (model: all-MiniLM-L6-v2 — lightweight, no external API key needed)
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from app.services.logger import get_logger
from config.settings import get_settings

log = get_logger(__name__)
settings = get_settings()

# ChromaDB collection that stores all SAP migration knowledge chunks
_COLLECTION_NAME = settings.chroma_collection   # "sap_migration_kb"
_EMBED_MODEL = "all-MiniLM-L6-v2"
_PERSIST_DIR = str(Path("output") / "chroma_db")

_vectorstore = None   # module-level singleton


# ── Embedding helper ─────────────────────────────────────────────────────────

def _get_embeddings():
    """Return a LangChain-compatible embedding model (local, no API key)."""
    from langchain_community.embeddings import SentenceTransformerEmbeddings
    return SentenceTransformerEmbeddings(model_name=_EMBED_MODEL)


# ── Vector store singleton ────────────────────────────────────────────────────

def _get_vectorstore():
    """Return (and lazily create) the ChromaDB vector store."""
    global _vectorstore
    if _vectorstore is not None:
        return _vectorstore

    from langchain_community.vectorstores import Chroma
    embeddings = _get_embeddings()
    _vectorstore = Chroma(
        collection_name=_COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=_PERSIST_DIR,
    )
    log.info("ChromaDB vectorstore initialised",
             collection=_COLLECTION_NAME, persist_dir=_PERSIST_DIR)
    return _vectorstore


# ── Ingestion ─────────────────────────────────────────────────────────────────

def ingest_knowledge_base(force: bool = False) -> int:
    """
    Load SAP migration knowledge documents and ingest them into ChromaDB.

    Skips ingestion when the collection already has documents (idempotent),
    unless ``force=True`` is passed.

    Returns the total number of document chunks in the collection after ingestion.
    """
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain.schema import Document
    from app.services.sap_knowledge_base import get_sap_knowledge_documents

    vs = _get_vectorstore()

    # Check if already populated
    existing = vs._collection.count()
    if existing > 0 and not force:
        log.info("Knowledge base already populated, skipping ingestion",
                 existing_chunks=existing)
        return existing

    log.info("Ingesting SAP migration knowledge base …")
    raw_docs: List[Document] = get_sap_knowledge_documents()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=80,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(raw_docs)

    # Batch upsert to avoid memory spikes on large knowledge bases
    batch_size = 100
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        vs.add_documents(batch)

    total = vs._collection.count()
    log.info("Knowledge base ingestion complete",
             raw_docs=len(raw_docs), chunks=len(chunks), total_in_db=total)
    return total


# ── Retrieval ─────────────────────────────────────────────────────────────────

def retrieve(query: str, k: int = 4) -> str:
    """
    Retrieve the top-k most relevant SAP knowledge chunks for *query*.

    Returns a single string suitable for injection into an LLM prompt.
    Falls back gracefully to an empty string when ChromaDB is unavailable.
    """
    try:
        vs = _get_vectorstore()
        docs = vs.similarity_search(query, k=k)
        if not docs:
            return ""
        sections = []
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get("source", "SAP Knowledge Base")
            sections.append(f"[Context {i} — {source}]\n{doc.page_content.strip()}")
        return "\n\n".join(sections)
    except Exception as exc:
        log.warning("RAG retrieval failed, proceeding without context", error=str(exc))
        return ""


def retrieve_for_finding(object_name: str, check_title: str, message: str, k: int = 3) -> str:
    """
    Build a targeted retrieval query from an ATC finding's key fields and
    return relevant SAP migration guidance.
    """
    query = f"{check_title} {object_name} {message}"
    return retrieve(query, k=k)


def retrieve_for_runbook(system_id: str, risk_level: str, key_risks: str, k: int = 5) -> str:
    """
    Build a retrieval query focused on runbook / migration planning context.
    """
    query = (
        f"SAP S/4HANA migration runbook {risk_level} risk "
        f"cutover planning {key_risks}"
    )
    return retrieve(query, k=k)
