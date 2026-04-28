import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(url, key)

try:
    res = supabase.table("profiles").select("role").eq("id", "ef7238ec-f51c-4914-a98f-897bc95cf2c0").execute()
    print("Normal select:", res.data)
except Exception as e:
    print("Normal select error:", e)

try:
    res = supabase.table("profiles").select("role").eq("id", "ef7238ec-f51c-4914-a98f-897bc95cf2c0").maybe_single().execute()
    print("Maybe single:", res.data)
except Exception as e:
    print("Maybe single error:", type(e), e)
