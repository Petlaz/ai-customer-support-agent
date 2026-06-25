"""Seeds the SQLite database with sample customers and tickets from data/.

Loads:
  - data/history/customer_history.json   → customers table
  - data/tickets/sample_tickets.json     → tickets table (current tickets)
  - data/history/historical_tickets.json → tickets table (historical tickets)

Safe to run multiple times — uses upsert logic (skips existing records).

Usage:
    python scripts/seed_database.py              # seed all data
    python scripts/seed_database.py --dry-run    # show counts without writing
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import create_tables
from database.models import Customer, Ticket
from database.session import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

CUSTOMER_HISTORY_PATH = Path("data/history/customer_history.json")
SAMPLE_TICKETS_PATH = Path("data/tickets/sample_tickets.json")
HISTORICAL_TICKETS_PATH = Path("data/history/historical_tickets.json")


def seed_customers(db, records: list[dict], dry_run: bool) -> int:
    """Upsert customer records from customer_history.json."""
    created = 0
    for record in records:
        customer_id = record["customer_id"]
        existing = db.query(Customer).filter_by(customer_id=customer_id).first()
        if existing:
            continue
        if not dry_run:
            customer = Customer(
                customer_id=customer_id,
                name=record.get("name"),
                email=record.get("email"),
            )
            db.add(customer)
        created += 1
    if not dry_run:
        db.commit()
    return created


def seed_tickets(db, records: list[dict], dry_run: bool) -> int:
    """Upsert ticket records from a tickets JSON array."""
    created = 0
    for record in records:
        ticket_id = record["ticket_id"]
        existing = db.query(Ticket).filter_by(ticket_id=ticket_id).first()
        if existing:
            continue

        # Ensure parent customer exists (create minimal record if needed)
        customer_id = record["customer_id"]
        if not dry_run:
            if not db.query(Customer).filter_by(customer_id=customer_id).first():
                db.add(Customer(customer_id=customer_id))
                db.flush()

            ticket = Ticket(
                ticket_id=ticket_id,
                customer_id=customer_id,
                subject=record.get("subject", ""),
                message=record.get("message", ""),
                channel=record.get("channel", "email"),
                priority=record.get("priority", "medium"),
                classification=record.get("classification"),
                confidence_score=record.get("confidence_score"),
                status=record.get("status", "open"),
            )
            db.add(ticket)
        created += 1

    if not dry_run:
        db.commit()
    return created


def seed(dry_run: bool = False) -> None:
    """Run all seeding operations."""
    # Ensure tables exist
    create_tables()

    db = SessionLocal()
    try:
        # 1. Seed customers
        if CUSTOMER_HISTORY_PATH.exists():
            customer_records = json.loads(CUSTOMER_HISTORY_PATH.read_text())
            n = seed_customers(db, customer_records, dry_run)
            logger.info("%s %d customers from %s", "Would create" if dry_run else "Created", n, CUSTOMER_HISTORY_PATH)
        else:
            logger.warning("File not found: %s", CUSTOMER_HISTORY_PATH)

        # 2. Seed sample (current) tickets
        if SAMPLE_TICKETS_PATH.exists():
            sample_tickets = json.loads(SAMPLE_TICKETS_PATH.read_text())
            n = seed_tickets(db, sample_tickets, dry_run)
            logger.info("%s %d sample tickets from %s", "Would create" if dry_run else "Created", n, SAMPLE_TICKETS_PATH)
        else:
            logger.warning("File not found: %s", SAMPLE_TICKETS_PATH)

        # 3. Seed historical tickets
        if HISTORICAL_TICKETS_PATH.exists():
            historical_tickets = json.loads(HISTORICAL_TICKETS_PATH.read_text())
            n = seed_tickets(db, historical_tickets, dry_run)
            logger.info("%s %d historical tickets from %s", "Would create" if dry_run else "Created", n, HISTORICAL_TICKETS_PATH)
        else:
            logger.warning("File not found: %s", HISTORICAL_TICKETS_PATH)

        # 4. Print summary
        if not dry_run:
            customer_count = db.query(Customer).count()
            ticket_count = db.query(Ticket).count()
            logger.info("Database seeding complete — %d customers, %d tickets in DB", customer_count, ticket_count)

    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the SQLite database with sample data")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to the database")
    args = parser.parse_args()
    seed(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
