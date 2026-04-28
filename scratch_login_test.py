import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(url, key)
admin_supabase: Client = create_client(url, key)

try:
    print("Logging in...")
    res = supabase.auth.sign_in_with_password({"email": "supakirtkaewsuphan123@gmail.com", "password": "AdminPassword123!"})
    print("Login success! User ID:", res.user.id)
    
    print("Fetching profile...")
    profile_resp = admin_supabase.table("profiles").select("role").eq("id", res.user.id).execute()
    print("Profile resp:", profile_resp.data)
    
    if profile_resp.data and len(profile_resp.data) > 0:
        role = profile_resp.data[0]['role']
        print(f"Extracted Role: {role}")
    else:
        print("No profile data found")
        
except Exception as e:
    print(f"Error: {e}")
