import os
from dotenv import load_dotenv
from supabase import create_client
import json

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

import sys
import io

# Force UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def inspect():
    # 1. Find room "A101"
    rooms = supabase.table("rooms").select("*").eq("room_number", "A101").execute()
    print("--- Rooms matching 'A101' ---")
    print(json.dumps(rooms.data, indent=2, ensure_ascii=False))
    
    if not rooms.data:
        return
        
    room_id = rooms.data[0]['id']
    
    # 2. Find bookings for this room today
    from datetime import datetime
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"\n--- Bookings for Room ID {room_id} around {today} ---")
    
    bookings = supabase.table("bookings")\
        .select("*")\
        .eq("room_id", room_id)\
        .order("created_at", desc=True)\
        .execute()
        
    print(json.dumps(bookings.data, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    inspect()
