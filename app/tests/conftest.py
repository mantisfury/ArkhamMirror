import pytest
from unittest.mock import MagicMock
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.arkham.services.db.models import Base

@pytest.fixture
def mock_session():
    """
    Fixture for a mocked SQLAlchemy session.
    Provides a MagicMock object that mimics a database session.
    """
    mock_db_session = MagicMock(spec=Session)
    return mock_db_session

@pytest.fixture
def in_memory_db():
    """
    Fixture for an in-memory SQLite database for integration-like unit tests.
    Creates a new database for each test, ensuring isolation.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(engine)

