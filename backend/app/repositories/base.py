"""Database session management and base repository."""
from contextlib import contextmanager
from typing import Generator
import os

from sqlmodel import SQLModel, Session, create_engine

from app.core.logging import setup_logging

logger = setup_logging(__name__)


class DatabaseSessionManager:
    """Manages the database session."""

    def __init__(self, db_url: str = None):
        if db_url is None:
            db_path = os.getenv("DATABASE_NAME", "narrative_storage/narrative.db")
            db_url = f'sqlite:///{db_path}'
            db_dir = os.path.dirname(db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)

        self.engine = create_engine(
            db_url,
            echo=False,
            connect_args={"timeout": 60},
            pool_size=5,
            max_overflow=10
        )
        self.create_tables()

    def create_tables(self):
        """Create database tables if they don't exist."""
        SQLModel.metadata.create_all(self.engine)

    def get_session(self) -> Session:
        """Get a new session."""
        return Session(self.engine)

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Provide a transactional scope around a series of operations."""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Session rollback due to exception: {e}")
            raise
        finally:
            session.close()


class BaseRepository:
    """Base repository class with session management."""

    def __init__(self, session: Session):
        self.session = session