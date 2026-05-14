import json
import os
from PIL import Image, ImageDraw
from database import admin_supabase

def main():
    with open('data/map_coords.json') as f:
        coords = json.load(f)

    img = Image.open('static/images/resort_map_bg.png')
    w, h = img.size
    os.makedirs('static/images/maps', exist_ok=True)

    for room_id, data in coords.items():
        label = data['label']
        x_pct = data['x']
        y_pct = data['y']
        
        px = int((x_pct / 100.0) * w)
        py = int((y_pct / 100.0) * h)
        
        # Create a copy to draw on
        room_img = img.copy()
        draw = ImageDraw.Draw(room_img)
        
        # Draw a red circle around the location
        r = 25
        draw.ellipse((px - r, py - r, px + r, py + r), outline='#ef4444', width=6)
        
        # Crop a 400x400 area around the point
        crop_size = 400
        left = max(0, px - crop_size//2)
        top = max(0, py - crop_size//2)
        right = min(w, px + crop_size//2)
        bottom = min(h, py + crop_size//2)
        
        # Adjust if hitting edges
        if left == 0: right = min(w, crop_size)
        if right == w: left = max(0, w - crop_size)
        if top == 0: bottom = min(h, crop_size)
        if bottom == h: top = max(0, h - crop_size)
        
        cropped = room_img.crop((left, top, right, bottom))
        filepath = f'static/images/maps/room_{label}.png'
        cropped.save(filepath)
        print(f'Saved {filepath}')
        
        # Now update the database
        # Find the room by room_number = label
        try:
            resp = admin_supabase.table('rooms').select('id, images').eq('room_number', label).execute()
            if resp.data:
                for room in resp.data:
                    current_images = room.get('images') or []
                    new_img_url = f'/static/images/maps/room_{label}.png'
                    
                    # Ensure we don't duplicate
                    if new_img_url not in current_images:
                        current_images.append(new_img_url)
                        admin_supabase.table('rooms').update({'images': current_images}).eq('id', room['id']).execute()
                        print(f'Updated database for room {label}')
        except Exception as e:
            print(f"Error updating DB for room {label}: {e}")

if __name__ == '__main__':
    main()
