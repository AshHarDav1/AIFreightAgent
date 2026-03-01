"""Database connection and session management"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from src.database.models import Base
from src.utils.config import config
from src.utils.logger import logger


class Database:
    """Database connection manager"""
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or config.settings.database_url
        self.engine = create_engine(
            self.database_url,
            echo=config.get('database.echo', False),
            pool_size=config.get('database.pool_size', 5)
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        logger.info(f"Database initialized: {self.database_url}")
    
    def create_tables(self):
        """Create all database tables"""
        Base.metadata.create_all(self.engine)
        logger.info("Database tables created")
    
    def drop_tables(self):
        """Drop all database tables"""
        Base.metadata.drop_all(self.engine)
        logger.warning("Database tables dropped")
    
    @contextmanager
    def get_session(self):
        """Get database session context manager"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def get_session_direct(self) -> Session:
        """Get database session directly (caller responsible for closing)"""
        return self.SessionLocal()


# Global database instance
db = Database()
