from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, desc
from datetime import datetime, timedelta
import logging
from typing import List, Optional
from pydantic import BaseModel
from database import get_db, Concert, Ticket, UserProfile, init_database

# Data Models for Request/Response
class TicketRequest(BaseModel):
    concert_id: int
    user_id: int
    quantity: int
    seat_type: str  # 'VIP', 'GENERAL', 'BACKSTAGE'

class TicketResponse(BaseModel):
    ticket_id: int
    concert_id: int
    user_id: int
    status: str  # 'RESERVED', 'CONFIRMED', 'CANCELLED'
    amount: float
    seat_type: str
    booking_time: datetime
    
class ErrorResponse(BaseModel):
    detail: str

# Initialize FastAPI app
app = FastAPI()

# Configure logging
log_filename = f"concert_booking_{datetime.now().strftime('%d_%m_%Y')}.log"
logging.basicConfig(
    filename=log_filename,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Cache for concert availability
availability_cache = {}
CACHE_DURATION = timedelta(minutes=5)

# Initialize monitoring
from monitoring import ServiceMonitor
service_monitor = ServiceMonitor()

@app.on_event("startup")
async def startup_event():
    """Initialize database and required tables on startup"""
    init_database()

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Concert Ticket Booking API",
        "version": "1.0",
        "endpoints": [
            "/concerts",
            "/tickets/book",
            "/tickets/cancel",
            "/health"
        ]
    }

@app.get("/health")
async def health_check():
    """Health check endpoint with monitoring metrics"""
    metrics = service_monitor.get_metrics()
    return {
        "status": "healthy",
        "metrics": metrics
    }
    
# Add these new status constants to your existing code
TICKET_STATUS = {
    "RESERVED": "RESERVED",      # Initial temporary hold
    "CONFIRMED": "CONFIRMED",    # Payment completed
    "CANCELLED": "CANCELLED",    # Cancelled by user
    "EXPIRED": "EXPIRED"        # Reservation timeout
}

# Add this new model for reservation requests
class ReservationRequest(BaseModel):
    concert_id: int
    user_id: int
    quantity: int
    seat_type: str

@app.post("/tickets/reserve", 
    response_model=dict,
    responses={
        404: {
            "model": ErrorResponse,
            "description": "Concert Not Found",
            "content": {
                "application/json": {
                    "examples": {
                        "concert_not_found": {
                            "summary": "Concert Does Not Exist",
                            "value": {
                                "detail": "Concert not found",
                                "error_code": "CONCERT_NOT_FOUND"
                            }
                        }
                    }
                }
            }
        },
        400: {
            "model": ErrorResponse,
            "description": "Bad Request - Validation Error",
            "content": {
                "application/json": {
                    "examples": {
                        "concert_passed": {
                            "summary": "Concert Already Occurred",
                            "value": {
                                "detail": "Concert has already taken place",
                                "error_code": "CONCERT_EXPIRED"
                            }
                        },
                        "insufficient_tickets": {
                            "summary": "Insufficient Ticket Availability",
                            "value": {
                                "detail": "Not enough tickets available",
                                "error_code": "INSUFFICIENT_TICKETS"
                            }
                        }
                    }
                }
            }
        },
        500: {
            "model": ErrorResponse,
            "description": "Internal Server Error",
            "content": {
                "application/json": {
                    "examples": {
                        "reservation_error": {
                            "summary": "Ticket Reservation Failed",
                            "value": {
                                "detail": "Error reserving tickets",
                                "error_code": "RESERVATION_FAILED"
                            }
                        }
                    }
                }
            }
        }
    })
