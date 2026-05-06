import json
from database import supabase
data = supabase.table('rooms').select('*').limit(1).execute().data
with open('scratch_rooms.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
