from apscheduler.schedulers.background import BackgroundScheduler
from database import supabase, update_room_status, update_booking_status
from datetime import datetime, timezone
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_expired_bookings():
    """
    Check for bookings that are 'pending' and have passed their 'expires_at' time.
    """
    now = datetime.now(timezone.utc)
    logger.info(f"Running expiry check at {now}")
    
    try:
        # Find pending bookings that are expired
        response = supabase.table("bookings")\
            .select("id, room_id")\
            .eq("status", "pending")\
            .lt("expires_at", now.isoformat())\
            .execute()
        
        expired_candidates = response.data
        
        if not expired_candidates:
            logger.info("No expired bookings found.")
            return

        # NEW: Check if these bookings have payments uploaded
        # Fetch all payment booking_ids
        payments_resp = supabase.table("payments").select("booking_id").execute()
        paid_booking_ids = {p['booking_id'] for p in (payments_resp.data or [])}

        for booking in expired_candidates:
            booking_id = booking['id']
            room_id = booking['room_id']
            
            # If they uploaded a slip, do NOT expire
            if booking_id in paid_booking_ids:
                logger.info(f"Booking {booking_id} has payment uploaded, skipping expiry.")
                continue
                
            logger.info(f"Expiring booking {booking_id} for room {room_id}")
            
            # Update booking status to expired
            update_booking_status(booking_id, "expired")
            
            # Revert room status to available
            # Note: We should check if there are no OTHER active bookings for this room, 
            # but for this simple version, we assume room status is directly tied.
            update_room_status(room_id, "I")
            
    except Exception as e:
        logger.error(f"Error checking expired bookings: {str(e)}")

def check_completed_bookings():
    """
    Check for bookings that have reached their checkout date.
    If today is checkout day or later, and it's after 9:00 AM, 
    we revert the room status to 'I'.
    """
    now = datetime.now()
    if now.hour < 9:
        return
        
    today_str = now.strftime('%Y-%m-%d')
    logger.info(f"Running checkout status cleanup at {now}")
    
    try:
        # Find bookings where checkout_date <= today and they were 'paid' or 'reserved'
        res = supabase.table("bookings")\
            .select("id, room_id")\
            .in_("status", ["paid"])\
            .lte("checkout_date", today_str)\
            .execute()
            
        for b in (res.data or []):
            # Revert room status to 'I' (ว่าง)
            update_room_status(b['room_id'], "I")
            # Mark booking as completed
            update_booking_status(b['id'], "completed")
            logger.info(f"Booking {b['id']} completed, room {b['room_id']} set to available.")
            
    except Exception as e:
        logger.error(f"Error cleaning up completed bookings: {e}")

def start_scheduler():
    scheduler = BackgroundScheduler()
    # Check every minute for expired payments
    scheduler.add_job(check_expired_bookings, 'interval', minutes=1)
    # Check every 15 minutes for completed stays (after 9:00 AM on checkout day)
    scheduler.add_job(check_completed_bookings, 'interval', minutes=15)
    scheduler.start()
    logger.info("Background scheduler started (1-minute interval).")
    return scheduler
