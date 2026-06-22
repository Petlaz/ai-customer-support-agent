"""SQLAlchemy engine, declarative Base, and table creation utility."""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase

from config.settings import settings

# Ensure the data directory exists (required for SQLite)
if settings.database_url.startswith("sqlite"):
    os.makedirs("data", exist_ok=True)

engine = create_engine(
    settings.database_url,
    # check_same_thread=False is required for SQLite in multi-threaded contexts (FastAPI)
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)


class Base(DeclarativeBase):
    pass


def create_tables() -> None:
    """Create all tables defined in SQLAlchemy models. Safe to call multiple times."""
    Base.metadata.create_all(bind=engine)
