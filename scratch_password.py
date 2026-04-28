import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(url, key)

try:
    user_id = 'ef7238ec-f51c-4914-a98f-897bc95cf2c0'
    res = supabase.auth.admin.update_user_by_id(user_id, {"password": "AdminPassword123!"})
    print("Password updated successfully!")
except Exception as e:
    print(f"Error updating password: {e}")
