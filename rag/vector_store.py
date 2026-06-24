"""ChromaDB vector store — persists document chunk embeddings and exposes add/query operations."""
import logging
from pathlib import Path

import chromadb
from langchain_core.documents import Document

from config.settings import settings
from rag.embeddings import get_embedding, get_embeddings

logger = logging.getLogger(__name__)

POLICY_COLLECTION = "policy_documents"
TICKETS_COLLECTION = "historical_tickets"


def _get_client() -> chromadb.PersistentClient:
    """Return a persistent ChromaDB client stored at CHROMA_PERSIST_PATH."""
    Path(settings.chroma_persist_path).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=settings.chroma_persist_path)


def get_or_create_collection(name: str) -> chromadb.Collection:
    """Return an existing ChromaDB collection or create it if it doesn't exist."""
    client = _get_client()
    return client.get_or_create_collection(name=name)


def add_documents(
    documents: list[Document],
    collection_name: str = POLICY_COLLECTION,
) -> int:
    """Embed and store a list of LangChain Documents in ChromaDB.

    Returns the number of documents added. Skips duplicates by using the
    document source + chunk_index as a stable ID.
    """
    if not documents:
        return 0

    collection = get_or_create_collection(collection_name)

    texts = [doc.page_content for doc in documents]
    metadatas = [doc.metadata for doc in documents]
    ids = [
        f"{meta.get('source', 'doc')}_{meta.get('chunk_index', i)}"
        for i, meta in enumerate(metadatas)
    ]
    embeddings = get_embeddings(texts)

    # ChromaDB metadata values must be str, int, float, or bool — convert lists
    safe_metadatas = []
    for meta in metadatas:
        safe = {}
        for k, v in meta.items():
            safe[k] = ", ".join(v) if isinstance(v, list) else v
        safe_metadatas.append(safe)

    collection.upsert(
        documents=texts,
        embeddings=embeddings,
        metadatas=safe_metadatas,
        ids=ids,
    )

    logger.info("Upserted %d chunks into collection '%s'.", len(documents), collection_name)
    return len(documents)


def query_collection(
    query_text: str,
    collection_name: str = POLICY_COLLECTION,
    n_results: int | None = None,
) -> list[dict]:
    """Query a ChromaDB collection and return the top matching chunks.

    Each result dict contains: document, metadata, distance, id.
    """
    n_results = n_results or settings.max_retrieval_docs
    collection = get_or_create_collection(collection_name)

    count = collection.count()
    if count == 0:
        logger.warning("Collection '%s' is empty — run ingestion first.", collection_name)
        return []

    query_embedding = get_embedding(query_text)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, count),
        include=["documents", "metadatas", "distances"],
    )

    output = []
    for doc, meta, dist, doc_id in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
        results["ids"][0],
    ):
        output.append({"document": doc, "metadata": meta, "distance": dist, "id": doc_id})

    return output


def delete_collection(name: str) -> None:
    """Delete a ChromaDB collection (used in tests / re-ingestion). No-op if not found."""
    client = _get_client()
    try:
        client.delete_collection(name=name)
        logger.info("Deleted collection '%s'.", name)
    except Exception:
        logger.debug("Collection '%s' did not exist — nothing to delete.", name)
