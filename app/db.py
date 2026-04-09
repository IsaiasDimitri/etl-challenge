from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()

source_engine = create_engine(settings.source_db_url, future=True)
target_engine = create_engine(settings.target_db_url, future=True)

SourceSessionLocal = sessionmaker(bind=source_engine, autoflush=False, autocommit=False)
TargetSessionLocal = sessionmaker(bind=target_engine, autoflush=False, autocommit=False)


def get_source_session() -> Generator[Session, None, None]:
    session = SourceSessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_target_session() -> Generator[Session, None, None]:
    session = TargetSessionLocal()
    try:
        yield session
    finally:
        session.close()
