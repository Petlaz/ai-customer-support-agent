"""SQLAlchemy session factory and FastAPI get_db() dependency."""
from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker

from database.db import engine

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a DB session and ensures it is closed after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
