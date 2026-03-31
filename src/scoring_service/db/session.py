from __future__ import annotations
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from scoring_service.config import Settings

def create_session_factory(settings: Settings):
    engine = create_engine(settings.database_url, echo=settings.db_echo, pool_pre_ping=True)
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False)
