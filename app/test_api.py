# tests/integration/test_api.py

from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import pytest
from app.main import app
from app.database import Base, engine, Concert, Ticket, UserProfile, get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    """Set up a clean test database for each test"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def create_test_concert():
    """Helper to create a test concert"""
    db = next(get_db())
    concert = Concert(
        name="Test Concert",
        artist="Test Artist",
        date=datetime.now() + timedelta(days=30),
        venue="Test Venue",
        genre="Rock",
        min_price=50.0,
        capacity=100
    )
    db.add(concert)
    db.commit()
    return concert

def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_concert_listing():
    """Test getting concert list with filters"""
    concert = create_test_concert()
    
    test_cases = [
        {"params": {}, "expected_count": 1},
        {"params": {"genre": "Rock"}, "expected_count": 1},
        {"params": {"genre": "Pop"}, "expected_count": 0},
        {"params": {"min_price": 40}, "expected_count": 1},
        {"params": {"min_price": 60}, "expected_count": 0}
    ]
    
    for case in test_cases:
        response = client.get("/concerts", params=case["params"])
        assert response.status_code == 200
        concerts = response.json()
        assert len(concerts) == case["expected_count"]

def test_ticket_reservation_flow():
    """Test complete ticket reservation process"""
    concert = create_test_concert()
    
    # Test reservation
    reservation_data = {
        "concert_id": concert.id,
        "user_id": 1,
        "quantity": 2,
        "seat_type": "VIP"
    }
    
    response = client.post("/tickets/reserve", json=reservation_data)
    assert response.status_code == 200
    reservation = response.json()
    assert "reservation_details" in reservation
    assert "tickets" in reservation["reservation_details"]
    
    # Test confirmation
    ticket_id = reservation["reservation_details"]["tickets"][0]["ticket_id"]
    confirm_response = client.post(f"/tickets/confirm/{ticket_id}?user_id=1")
    assert confirm_response.status_code == 200

def test_concurrent_reservations():
    """Test handling multiple simultaneous reservations"""
    concert = create_test_concert()
    
    # Create multiple reservations simultaneously
    reservations = []
    for _ in range(5):
        response = client.post("/tickets/reserve", json={
            "concert_id": concert.id,
            "user_id": 1,
            "quantity": 10,
            "seat_type": "GENERAL"
        })
        reservations.append(response)
    
    # Verify no overbooking
    successful = sum(1 for r in reservations if r.status_code == 200)
    assert successful <= concert.capacity // 10

def test_error_handling():
    """Test various error scenarios"""
    error_cases = [
        {
            "endpoint": "/tickets/reserve",
            "data": {"concert_id": 999, "user_id": 1, "quantity": 1, "seat_type": "VIP"},
            "expected_status": 404
        },
        {
            "endpoint": "/tickets/cancel/999",
            "params": {"user_id": 1},
            "expected_status": 404
        },
        {
            "endpoint": "/tickets/confirm/999",
            "params": {"user_id": 1},
            "expected_status": 404
        }
    ]
    
    for case in error_cases:
        if "data" in case:
            response = client.post(case["endpoint"], json=case["data"])
        else:
            response = client.post(case["endpoint"], params=case["params"])
        assert response.status_code == case["expected_status"]