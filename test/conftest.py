import pytest
from app.database import Base, engine, SessionLocal
from app.models.entities import Account, AccountType, EscrowOrder, EscrowStatus
from decimal import Decimal

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    # Crea tablas en PostgreSQL local
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()