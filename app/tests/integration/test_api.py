import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from database import SessionLocal, Concert, UserProfile, init_database
from main import app

client = TestClient(app)

@pytest.fixture(scope="module")
def test_db():
    # Initialize test database
    init_database()
    db = SessionLocal()
    yield db
    db.close()

@pytest.fixture(scope="module")
def test_concert(test_db):
    concert = Concert(
        name="Test Concert",
        artist="Test Artist",
        date=datetime.now() + timedelta(days=30),
        venue="Test Venue",
        genre="Rock",
        min_price=50.0,
        capacity=100,
        description="Test concert description"
    )
    test_db.add(concert)
    test_db.commit()
    return concert

@pytest.fixture(scope="module")
def test_user(test_db):
    user = UserProfile(
        email="test@example.com",
        name="Test User"
    )
    test_db.add(user)
    test_db.commit()
    return user

def test_root_endpoint():
    """Test the root endpoint returns API information"""
    response = client.get("/")
    assert response.status_code == 200
    assert "Concert Ticket Booking API" in response.json()["message"]
    assert "version" in response.json()

def test_health_check():
    """Test the health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_get_concerts(test_concert):
    """Test retrieving available concerts"""
    response = client.get("/concerts")
    assert response.status_code == 200
    concerts = response.json()
    assert len(concerts) > 0
    assert any(c["name"] == "Test Concert" for c in concerts)

def test_ticket_reservation_flow(test_concert, test_user):
    """Test the complete ticket reservation and confirmation flow"""
    reservation_data = {
        "concert_id": test_concert.id,
        "user_id": test_user.id,
        "quantity": 2,
        "seat_type": "VIP"
    }
    
    reserve_response = client.post("/tickets/reserve", json=reservation_data)
    assert reserve_response.status_code == 200
    reservation = reserve_response.json()
    assert "reservation_details" in reservation
    assert len(reservation["reservation_details"]["tickets"]) == 2
    
    # Confirm the first reserved ticket
    print("="*1000)
    print("reservation")
    print(reservation)
    ticket_id = reservation["reservation_details"]["tickets"][0]["ticket_id"]
    confirm_response = client.post(
        f"/tickets/confirm/{ticket_id}",
        params={"user_id": test_user.id}
    )
    assert confirm_response.status_code == 200
    assert "Ticket confirmed successfully" in confirm_response.json()["message"]

def test_ticket_booking_and_cancellation(test_concert, test_user):
    """Test booking tickets and then cancelling them"""
    # Print test data for debugging
    print("\n=== Debug Information ===")
    print(f"Test Concert ID: {test_concert.id}")
    print(f"Test User ID: {test_user.id}")

    # Step 1: Book tickets
    booking_data = {
        "concert_id": test_concert.id,
        "user_id": test_user.id,
        "quantity": 1,
        "seat_type": "GENERAL"
    }
    
    print("\nRequest Data:")
    print(booking_data)
    
    book_response = client.post("/tickets/book", json=booking_data)
    print("\nResponse Status Code:", book_response.status_code)
    
    tickets = book_response.json()
    print("\nFull Response Content:")
    print(tickets)
    
    if isinstance(tickets, list):
        print("\nFirst Ticket Keys:")
        print(tickets[0].keys())
    
    # Now try to access ticket_id with debug info
    try:
        ticket_id = tickets[0]["ticket_id"]
        print(f"\nFound ticket_id: {ticket_id}")
    except KeyError as e:
        print(f"\nKeyError when accessing ticket_id. Available keys: {tickets[0].keys()}")
        raise  # Re-raise the exception to fail the test
        
    # Step 2: Cancel the booked ticket
    cancel_response = client.post(
        f"/tickets/cancel/{ticket_id}",
        params={"user_id": test_user.id}
    )
    assert cancel_response.status_code == 200
    assert "Ticket cancelled successfully" in cancel_response.json()["message"]

def test_concert_filtering(test_concert):
    """Test concert filtering capabilities"""
    # Test genre filter
    response = client.get("/concerts", params={"genre": "Rock"})
    assert response.status_code == 200
    assert len(response.json()) > 0
    
    # Test price filter
    response = client.get("/concerts", params={"min_price": 40.0})
    assert response.status_code == 200
    concerts = response.json()
    assert all(c["min_price"] >= 40.0 for c in concerts)

if __name__ == "__main__":
    pytest.main(["-v"])