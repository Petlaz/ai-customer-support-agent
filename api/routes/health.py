"""Health-check endpoint."""
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends

from database.session import get_db

router = APIRouter()


@router.get("/health", summary="Liveness check")
def health_check(db: Session = Depends(get_db)):
    """Return OK when the app and database are reachable."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "version": "1.0.0", "database": "ok"}
