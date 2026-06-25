"""Indexes historical resolved tickets into the ChromaDB historical_tickets collection.

Reads data/history/historical_resolutions.json (full context with agent responses)
and data/history/historical_tickets.json (raw tickets without resolutions), then
embeds and stores them so the agent can retrieve semantically similar past cases.

Run this script once after seed_database.py and again whenever new resolved
tickets should be added to semantic memory.

Usage:
    python scripts/ingest_memory.py              # ingest all historical tickets
    python scripts/ingest_memory.py --dry-run    # show what would be ingested
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.semantic_memory import index_tickets_batch
from rag.vector_store import TICKETS_COLLECTION, delete_collection, query_collection

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

RESOLUTIONS_PATH = Path("data/history/historical_resolutions.json")
TICKETS_PATH = Path("data/history/historical_tickets.json")


def build_tickets_from_resolutions(resolutions: list[dict]) -> list[dict]:
    """Convert historical_resolutions.json records into indexable ticket dicts.

    The text field is a rich combination of subject + message + resolution +
    agent_response so semantic search can match on any of these dimensions.
    """
    tickets = []
    for r in resolutions:
        text_parts = [
            f"Subject: {r.get('subject', '')}",
            f"Message: {r.get('message', '')}",
        ]
        if r.get("resolution"):
            text_parts.append(f"Resolution: {r['resolution']}")
        if r.get("agent_response"):
            text_parts.append(f"Agent response: {r['agent_response']}")

        tickets.append({
            "ticket_id": r["ticket_id"],
            "text": "\n".join(text_parts),
            "subject": r.get("subject", ""),
            "classification": r.get("classification", ""),
            "resolution": r.get("resolution", ""),
            "routing_decision": r.get("routing_decision", ""),
            "escalated": str(r.get("escalated", False)),
        })
    return tickets


def build_tickets_from_raw(raw_tickets: list[dict], existing_ids: set[str]) -> list[dict]:
    """Convert historical_tickets.json records (no resolution) into indexable dicts.

    Only includes tickets whose ticket_id is not already in existing_ids
    (i.e. not already covered by historical_resolutions.json).
    """
    tickets = []
    for t in raw_tickets:
        if t["ticket_id"] in existing_ids:
            continue
        text = f"Subject: {t.get('subject', '')}\nMessage: {t.get('message', '')}"
        tickets.append({
            "ticket_id": t["ticket_id"],
            "text": text,
            "subject": t.get("subject", ""),
            "classification": t.get("classification", ""),
            "resolution": "",
        })
    return tickets


def ingest(dry_run: bool = False) -> None:
    """Load historical tickets and index them into ChromaDB."""
    start = time.time()

    # 1. Load resolutions (rich data — preferred source)
    resolutions: list[dict] = []
    if RESOLUTIONS_PATH.exists():
        resolutions = json.loads(RESOLUTIONS_PATH.read_text())
        logger.info("Loaded %d historical resolutions from %s", len(resolutions), RESOLUTIONS_PATH)
    else:
        logger.warning("File not found: %s", RESOLUTIONS_PATH)

    # 2. Load raw historical tickets (fallback / additional coverage)
    raw_tickets: list[dict] = []
    if TICKETS_PATH.exists():
        raw_tickets = json.loads(TICKETS_PATH.read_text())
        logger.info("Loaded %d raw historical tickets from %s", len(raw_tickets), TICKETS_PATH)
    else:
        logger.warning("File not found: %s", TICKETS_PATH)

    # 3. Build indexable dicts
    resolution_tickets = build_tickets_from_resolutions(resolutions)
    resolution_ids = {t["ticket_id"] for t in resolution_tickets}
    raw_only_tickets = build_tickets_from_raw(raw_tickets, resolution_ids)

    all_tickets = resolution_tickets + raw_only_tickets
    logger.info(
        "Total tickets to index: %d (%d with resolutions, %d raw only)",
        len(all_tickets),
        len(resolution_tickets),
        len(raw_only_tickets),
    )

    if dry_run:
        logger.info("Dry run — skipping ChromaDB write.")
        for t in all_tickets[:3]:
            logger.info("  [%s] %s: %s...", t["ticket_id"], t["classification"], t["text"][:80])
        return

    # 4. Clear existing collection and re-index
    logger.info("Deleting existing '%s' collection (if any) ...", TICKETS_COLLECTION)
    delete_collection(TICKETS_COLLECTION)

    logger.info("Indexing %d tickets into '%s' ...", len(all_tickets), TICKETS_COLLECTION)
    count = index_tickets_batch(all_tickets)
    logger.info("  Indexed %d tickets", count)

    # 5. Verify
    if count > 0:
        results = query_collection("refund request", collection_name=TICKETS_COLLECTION, n_results=2)
        logger.info("Test query returned %d results", len(results))
        if results:
            logger.info("  Top result: [%s] %s", results[0]["metadata"].get("ticket_id"), results[0]["metadata"].get("subject", ""))

    elapsed = time.time() - start
    logger.info("Memory ingestion complete in %.1fs — %d tickets indexed", elapsed, count)


def main() -> None:
    parser = argparse.ArgumentParser(description="Index historical tickets into ChromaDB semantic memory")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to ChromaDB")
    args = parser.parse_args()
    ingest(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
