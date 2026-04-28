import sys
import io
from database import admin_supabase

# Force UTF-8 for stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_rooms():
    res = admin_supabase.table("rooms").select("id, room_number, name, status").execute()
    for room in res.data:
        # Safe print for debugging
        print(f"Room {room['id']} (#{room['room_number']}): {room['status']}")

if __name__ == "__main__":
    check_rooms()
