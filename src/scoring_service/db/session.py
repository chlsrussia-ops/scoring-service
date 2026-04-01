from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from scoring_service.config import Settings


def create_session_factory(settings: Settings) -> tuple:
    engine = create_engine(
        settings.database_url,
        echo=settings.db_echo,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return engine, factory


def get_db(session_factory) -> Session:  # type: ignore[type-arg]
    """Yield a session, ensuring cleanup."""
    db = session_factory()
    try:
        yield db  # type: ignore[misc]
    finally:
        db.close()
