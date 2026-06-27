"""Database connection: engine, session factory, and Base.

The connection string comes from DATABASE_URL in the environment (loaded from
.env via python-dotenv), so the same code points at a local container today and
at the docker-compose `postgres` service in Step 4 — only the env var changes.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://cinemind:cinemind@127.0.0.1:5432/cinemind",
)

engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
