"""Customer endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.models import Customer, Ticket
from database.session import get_db

router = APIRouter()


@router.get("/{customer_id}", summary="Fetch a customer record with recent ticket history")
def get_customer(customer_id: str, db: Session = Depends(get_db)):
    """Return the customer record and their last 20 tickets."""
    customer = db.query(Customer).filter_by(customer_id=customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer '{customer_id}' not found")
    tickets = (
        db.query(Ticket)
        .filter_by(customer_id=customer_id)
        .order_by(Ticket.created_at.desc())
        .limit(20)
        .all()
    )
    return {
        "customer_id": customer.customer_id,
        "name": customer.name,
        "email": customer.email,
        "created_at": customer.created_at.isoformat() if customer.created_at else None,
        "total_tickets": len(tickets),
        "recent_tickets": [
            {
                "ticket_id": t.ticket_id,
                "subject": t.subject,
                "classification": t.classification,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tickets
        ],
    }
