"""SQLAlchemy database engine and session factory.

Reads DATABASE_URL from env — defaults to a local SQLite file for development.
Set DATABASE_URL=postgresql://user:pass@host/db on Render for production.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

_url = os.getenv("DATABASE_URL", "sqlite:///./dac_underwriting.db")
# Render injects "postgres://..." but SQLAlchemy 2.x requires "postgresql://"
if _url.startswith("postgres://"):
    _url = _url.replace("postgres://", "postgresql://", 1)

DATABASE_URL = _url

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: yields a DB session, closes on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
