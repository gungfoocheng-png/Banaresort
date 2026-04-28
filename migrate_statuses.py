import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    print("Error: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing from .env")
    exit(1)

supabase: Client = create_client(url, key)

def migrate_statuses():
    print("--- Migrating Room Statuses ---")
    
    # Mapping
    mapping = {
        "available": "I",
        "reserved": "R",
        "occupied": "O",
        "maintenance": "O"
    }

    try:
        # Get all rooms
        response = supabase.table("rooms").select("id, status").execute()
        rooms = response.data
        
        for room in rooms:
            old_status = room['status']
            if old_status in mapping:
                new_status = mapping[old_status]
                print(f"Updating room {room['id']}: {old_status} -> {new_status}")
                supabase.table("rooms").update({"status": new_status}).eq("id", room['id']).execute()
            else:
                print(f"Room {room['id']} already has status {old_status} (or unknown).")
                
    except Exception as e:
        print(f"Migration error: {e}")

    print("--- Migration Complete ---")

if __name__ == "__main__":
    migrate_statuses()
