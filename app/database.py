from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timedelta
import enum

# Create database engine - Using SQLite for development
SQLALCHEMY_DATABASE_URL = "sqlite:///./concerts.db"
# For production, you might want to use PostgreSQL:
# SQLALCHEMY_DATABASE_URL = "postgresql://user:password@localhost/dbname"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}  # Only needed for SQLite
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class SeatType(str, enum.Enum):
    GENERAL = "GENERAL"
    VIP = "VIP"
    BACKSTAGE = "BACKSTAGE"

class TicketStatus(str, enum.Enum):
    RESERVED = "RESERVED"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"

class Concert(Base):
    __tablename__ = "concerts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    artist = Column(String, index=True)
    date = Column(DateTime, index=True)
    venue = Column(String)
    genre = Column(String, index=True)
    min_price = Column(Float)
    capacity = Column(Integer)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tickets = relationship("Ticket", back_populates="concert")

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    concert_id = Column(Integer, ForeignKey("concerts.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    seat_type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    booking_time = Column(DateTime, default=datetime.utcnow)
    reservation_expiry = Column(DateTime, nullable=True)
    
    concert = relationship("Concert", back_populates="tickets")
    user = relationship("UserProfile", back_populates="tickets")

class UserProfile(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tickets = relationship("Ticket", back_populates="user")
    
def get_db():
    """
    Creates a new database session for each request and ensures proper cleanup.
    This is a dependency that will be used by FastAPI endpoints.
    
    Yields:
        Session: A SQLAlchemy session object
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def generate_test_data(db):
    """Generate test data for development and testing"""
    
    # Clear existing data
    db.query(Ticket).delete()
    db.query(Concert).delete()
    db.query(UserProfile).delete()
    
    # Create test concerts
    concerts = [
        Concert(
            name="Summer Rock Festival",
            artist="Various Artists",
            date=datetime.now() + timedelta(days=30),
            venue="Central Park",
            genre="Rock",
            min_price=50.0,
            capacity=1000,
            description="Annual summer rock festival featuring multiple bands"
        ),
        Concert(
            name="Classical Night",
            artist="Symphony Orchestra",
            date=datetime.now() + timedelta(days=45),
            venue="Concert Hall",
            genre="Classical",
            min_price=75.0,
            capacity=500,
            description="A night of classical masterpieces"
        )
    ]
    db.bulk_save_objects(concerts)
    
    # Create test users
    users = [
        UserProfile(
            email="john@example.com",
            name="John Doe"
        ),
        UserProfile(
            email="jane@example.com",
            name="Jane Smith"
        )
    ]
    db.bulk_save_objects(users)
    db.commit()

def init_database():
    """Initialize database tables and populate with test data"""
    Base.metadata.create_all(bind=engine)
    
    # Create a database session
    db = SessionLocal()
    try:
        # Generate and insert test data
        generate_test_data(db)
        db.commit()
        return True
    except Exception as e:
        print(f"Error initializing database: {e}")
        db.rollback()
        return False
    finally:
        db.close()