import os
import logging
from dotenv import load_dotenv
from supabase import create_client, Client

logging.basicConfig(level=logging.DEBUG)

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(url, key)

print("--- Normal Select ---")
res = supabase.table("profiles").select("role").eq("id", "ef7238ec-f51c-4914-a98f-897bc95cf2c0").execute()
print(res.data)

print("--- Maybe Single ---")
res = supabase.table("profiles").select("role").eq("id", "ef7238ec-f51c-4914-a98f-897bc95cf2c0").maybe_single().execute()
print(res.data)
