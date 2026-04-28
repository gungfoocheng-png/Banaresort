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

REQUIRED_BUCKETS = ["room_images", "slips"]

def init_storage():
    print("--- Initializing Supabase Storage Buckets ---")
    
    # Get existing buckets
    try:
        existing_buckets = supabase.storage.list_buckets()
        existing_names = [b.name for b in existing_buckets]
        print(f"Existing buckets: {existing_names}")
    except Exception as e:
        print(f"Error listing buckets: {e}")
        existing_names = []

    for bucket_name in REQUIRED_BUCKETS:
        if bucket_name not in existing_names:
            print(f"Creating bucket: {bucket_name}...")
            try:
                # Create public bucket
                res = supabase.storage.create_bucket(bucket_name, options={"public": True})
                print(f"Successfully created bucket: {bucket_name}")
            except Exception as e:
                # Catch case where it might already exist but list_buckets missed it
                if "already exists" in str(e).lower():
                    print(f"Bucket {bucket_name} already exists.")
                else:
                    print(f"Failed to create bucket {bucket_name}: {e}")
        else:
            print(f"Bucket {bucket_name} already exists.")

    print("--- Storage Initialization Complete ---")

if __name__ == "__main__":
    init_storage()
