import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url: str = os.getenv("SUPABASE_URL")
anon_key: str = os.getenv("SUPABASE_KEY")
service_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not url or not anon_key or not service_key:
    print("Warning: SUPABASE_URL, SUPABASE_KEY, or SUPABASE_SERVICE_ROLE_KEY not found in environment.")

# Both clients use the service role key for now as the provided anon key is invalid for this library
supabase: Client = create_client(url, service_key)

# Admin client with Service Role (Bypasses RLS)
admin_supabase: Client = create_client(url, service_key)

def get_rooms():
    return admin_supabase.table("rooms").select("*, resort_types(*)").neq("status", "F").order("id").execute()

def get_rooms_admin():
    return admin_supabase.table("rooms").select("*").neq("status", "F").order("created_at", desc=True).execute()

def get_room_by_id(room_id):
    return admin_supabase.table("rooms").select("*").eq("id", room_id).execute()

def update_room_status(room_id, status):
    return admin_supabase.table("rooms").update({"status": status}).eq("id", room_id).execute()

def add_room(room_data):
    return admin_supabase.table("rooms").insert(room_data).execute()

def update_room(room_id, room_data):
    return admin_supabase.table("rooms").update(room_data).eq("id", room_id).execute()

def delete_room(room_id):
    return admin_supabase.table("rooms").delete().eq("id", room_id).execute()

def create_booking(booking_data):
    return admin_supabase.table("bookings").insert(booking_data).execute()

def get_bookings():
    return admin_supabase.table("bookings").select("*, rooms(*)").order("created_at", desc=True).execute()

def get_pending_bookings():
    return admin_supabase.table("bookings").select("*").eq("status", "pending").execute()

def update_booking_status(booking_id, status):
    return admin_supabase.table("bookings").update({"status": status}).eq("id", booking_id).execute()

def create_payment(payment_data):
    return admin_supabase.table("payments").insert(payment_data).execute()

def get_expenses():
    return admin_supabase.table("expenses").select("*").order("created_at", desc=True).execute()

def add_expense(expense_data):
    return admin_supabase.table("expenses").insert(expense_data).execute()

# --- Resort Settings ---
def get_resort_settings():
    try:
        res = admin_supabase.table("resort_settings").select("*").eq("id", 1).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
    except Exception as e:
        print(f"Error fetching resort settings: {e}")
    
    # Default values if no record or table
    return {
        "name": "บ้านนารีสอร์ท&บ้านสวนแก้วสุพรรณ",
        "phone": "081-234-5678",
        "address": "ตำบล บ้านนาถาวร อำเภอ ประทุมราชวงศา",
        "promptpay_id": os.getenv("PROMPTPAY_ID", "0812345678")
    }

def update_resort_settings(data):
    # UPSERT pattern (id=1)
    data["id"] = 1
    return admin_supabase.table("resort_settings").upsert(data).execute()

def delete_booking(booking_id):
    return admin_supabase.table("bookings").delete().eq("id", booking_id).execute()

def delete_expense(expense_id):
    return admin_supabase.table("expenses").delete().eq("id", expense_id).execute()

def get_auth_client():
    """Returns a fresh Supabase client for authentication to avoid polluting shared client state."""
    return create_client(url, service_key)

# --- Attractions & Activities ---
def get_attractions(only_active=False):
    query = admin_supabase.table("attractions").select("*")
    if only_active:
        query = query.eq("is_active", True)
    return query.order("created_at", desc=True).execute()

def add_attraction(data):
    return admin_supabase.table("attractions").insert(data).execute()

def update_attraction(id, data):
    return admin_supabase.table("attractions").update(data).eq("id", id).execute()

def delete_attraction(id):
    return admin_supabase.table("attractions").delete().eq("id", id).execute()
