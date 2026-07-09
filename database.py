"""
Axiom - User Database connection/session setup.

Uses SQLite for the MVP (zero-config, single file, plenty fast for a
launch-scale user base). Swapping to Postgres later only requires
changing DATABASE_URL -- the models and crud layer don't change.
"""

import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "axiom_users.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# check_same_thread=False is needed for SQLite when a session might be used
# across the async/threaded context of a web framework (e.g. FastAPI/Flask).
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db():
    """Create all tables if they don't already exist."""
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session():
    """Context-managed session: commits on success, rolls back on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()