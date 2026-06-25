"""Customer endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import crud
from database.session import get_db

router = APIRouter()


@router.get("/{customer_id}", summary="Fetch a customer record with recent ticket history")
def get_customer(customer_id: str, db: Session = Depends(get_db)):
    """Return the customer record and their last 20 tickets."""
    customer = crud.get_customer(db, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer '{customer_id}' not found")
    tickets = crud.get_customer_history(db, customer_id, limit=20)
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