async def reserve_ticket(
    reservation_request: ReservationRequest,
    db: Session = Depends(get_db)
):
    """
    Reserve tickets for a concert with a temporary hold.
    
    Reservations expire after 15 minutes if not confirmed.
    
    Possible Errors:
    - 404: Concert not found
    - 400: Concert already passed or insufficient tickets
    - 500: Internal server error during reservation
    """
    try:
        start_time = datetime.now()
        
        # Check concert existence and availability
        concert = db.query(Concert).filter(Concert.id == reservation_request.concert_id).first()
        if not concert:
            raise HTTPException(status_code=404, detail="Concert not found")
            
        # Check if concert date has passed
        if concert.date < datetime.now():
            raise HTTPException(status_code=400, detail="Concert has already taken place")
            
        # Check ticket availability
        available_tickets = get_available_tickets(
            db,
            concert.id,
            reservation_request.seat_type
        )
        
        if available_tickets < reservation_request.quantity:
            raise HTTPException(
                status_code=400,
                detail="Not enough tickets available"
            )
            
        # Create temporary reservation records
        tickets = []
        reservation_expiry = datetime.now() + timedelta(minutes=15)
        
        for _ in range(reservation_request.quantity):
            ticket = Ticket(
                concert_id=concert.id,
                user_id=reservation_request.user_id,
                seat_type=reservation_request.seat_type,
                status="RESERVED",
                amount=get_ticket_price(concert, reservation_request.seat_type),
                booking_time=datetime.now(),
                reservation_expiry=reservation_expiry
            )
            db.add(ticket)
            tickets.append(ticket)
            
        db.commit()
        
        # Transform tickets to response format
        ticket_responses = [
            {
                "ticket_id": t.id,
                "concert_id": t.concert_id,
                "user_id": t.user_id,
                "status": t.status,
                "amount": t.amount,
                "seat_type": t.seat_type,
                "booking_time": t.booking_time,
                "reservation_expiry": t.reservation_expiry
            }
            for t in tickets
        ]
        
        return {
            "message": "Tickets reserved successfully",
            "reservation_details": {
                "tickets": ticket_responses,
                "expires_at": reservation_expiry,
                "payment_required_by": reservation_expiry.isoformat()
            }
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logging.error(f"Error reserving tickets: {str(e)}")
        raise HTTPException(status_code=500, detail="Error reserving tickets")
    finally:
        db.close()

@app.post("/tickets/confirm/{ticket_id}")
async def confirm_ticket(
    ticket_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Confirm a reserved ticket by completing the payment.
    Must be done before reservation expires.
    """
    try:
        start_time = datetime.now()
        
        # Get ticket reservation
        ticket = db.query(Ticket).filter(
            Ticket.id == ticket_id,
            Ticket.user_id == user_id,
            Ticket.status == TICKET_STATUS["RESERVED"]
        ).first()
        
        if not ticket:
            raise HTTPException(
                status_code=404,
                detail="Reserved ticket not found or unauthorized"
            )
            
        # Check if reservation has expired
        if datetime.now() > ticket.reservation_expiry:
            ticket.status = TICKET_STATUS["EXPIRED"]
            db.commit()
            raise HTTPException(
                status_code=400,
                detail="Ticket reservation has expired"
            )
            
        # Update ticket status to confirmed
        ticket.status = TICKET_STATUS["CONFIRMED"]
        db.commit()
        
        # Clear availability cache
        clear_availability_cache(ticket.concert_id)
        
        # Update monitoring
        service_monitor.record_request(
            duration=(datetime.now() - start_time).total_seconds(),
            success=True
        )
        
        logging.info(f"Successfully confirmed ticket {ticket_id}")
        return {
            "message": "Ticket confirmed successfully",
            "ticket": ticket
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logging.error(f"Error confirming ticket: {str(e)}")
        service_monitor.record_request(
            duration=(datetime.now() - start_time).total_seconds(),
            success=False
        )
        raise HTTPException(status_code=500, detail="Error confirming ticket")
    finally:
        db.close()

# Add this to your existing Ticket model in database.py

@app.get("/concerts")
async def get_concerts(
    skip: int = 0,
    limit: int = 10,
    genre: Optional[str] = None,
    min_price: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """
    Get available concerts with optional filtering
    """
    try:
        start_time = datetime.now()
        
        # Build query with filters
        query = db.query(Concert).filter(Concert.date >= datetime.now())
        
        if genre:
            query = query.filter(Concert.genre == genre)
        if min_price is not None:
            query = query.filter(Concert.min_price >= min_price)
            
        # Apply pagination
        concerts = query.offset(skip).limit(limit).all()
        
        # Update monitoring
        service_monitor.record_request(
            duration=(datetime.now() - start_time).total_seconds(),
            success=True
        )
        
        logging.info(f"Successfully retrieved {len(concerts)} concerts")
        return concerts
        
    except Exception as e:
        logging.error(f"Error retrieving concerts: {str(e)}")
        service_monitor.record_request(
            duration=(datetime.now() - start_time).total_seconds(),
            success=False
        )
        raise HTTPException(status_code=500, detail="Error retrieving concerts")

@app.post("/tickets/book")
async def book_ticket(
    ticket_request: TicketRequest,
    db: Session = Depends(get_db)
):
    """
    Book tickets for a concert
    """
    try:
        start_time = datetime.now()
        
        # Check concert existence and availability
        concert = db.query(Concert).filter(Concert.id == ticket_request.concert_id).first()
        if not concert:
            raise HTTPException(status_code=404, detail="Concert not found")
            
        # Check if concert date has passed
        if concert.date < datetime.now():
            raise HTTPException(status_code=400, detail="Concert has already taken place")
            
        # Check ticket availability
        available_tickets = get_available_tickets(
            db,
            concert.id,
            ticket_request.seat_type
        )
        
        if available_tickets < ticket_request.quantity:
            raise HTTPException(
                status_code=400,
                detail="Not enough tickets available"
            )
            
        # Create ticket records
        tickets = []
        for _ in range(ticket_request.quantity):
            ticket = Ticket(
                concert_id=concert.id,
                user_id=ticket_request.user_id,
                seat_type=ticket_request.seat_type,
                status="RESERVED",
                amount=get_ticket_price(concert, ticket_request.seat_type),
                booking_time=datetime.now()
            )
            db.add(ticket)
            tickets.append(ticket)
            
        db.commit()
        
        # Clear availability cache
        clear_availability_cache(concert.id)
        
        # Update monitoring
        service_monitor.record_request(
            duration=(datetime.now() - start_time).total_seconds(),
            success=True
        )
        
        logging.info(f"Successfully booked {len(tickets)} tickets for concert {concert.id}")
        return tickets
        
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logging.error(f"Error booking tickets: {str(e)}")
        service_monitor.record_request(
            duration=(datetime.now() - start_time).total_seconds(),
            success=False
        )
        raise HTTPException(status_code=500, detail="Error booking tickets")
    finally:
        db.close()

@app.post("/tickets/cancel/{ticket_id}")
async def cancel_ticket(
    ticket_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Cancel a booked ticket
    """
    try:
        start_time = datetime.now()
        
        # Get ticket
        ticket = db.query(Ticket).filter(
            Ticket.id == ticket_id,
            Ticket.user_id == user_id
        ).first()
        
        if not ticket:
            raise HTTPException(
                status_code=404,
                detail="Ticket not found or unauthorized"
            )
            
        # Check if concert is within cancellation window
        concert = db.query(Concert).filter(Concert.id == ticket.concert_id).first()
        if concert.date - datetime.now() < timedelta(hours=24):
            raise HTTPException(
                status_code=400,
                detail="Cannot cancel tickets less than 24 hours before concert"
            )
            
        # Update ticket status
        ticket.status = "CANCELLED"
        db.commit()
        
        # Clear availability cache
        clear_availability_cache(concert.id)
        
        # Update monitoring
        service_monitor.record_request(
            duration=(datetime.now() - start_time).total_seconds(),
            success=True
        )
        
        logging.info(f"Successfully cancelled ticket {ticket_id}")
        return {"message": "Ticket cancelled successfully"}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        logging.error(f"Error cancelling ticket: {str(e)}")
        service_monitor.record_request(
            duration=(datetime.now() - start_time).total_seconds(),
            success=False
        )
        raise HTTPException(status_code=500, detail="Error cancelling ticket")
    finally:
        db.close()

def get_available_tickets(db: Session, concert_id: int, seat_type: str) -> int:
    """Calculate available tickets for a concert and seat type"""
    cache_key = f"concert_{concert_id}_{seat_type}"
    
    # Check cache
    if cache_key in availability_cache:
        cache_time, count = availability_cache[cache_key]
        if datetime.now() - cache_time < CACHE_DURATION:
            return count
            
    # Query database
    total_tickets = db.query(Concert).filter(
        Concert.id == concert_id
    ).first().capacity
    
    booked_tickets = db.query(Ticket).filter(
        and_(
            Ticket.concert_id == concert_id,
            Ticket.seat_type == seat_type,
            Ticket.status.in_(["RESERVED", "CONFIRMED"])
        )
    ).count()
    
    available = total_tickets - booked_tickets
    
    # Update cache
    availability_cache[cache_key] = (datetime.now(), available)
    
    return available

def get_ticket_price(concert: Concert, seat_type: str) -> float:
    """Calculate ticket price based on seat type"""
    base_price = concert.min_price
    multipliers = {
        "GENERAL": 1.0,
        "VIP": 2.5,
        "BACKSTAGE": 4.0
    }
    return base_price * multipliers.get(seat_type, 1.0)

def clear_availability_cache(concert_id: int):
    """Clear cache entries for a specific concert"""
    keys_to_remove = [
        key for key in availability_cache.keys()
        if key.startswith(f"concert_{concert_id}")
    ]
    for key in keys_to_remove:
        availability_cache.pop(key, None)