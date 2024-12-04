from fastapi.testclient import TestClient
from main import app
from database import Base, engine, Concert, Ticket, UserProfile
from datetime import datetime, timedelta
import pytest
import time

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    """Set up test database before each test"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_ticket_reservation():
    """Test the complete ticket reservation flow"""
    # Create test concert
    concert = Concert(
        name="Test Concert",
        artist="Test Artist",
        date=datetime.now() + timedelta(days=30),
        venue="Test Venue",
        genre="Rock",
        min_price=50.0,
        capacity=100
    )
    db = next(get_db())
    db.add(concert)
    db.commit()
    
    # Test reservation
    reservation_request = {
        "concert_id": concert.id,
        "user_id": 1,
        "quantity": 2,
        "seat_type": "VIP"
    }
    
    # Make reservation
    response = client.post("/tickets/reserve", json=reservation_request)
    assert response.status_code == 200
    reservation = response.json()
    
    # Verify response structure
    assert "reservation_details" in reservation
    assert "tickets" in reservation["reservation_details"]
    assert len(reservation["reservation_details"]["tickets"]) > 0
    
    # Get ticket ID (adjusting to match actual response structure)
    ticket = reservation["reservation_details"]["tickets"][0]
    ticket_id = ticket["ticket_id"]  # Changed from 'id' to 'ticket_id'
    
    # Test confirmation
    confirmation_response = client.post(f"/tickets/confirm/{ticket_id}?user_id=1")
    assert confirmation_response.status_code == 200
    assert confirmation_response.json()["message"] == "Ticket confirmed successfully"
    
    # Verify ticket status in database
    db = next(get_db())
    confirmed_ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    assert confirmed_ticket is not None
    assert confirmed_ticket.status == "CONFIRMED"

def test_reservation_validation():
    """Test validation of reservation requests"""
    invalid_requests = [
        {
            "concert_id": 999,  # Non-existent concert
            "user_id": 1,
            "quantity": 2,
            "seat_type": "VIP"
        },
        {
            "concert_id": 1,
            "user_id": 1,
            "quantity": 0,  # Invalid quantity
            "seat_type": "VIP"
        },
        {
            "concert_id": 1,
            "user_id": 1,
            "quantity": 2,
            "seat_type": "INVALID_TYPE"  # Invalid seat type
        }
    ]
    
    for req in invalid_requests:
        response = client.post("/tickets/reserve", json=req)
        assert response.status_code in [400, 404]  # Either bad request or not found

def test_reservation_expiration():
    """Test that reservations expire correctly"""
    # Create test concert
    concert = Concert(
        name="Test Concert",
        artist="Test Artist",
        date=datetime.now() + timedelta(days=30),
        venue="Test Venue",
        genre="Rock",
        min_price=50.0,
        capacity=100
    )
    db = next(get_db())
    db.add(concert)
    db.commit()
    
    # Create expired ticket
    expired_ticket = Ticket(
        concert_id=concert.id,
        user_id=1,
        seat_type="VIP",
        status="RESERVED",
        amount=125.0,
        booking_time=datetime.now() - timedelta(minutes=20),  # 20 minutes ago
        reservation_expiry=datetime.now() - timedelta(minutes=5)  # Expired 5 minutes ago
    )
    db.add(expired_ticket)
    db.commit()
    
    # Try to confirm expired ticket
    response = client.post(f"/tickets/confirm/{expired_ticket.id}?user_id=1")
    assert response.status_code == 400
    assert "expired" in response.json()["detail"].lower()

# Add this function at the end of test_api.py
def get_db():
    """Database session fixture"""
    from database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()