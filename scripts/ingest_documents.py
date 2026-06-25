"""Ingests policy documents into the ChromaDB policy_documents collection.

Run this script once before starting the agent, and again whenever a policy
file is updated. It deletes the existing collection and re-ingests from
scratch so embeddings are always in sync with the current policy text.

Usage:
    python scripts/ingest_documents.py              # ingest all policies
    python scripts/ingest_documents.py --dry-run    # show what would be ingested

When OpenAI billing credits are available, this script automatically uses
text-embedding-3-small. Without credits, it falls back to deterministic mock
embeddings (retrieval works but results are not semantically ranked).
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.chunker import chunk_documents
from rag.document_loader import load_policy_documents
from rag.vector_store import POLICY_COLLECTION, add_documents, delete_collection, query_collection

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)


def ingest(dry_run: bool = False) -> None:
    """Run the full policy ingestion pipeline."""
    start = time.time()

    # 1. Load policy documents
    logger.info("Loading policy documents from data/policies/ ...")
    docs = load_policy_documents()
    logger.info("  Loaded %d documents: %s", len(docs), [d.metadata["source"] for d in docs])

    # 2. Chunk documents
    logger.info("Chunking documents (CHUNK_SIZE=500, OVERLAP=50) ...")
    chunks = chunk_documents(docs)
    logger.info("  Created %d chunks", len(chunks))

    if dry_run:
        logger.info("Dry run — skipping ChromaDB write.")
        for i, chunk in enumerate(chunks[:3]):
            logger.info("  Sample chunk %d [%s]: %s...", i, chunk.metadata["source"], chunk.page_content[:80])
        return

    # 3. Delete existing collection to avoid stale embeddings
    logger.info("Deleting existing '%s' collection (if any) ...", POLICY_COLLECTION)
    delete_collection(POLICY_COLLECTION)

    # 4. Upsert chunks into ChromaDB
    logger.info("Upserting %d chunks into ChromaDB collection '%s' ...", len(chunks), POLICY_COLLECTION)
    count = add_documents(chunks, collection_name=POLICY_COLLECTION)
    logger.info("  Stored %d chunks", count)

    # 5. Verify with a test query
    logger.info("Verifying — running test query ...")
    results = query_collection("refund policy", collection_name=POLICY_COLLECTION, n_results=2)
    logger.info("  Test query returned %d results", len(results))
    if results:
        logger.info("  Top result source: %s", results[0]["metadata"].get("source"))

    elapsed = time.time() - start
    logger.info("Ingestion complete in %.1fs — %d chunks in '%s'", elapsed, count, POLICY_COLLECTION)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest policy documents into ChromaDB")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to ChromaDB")
    args = parser.parse_args()
    ingest(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
