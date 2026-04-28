import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(url, key)

try:
    users = supabase.auth.admin.list_users()
    for u in users:
        print(u.email, u.id)
except Exception as e:
    print(e)
