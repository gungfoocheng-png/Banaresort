from database import supabase
rooms = supabase.table('rooms').select('id, name, map_coords').execute()
for r in rooms.data:
    print(r)
