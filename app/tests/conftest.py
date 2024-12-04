import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from scripts.test_database import generate_test_data

@pytest.fixture(scope="session")
def engine():
    """Create test database engine"""
    SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    return engine

@pytest.fixture(scope="function")
def db_session(engine):
    """Create a fresh database session for each test"""
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    
    # Generate test data for each test
    generate_test_data(session)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

# tests/integration/test_concert_api.py
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from main import app
from app.database import Concert, Ticket, UserProfile

client = TestClient(app)

def test_get_concerts(db_session):
    """Test getting list of concerts"""
    response = client.get("/concerts")
    assert response.status_code == 200
    concerts = response.json()
    assert len(concerts) > 0
    assert "name" in concerts[0]
    assert "artist" in concerts[0]

def test_book_ticket(db_session):
    """Test booking a ticket"""
    # Get a concert and user from test data
    concert = db_session.query(Concert).first()
    user = db_session.query(UserProfile).first()
    
    ticket_request = {
        "concert_id": concert.id,
        "user_id": user.id,
        "quantity": 2,
        "seat_type": "VIP"
    }
    
    response = client.post("/tickets/book", json=ticket_request)
    assert response.status_code == 200
    tickets = response.json()
    assert len(tickets) == 2
    assert tickets[0]["status"] == "RESERVED"

def test_cancel_ticket(db_session):
    """Test canceling a ticket"""
    # First book a ticket
    concert = db_session.query(Concert).first()
    user = db_session.query(UserProfile).first()
    
    ticket = Ticket(
        concert_id=concert.id,
        user_id=user.id,
        seat_type="GENERAL",
        status="RESERVED",
        amount=50.0,
        booking_time=datetime.now()
    )
    db_session.add(ticket)
    db_session.commit()
    
    response = client.post(f"/tickets/cancel/{ticket.id}?user_id={user.id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Ticket cancelled successfully"
    
    # Verify ticket status in database
    updated_ticket = db_session.query(Ticket).filter_by(id=ticket.id).first()
    assert updated_ticket.status == "CANCELLED"

def test_book_invalid_concert(db_session):
    """Test booking a ticket for non-existent concert"""
    ticket_request = {
        "concert_id": 9999,  # Non-existent concert
        "user_id": 1,
        "quantity": 1,
        "seat_type": "GENERAL"
    }
    
    response = client.post("/tickets/book", json=ticket_request)
    assert response.status_code == 404
    assert "Concert not found" in response.json()["detail"]

def test_cancel_expired_ticket(db_session):
    """Test canceling a ticket too close to concert date"""
    concert = db_session.query(Concert).first()
    concert.date = datetime.now() + timedelta(hours=12)  # Concert in 12 hours
    user = db_session.query(UserProfile).first()
    
    ticket = Ticket(
        concert_id=concert.id,
        user_id=user.id,
        seat_type="GENERAL",
        status="RESERVED",
        amount=50.0,
        booking_time=datetime.now()
    )
    db_session.add(ticket)
    db_session.commit()
    
    response = client.post(f"/tickets/cancel/{ticket.id}?user_id={user.id}")
    assert response.status_code == 400
    assert "Cannot cancel tickets less than 24 hours before concert" in response.json()["detail"]