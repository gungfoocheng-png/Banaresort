import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(url, key)
admin_supabase: Client = create_client(url, key)

print("Before login:")
res1 = admin_supabase.table("profiles").select("role").eq("id", "ef7238ec-f51c-4914-a98f-897bc95cf2c0").execute()
print(res1.data)

print("Logging in...")
res = supabase.auth.sign_in_with_password({"email": "supakirtkaewsuphan123@gmail.com", "password": "AdminPassword123!"})

print("After login:")
res2 = admin_supabase.table("profiles").select("role").eq("id", "ef7238ec-f51c-4914-a98f-897bc95cf2c0").execute()
print(res2.data)
