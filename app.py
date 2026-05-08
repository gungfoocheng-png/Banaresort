from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from database import supabase, admin_supabase, get_rooms, get_room_by_id, get_rooms_admin, update_room_status, create_booking, update_booking_status, create_payment, get_bookings, get_expenses, add_expense, get_resort_settings, update_resort_settings, add_room, update_room, delete_room, delete_booking, delete_expense, get_auth_client, get_attractions, add_attraction, update_attraction, delete_attraction
from scheduler import start_scheduler
from utils.promptpay import generate_promptpay_qr
from utils.pdf_gen import generate_receipt_pdf
from datetime import datetime, timedelta, timezone
import os
import io
import uuid
import os
import io
import uuid
import json
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "bannaresort_secret_key")

# Start background scheduler
scheduler = start_scheduler()

# --- Helpers ---
def is_admin():
    role = session.get('role')
    print(f"DEBUG is_admin: user_id={session.get('user_id')}, role={role}")
    return role in ['admin', 'super_admin']

def is_super_admin():
    return session.get('role') == 'super_admin'

def upload_to_supabase(file, bucket, folder=""):
    try:
        ext = file.filename.split('.')[-1]
        filename = f"{uuid.uuid4()}.{ext}"
        path = f"{folder}/{filename}" if folder else filename
        
        file_bytes = file.read()
        admin_supabase.storage.from_(bucket).upload(
            path, 
            file_bytes, 
            {"content-type": file.content_type}
        )
        
        # Get public URL
        url_res = admin_supabase.storage.from_(bucket).get_public_url(path)
        return url_res
    except Exception as e:
        print(f"Upload Error: {e}")
        return None

@app.template_filter('format')
def number_format(value):
    try:
        if value is None: return "0.00"
        return "{:,.2f}".format(float(value))
    except (ValueError, TypeError):
        return value

@app.context_processor
def inject_resort_info():
    return dict(resort=get_resort_settings())

@app.before_request
def refresh_session_role():
    # Use direct httpx call to avoid supabase client auth state pollution
    if session.get('user_id') and not request.path.startswith('/static') and not request.path.startswith('/api'):
        try:
            import httpx
            _supabase_url = os.getenv('SUPABASE_URL')
            _service_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
            resp = httpx.get(
                f"{_supabase_url}/rest/v1/profiles",
                params={"id": f"eq.{session['user_id']}", "select": "role,full_name,display_name,phone"},
                headers={"Authorization": f"Bearer {_service_key}", "apikey": _service_key},
                timeout=5.0
            )
            data = resp.json()
            if data and isinstance(data, list) and len(data) > 0:
                prof = data[0]
                session['role'] = prof.get('role', 'customer')
                session['full_name'] = prof.get('display_name') or prof.get('full_name') or 'Guest'
                session['phone'] = prof.get('phone') or ''
                print(f"DEBUG before_request: role={session['role']} for user={session.get('email')}")
        except Exception as e:
            print(f"Role refresh error for {session.get('email')}: {e}")

@app.route('/debug_session')
def debug_session():
    return jsonify({
        "user_id": session.get('user_id'),
        "email": session.get('email'),
        "role": session.get('role'),
        "full_name": session.get('full_name')
    })

# --- Authentication Routes ---

def get_current_status_rooms():
    try:
        now = datetime.now(timezone(timedelta(hours=7)))
        today = now.strftime('%Y-%m-%d')
        tomorrow = (now + timedelta(days=1)).strftime('%Y-%m-%d')
        
        rooms_res = get_rooms()
        rooms = rooms_res.data if (rooms_res and rooms_res.data) else []
        
        current_hour = now.hour
        query = admin_supabase.table("bookings")\
            .select("room_id, status")\
            .in_("status", ["pending", "paid", "reserved"])\
            .lt("checkin_date", tomorrow)
            
        if current_hour < 9:
            query = query.gte("checkout_date", today)
        else:
            query = query.gt("checkout_date", today)
            
        bookings_query = query.execute()
        
        unavailable_status = {}
        for b in (bookings_query.data or []):
            rid = b['room_id']
            status = b['status']
            if status == 'paid':
                unavailable_status[rid] = 'O'
            elif status in ['pending', 'reserved']:
                if unavailable_status.get(rid) != 'O':
                    unavailable_status[rid] = 'R'
                
        for room in rooms:
            rid = room['id']
            if room.get('status') == 'maintenance':
                continue
            if rid in unavailable_status:
                room['status'] = unavailable_status[rid]
            else:
                room['status'] = 'I'
        return rooms
    except Exception as e:
        print(f"Error in get_current_status_rooms: {e}")
        fallback = get_rooms()
        return fallback.data if fallback else []

@app.route('/')
def index():
    all_rooms = get_current_status_rooms()
    
    # Implement pagination for initial render
    page_rooms = []
    type_counts = {}
    for r in all_rooms:
        if len(page_rooms) >= 15:
            break
        
        res_type = r.get('resort_types')
        t_name = res_type.get('name', 'บ้านพักอื่นๆ') if isinstance(res_type, dict) else 'บ้านพักอื่นๆ'
            
        count = type_counts.get(t_name, 0)
        if count < 5:
            page_rooms.append(r)
            type_counts[t_name] = count + 1

    attr_res = get_attractions(only_active=True)
    attractions = attr_res.data if attr_res.data else []

    return render_template('index.html', rooms=page_rooms, attractions=attractions)

@app.route('/map')
def resort_map():
    return render_template('map.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.args.get('msg') == 'book':
        flash("กรุณาลงทะเบียนสมัครสมาชิกก่อน", "info")
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            print(f"Login Attempt: {email}") # Debug log
            auth_client = get_auth_client()
            res = auth_client.auth.sign_in_with_password({"email": email, "password": password})
            session['user_id'] = res.user.id
            session['email'] = res.user.email
            
            # Fetch profile for role using direct HTTP to avoid auth state pollution
            try:
                import httpx as _httpx
                _supa_url = os.getenv('SUPABASE_URL')
                _svc_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
                _resp = _httpx.get(
                    f"{_supa_url}/rest/v1/profiles",
                    params={"id": f"eq.{res.user.id}", "select": "role,full_name,display_name,phone"},
                    headers={"Authorization": f"Bearer {_svc_key}", "apikey": _svc_key},
                    timeout=5.0
                )
                _pdata = _resp.json()
                
                if _pdata and isinstance(_pdata, list) and len(_pdata) > 0:
                    prof = _pdata[0]
                    session['role'] = prof.get('role', 'customer')
                    session['full_name'] = prof.get('display_name') or prof.get('full_name') or 'Guest'
                    session['phone'] = prof.get('phone') or ''
                    print(f"Login Success: {email}, Role: {session['role']}")
                else:
                    # Self-healing: create profile if missing
                    print(f"Profile not found for {email}, creating customer profile.")
                    admin_supabase.table("profiles").insert({
                        "id": res.user.id,
                        "email": res.user.email,
                        "role": "customer",
                        "full_name": "New Guest"
                    }).execute()
                    session['role'] = 'customer'
            except Exception as profile_err:
                print(f"Profile lookup error for {email}: {type(profile_err).__name__}")
                session['role'] = 'customer' # Fallback
            
            flash("เข้าสู่ระบบสำเร็จ", "success")
            return redirect(url_for('index'))
        except Exception as e:
            print(f"Login Error for {email}: {str(e)}")
            flash("เข้าสู่ระบบล้มเหลว กรุณาลงทะเบียน", "error")
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('guest_name', 'Guest')
        phone = request.form.get('phone')
        
        try:
            # Bypass rate limit and email confirmation using Admin API
            # User will be confirmed automatically
            auth_client = get_auth_client()
            res = auth_client.auth.admin.create_user({
                "email": email, 
                "password": password,
                "user_metadata": {"full_name": full_name, "phone": phone},
                "email_confirm": True
            })
            user_id = res.user.id
            
            # Create profile
            profile_data = {
                "id": user_id,
                "email": email,
                "full_name": full_name,
                "role": "customer",
                "phone": phone
            }
            admin_supabase.table("profiles").insert(profile_data).execute()
            
            flash("ลงทะเบียนสำเร็จ กรุณาเข้าสู่ระบบ", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"ลงทะเบียนล้มเหลว: {str(e)}", "error")
            
    return render_template('register.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        try:
            # Use Supabase to send reset email
            reset_url = url_for('reset_password', _external=True)
            auth_client = get_auth_client()
            auth_client.auth.reset_password_for_email(email, {"redirect_to": reset_url})
            flash("ส่งลิงก์รีเซ็ตรหัสผ่านไปยังอีเมลของคุณแล้ว กรุณาตรวจสอบกล่องจดหมาย", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"เกิดข้อผิดพลาด: {str(e)}", "error")
            
    return render_template('forgot_password.html')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        access_token = request.form.get('access_token')
        refresh_token = request.form.get('refresh_token')
        
        if not access_token:
            flash("ข้อมูลยืนยันตัวตนไม่ถูกต้อง", "error")
            return redirect(url_for('login'))
            
        try:
            # Establish session using the recovery tokens
            auth_client = get_auth_client()
            auth_client.auth.set_session(access_token, refresh_token)
            # Update the user's password
            auth_client.auth.update_user({"password": new_password})
            
            # Sign out the specific auth client session
            auth_client.auth.sign_out()
            session.clear()
            
            flash("รีเซ็ตรหัสผ่านสำเร็จ คุณสามารถเข้าสู่ระบบด้วยรหัสผ่านใหม่ได้ทันที", "success")
            return redirect(url_for('login'))
        except Exception as e:
            print(f"Reset password error: {str(e)}")
            flash("เกิดข้อผิดพลาด หรือลิงก์รีเซ็ตรหัสผ่านหมดอายุแล้ว", "error")
            return redirect(url_for('login'))
            
    return render_template('reset_password.html')

@app.route('/logout')
def logout():
    # Only clear Flask session. Do not call sign_out() on shared admin client
    # to avoid pulling the "Service Role" key out.
    session.clear()
    flash("ออกจากระบบเรียบร้อยแล้ว", "info")
    return redirect(url_for('index'))

@app.route('/bookings')
def view_bookings():
    if not session.get('user_id'):
        flash("กรุณาเข้าสู่ระบบเพื่อดูประวัติการจองของคุณ", "info")
        return redirect(url_for('login'))
        
    phone = request.args.get('phone')
    user_id = session['user_id']
    bookings = []
    
    # Always fetch user's profile to get their official phone number
    profile_resp = admin_supabase.table("profiles").select("phone").eq("id", user_id).execute()
    user_phone = profile_resp.data[0].get('phone') if (profile_resp.data and isinstance(profile_resp.data, list) and len(profile_resp.data) > 0) else None
    
    if phone:
        # Clean search input
        clean_search = ''.join(filter(str.isdigit, phone))
        
        # Security Check: Only allow search if it matches their own phone number
        if clean_search == user_phone:
            res = admin_supabase.table("bookings").select("*, rooms(*)").eq("guest_phone", clean_search).order("created_at", desc=True).execute()
            bookings = res.data
        else:
            flash("คุณสามารถค้นหาได้เฉพาะข้อมูลของตัวเองเท่านั้น", "error")
            # Default back to showing their bookings by user_id
            res = admin_supabase.table("bookings").select("*, rooms(*)").eq("user_id", user_id).order("created_at", desc=True).execute()
            bookings = res.data
    else:
        # Default: fetch by user_id (most reliable for logged in users)
        res = admin_supabase.table("bookings").select("*, rooms(*)").eq("user_id", user_id).order("created_at", desc=True).execute()
        bookings = res.data
        
    return render_template('bookings.html', bookings=bookings, searched_phone=phone)

@app.route('/api/rooms')
def api_rooms():
    rooms = get_current_status_rooms()
    
    # Load map coords
    map_coords = {}
    try:
        if os.path.exists('data/map_coords.json'):
            with open('data/map_coords.json', 'r', encoding='utf-8') as f:
                map_coords = json.load(f)
    except Exception as e:
        print(f"Error loading map_coords: {e}")
        
    for room in rooms:
        room_id_str = str(room['id'])
        if room_id_str in map_coords:
            room['map_coords'] = map_coords[room_id_str]
            
    return jsonify(rooms)

@app.route('/api/check_availability', methods=['POST'])
def api_check_availability():
    data = request.json
    checkin = data.get('checkin')
    checkout = data.get('checkout')
    
    if not checkin or not checkout:
        return jsonify({"error": "Missing dates"}), 400
        
    try:
        # Overlap logic with 9:00 AM rule
        now = datetime.now(timezone(timedelta(hours=7)))
        current_hour = now.hour
        
        query = admin_supabase.table("bookings")\
            .select("room_id, status")\
            .in_("status", ["pending", "paid"])\
            .lt("checkin_date", checkout)
            
        # If the requested check-in is today, we check time
        if checkin == now.strftime('%Y-%m-%d') and current_hour < 9:
            # If checking in today before 9 AM, we are stricter about overlaps
            query = query.gte("checkout_date", checkin)
        else:
            query = query.gt("checkout_date", checkin)
            
        res = query.execute()
        
        unavailable_status = {}
        for b in (res.data or []):
            rid = b['room_id']
            status = b['status']
            if status == 'paid':
                unavailable_status[rid] = 'O'
            elif status in ['pending', 'reserved']:
                if unavailable_status.get(rid) != 'O':
                    unavailable_status[rid] = 'R'
                
        return jsonify({
            "unavailable_ids": list(unavailable_status.keys()),
            "unavailable_status": unavailable_status
        })
    except Exception as e:
        print(f"Availability check error: {e}")
        return jsonify({"unavailable_ids": [], "error": str(e)}), 500

@app.route('/book', methods=['POST'])
def book_room():
    if not session.get('user_id'):
        flash("กรุณาเข้าสู่ระบบเพื่อทำการจองห้องพัก", "info")
        return redirect(url_for('login'))
        
    room_id = request.form.get('room_id')
    guest_name = request.form.get('guest_name')
    guest_phone = request.form.get('guest_phone')
    guest_email = request.form.get('guest_email')
    checkin_date = request.form.get('checkin_date')
    checkout_date = request.form.get('checkout_date')
    
    # Calculate price
    try:
        room_id_int = int(room_id)
    except:
        room_id_int = room_id
        
    room_resp = get_room_by_id(room_id_int)
    if not room_resp.data or not isinstance(room_resp.data, list) or len(room_resp.data) == 0:
        flash("ไม่พบข้อมูลห้องพัก", "error")
        return redirect(url_for('index'))
    
    room = room_resp.data[0]
    price_per_night = float(room['price'])
    
    # Calculate days
    d1 = datetime.strptime(checkin_date, "%Y-%m-%d")
    d2 = datetime.strptime(checkout_date, "%Y-%m-%d")
    num_days = (d2 - d1).days
    if num_days <= 0:
        flash("วันที่เช็คเอาท์ต้องอยู่หลังจากวันเช็คอิน", "error")
        return redirect(url_for('index'))
    
    total_price = price_per_night * num_days
    
    # Expiry time (2 minutes from now for testing)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=2)
    
    booking_data = {
        "room_id": room_id_int,
        "user_id": session.get('user_id'), # Link to user profile if logged in
        "guest_name": guest_name,
        "guest_phone": guest_phone,
        "guest_email": guest_email,
        "checkin_date": checkin_date,
        "checkout_date": checkout_date,
        "total_price": total_price,
        "status": "pending",
        "expires_at": expires_at.isoformat()
    }
    
    # Save booking
    res = create_booking(booking_data)
    if not res.data or not isinstance(res.data, list) or len(res.data) == 0:
        flash("ไม่สามารถสร้างการจองได้", "error")
        return redirect(url_for('index'))
    
    booking_id = res.data[0]['id']
    
    # Update room status to reserved temporarily
    update_room_status(room_id, "R")
    
    return redirect(url_for('payment', booking_id=booking_id))

@app.route('/payment/<booking_id>')
def payment(booking_id):
    booking_resp = admin_supabase.table("bookings").select("*, rooms(name)").eq("id", booking_id).execute()
    if not booking_resp.data or not isinstance(booking_resp.data, list) or len(booking_resp.data) == 0:
        flash("ไม่พบข้อมูลการจอง", "error")
        return redirect(url_for('index'))
    
    booking = booking_resp.data[0]
    booking['room_name'] = booking['rooms']['name']
    
    if booking['status'] != 'pending':
        flash("การจองนี้ได้รับการจัดการแล้ว", "info")
        return redirect(url_for('index'))

    # Fetch PromptPay ID from dynamic settings
    settings = get_resort_settings()
    pp_id = settings.get('promptpay_id', os.getenv("PROMPTPAY_ID", "0812345678"))
    
    qr_code = generate_promptpay_qr(booking['total_price'], pp_id=pp_id)
    
    return render_template('payment.html', booking=booking, qr_code=qr_code)

@app.route('/upload_slip/<booking_id>', methods=['POST'])
def upload_slip(booking_id):
    file = request.files.get('slip')
    if not file:
        flash("กรุณาเลือกไฟล์สลิป", "error")
        return redirect(url_for('payment', booking_id=booking_id))
    
    # Get booking amount
    try:
        booking_resp = admin_supabase.table("bookings").select("total_price").eq("id", booking_id).execute()
        amount = 0
        if booking_resp.data and isinstance(booking_resp.data, list) and len(booking_resp.data) > 0:
            amount = float(booking_resp.data[0]['total_price'])
    except Exception as e:
        print(f"Error getting booking amount: {e}")
        amount = 0
        
    try:
        ext = file.filename.split('.')[-1].lower() if '.' in file.filename else 'jpg'
        import uuid
        filename = f"slip_{booking_id}_{uuid.uuid4().hex[:8]}.{ext}"
        file_data = file.read()
        
        mime_type = f"image/{ext}"
        if ext in ['jpg', 'jpeg']: mime_type = "image/jpeg"
        elif ext == 'png': mime_type = "image/png"
        
        # Use a fresh client to ensure service_role is used without any session interference
        from supabase import create_client as fresh_create_client
        fresh_admin = fresh_create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
        
        # Use direct REST API to ensure service_role is correctly applied without library interference
        import requests
        supabase_url = os.getenv("SUPABASE_URL")
        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        upload_url = f"{supabase_url}/storage/v1/object/slips/{filename}"
        headers = {
            "Authorization": f"Bearer {service_key}",
            "apiKey": service_key,
            "Content-Type": mime_type
        }
        
        print(f"Direct upload to: {upload_url}")
        response = requests.post(upload_url, headers=headers, data=file_data)
        
        if response.status_code == 200:
            slip_url = f"{supabase_url}/storage/v1/object/public/slips/{filename}"
            print(f"Direct upload success: {slip_url}")
        else:
            raise Exception(f"Upload failed with status {response.status_code}: {response.text}")
            
    except Exception as e:
        error_msg = str(e)
        print(f"Slip upload error: {error_msg}")
        with open("upload_error.log", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now(timezone(timedelta(hours=7)))}: {error_msg}\n")
        # Fallback if upload fails
        slip_url = "https://placehold.co/600x800?text=Upload+Error+" + error_msg[:20]
    
    # Create payment record
    payment_data = {
        "booking_id": booking_id,
        "amount": amount,
        "slip_url": slip_url,
        "status": "pending"
    }
    
    create_payment(payment_data)
    # Note: Status remains 'pending' but having a payment record will prevent expiry
    
    flash("ส่งสลิปเรียบร้อยแล้ว กรุณารอการตรวจสอบจาก Admin", "success")
    return redirect(url_for('index'))

# --- Admin Routes ---

@app.route('/admin')
def admin_dashboard():
    # Auto-refresh session role from DB to avoid stale sessions
    if session.get('user_id'):
        profile = admin_supabase.table("profiles").select("role").eq("id", session['user_id']).execute()
        if profile.data and isinstance(profile.data, list) and len(profile.data) > 0:
            session['role'] = profile.data[0]['role']

    # Redirect if not admin
    if not is_admin():
        flash("เฉพาะเจ้าหน้าที่เท่านั้นที่เข้าถึงส่วนนี้ได้", "error")
        return redirect(url_for('login'))
    
    # Stats
    bookings_resp = admin_supabase.table("bookings").select("*, rooms(*)").order("created_at", desc=True).execute()
    bookings = bookings_resp.data
    
    expenses_resp = admin_supabase.table("expenses").select("*").order("created_at", desc=True).execute()
    expenses = expenses_resp.data
    
    total_income = sum(float(b['total_price']) for b in bookings if b['status'] == 'paid')
    total_expense = sum(float(e['amount']) for e in expenses)
    profit = total_income - total_expense
    
    # Recent payments needing verification
    payments_resp = admin_supabase.table("payments").select("*, bookings(guest_name, total_price)").eq("status", "pending").execute()
    pending_payments = payments_resp.data

    return render_template('admin/dashboard.html', 
                           total_income=total_income, 
                           total_expense=total_expense, 
                           profit=profit,
                           pending_payments=pending_payments,
                           bookings=bookings,
                           expenses=expenses)

@app.route('/admin/map')
def admin_map_editor():
    if not is_admin(): return redirect(url_for('login'))
    return render_template('admin/map_editor.html')

@app.route('/api/admin/save_map_coords', methods=['POST'])
def save_map_coords():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 403
    
    coords_data = request.json
    try:
        os.makedirs('data', exist_ok=True)
        with open('data/map_coords.json', 'w', encoding='utf-8') as f:
            json.dump(coords_data, f, ensure_ascii=False, indent=2)
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error saving map_coords: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/admin/walkin', methods=['GET', 'POST'])
def admin_walkin():
    if not is_admin(): return redirect(url_for('login'))
    
    available_rooms = None
    checkin_date = request.args.get('checkin_date')
    checkout_date = request.args.get('checkout_date')
    
    if request.method == 'POST':
        print(f"DEBUG admin_walkin POST form: {request.form}")
        room_id = request.form.get('room_id')
        guest_name = request.form.get('guest_name')
        guest_phone = request.form.get('guest_phone')
        guest_email = request.form.get('guest_email', 'walkin@bannaresort.com')
        checkin_date = request.form.get('checkin_date')
        checkout_date = request.form.get('checkout_date')
        
        # Calculate price
        try:
            room_id_int = int(room_id)
        except:
            room_id_int = room_id
            
        room_resp = get_room_by_id(room_id_int)
        if not room_resp.data or not isinstance(room_resp.data, list) or len(room_resp.data) == 0:
            flash(f"ไม่พบข้อมูลห้องพัก (ID: {room_id})", "error")
            return redirect(url_for('admin_walkin'))
            
        room = room_resp.data[0]
        price_per_night = float(room['price'])
        
        d1 = datetime.strptime(checkin_date, "%Y-%m-%d")
        d2 = datetime.strptime(checkout_date, "%Y-%m-%d")
        num_days = (d2 - d1).days
        if num_days <= 0:
            flash("วันที่เช็คเอาท์ต้องอยู่หลังจากวันเช็คอิน", "error")
            return redirect(url_for('admin_walkin'))
            
        total_price = price_per_night * num_days
        
        # Add booking
        booking_data = {
            "room_id": room_id,
            "guest_name": guest_name,
            "guest_phone": guest_phone,
            "guest_email": guest_email,
            "checkin_date": checkin_date,
            "checkout_date": checkout_date,
            "total_price": total_price,
            "status": "paid",
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat() # Never expires
        }
        res = create_booking(booking_data)
        if res.data and isinstance(res.data, list) and len(res.data) > 0:
            booking_id = res.data[0]['id']
            # Add payment
            admin_supabase.table("payments").insert({
                "booking_id": booking_id,
                "amount": total_price,
                "status": "verified",
                "slip_url": "walk-in-confirmed",
                "verified_at": datetime.now(timezone.utc).isoformat()
            }).execute()
            
            # Update room status to 'O' if check-in is today
            now = datetime.now(timezone(timedelta(hours=7)))
            today_str = now.strftime('%Y-%m-%d')
            if checkin_date == today_str:
                update_room_status(room_id, "O")
                
            flash(f"ทำรายการจอง Walk-in สำหรับ {guest_name} เรียบร้อยแล้ว", "success")
            return redirect(url_for('admin_walkin'))
        else:
            flash("เกิดข้อผิดพลาดในการสร้างการจอง", "error")
            
    # GET: If dates provided, search for rooms
    total_available = 0
    if checkin_date and checkout_date:
        now = datetime.now(timezone(timedelta(hours=7)))
        current_hour = now.hour
        
        query = admin_supabase.table("bookings")\
            .select("room_id, status")\
            .in_("status", ["pending", "paid"])\
            .lt("checkin_date", checkout_date)
            
        if checkin_date == now.strftime('%Y-%m-%d') and current_hour < 9:
            query = query.gte("checkout_date", checkin_date)
        else:
            query = query.gt("checkout_date", checkin_date)
            
        res = query.execute()
        unavailable_ids = [b['room_id'] for b in (res.data or [])]
        
        # Fetch rooms with resort_types
        all_rooms_res = admin_supabase.table("rooms").select("*, resort_types(*)").neq("status", "maintenance").execute()
        
        available_rooms_grouped = {}
        for r in (all_rooms_res.data or []):
            if r['id'] not in unavailable_ids:
                res_type = r.get('resort_types')
                type_name = res_type.get('name', 'อื่นๆ') if isinstance(res_type, dict) else 'อื่นๆ'
                
                if type_name not in available_rooms_grouped:
                    available_rooms_grouped[type_name] = []
                
                available_rooms_grouped[type_name].append(r)
                total_available += 1
        
        available_rooms = available_rooms_grouped
                
    return render_template('admin/walkin.html', 
                           available_rooms=available_rooms, 
                           total_available=total_available,
                           checkin_date=checkin_date, 
                           checkout_date=checkout_date)

@app.route('/admin/daily')
def admin_daily():
    if not is_admin(): return redirect(url_for('login'))
    # Fetch bookings and filter in Python to avoid syntax issues with OR filters
    today = datetime.now(timezone(timedelta(hours=7))).strftime('%Y-%m-%d')
    resp = admin_supabase.table("bookings").select("*, rooms(*)").order("created_at", desc=True).limit(50).execute()
    # Filter bookings that check-in or check-out today
    daily_bookings = [b for b in resp.data if b['checkin_date'] == today or b['checkout_date'] == today]
    return render_template('admin/daily.html', bookings=daily_bookings, datetime=datetime)

@app.route('/admin/reports')
def admin_reports():
    if not is_admin(): return redirect(url_for('login'))
    # Only fetch 'paid' bookings for the income summary
    bookings = admin_supabase.table("bookings").select("*").eq("status", "paid").execute().data or []
    expenses = admin_supabase.table("expenses").select("*").execute().data or []
    return render_template('admin/reports.html', bookings=bookings, expenses=expenses)

@app.route('/admin/daily_income')
def admin_daily_income():
    if not is_admin(): return redirect(url_for('login'))
    
    # Get today's range in local time (ISO format)
    now = datetime.now(timezone(timedelta(hours=7)))
    today_str = now.strftime('%Y-%m-%d')
    start_time = f"{today_str}T00:00:00Z"
    end_time = f"{today_str}T23:59:59Z"
    
    # Fetch verified payments for today
    # We join with bookings and rooms to get guest and room details
    payments_resp = admin_supabase.table("payments")\
        .select("*, bookings(*, rooms(*))")\
        .eq("status", "verified")\
        .gte("verified_at", start_time)\
        .lte("verified_at", end_time)\
        .execute()
    
    payments = payments_resp.data
    
    # Process payments for display
    report_data = []
    total_amount = 0
    
    for pay in payments:
        booking = pay.get('bookings')
        if not booking: continue
        
        room = booking.get('rooms')
        
        # Calculate nights
        checkin = datetime.strptime(booking['checkin_date'], '%Y-%m-%d')
        checkout = datetime.strptime(booking['checkout_date'], '%Y-%m-%d')
        nights = (checkout - checkin).days
        
        amount = float(pay['amount'])
        total_amount += amount
        
        report_data.append({
            'guest_name': booking['guest_name'],
            'room_name': room['name'] if room else 'N/A',
            'checkin': booking['checkin_date'],
            'checkout': booking['checkout_date'],
            'nights': nights,
            'amount': amount,
            'payment_time': pay['verified_at']
        })
    
    return render_template('admin/daily_income.html', 
                           report_data=report_data, 
                           total_amount=total_amount,
                           today=today_str)

@app.route('/admin/booking/<booking_id>/receipt')
def download_receipt(booking_id):
    if not is_admin():
        # Allow customers to download their own receipts
        if not session.get('user_id'):
            return redirect(url_for('login'))
        
    # Fetch booking with room details
    res = admin_supabase.table("bookings").select("*, rooms(*)").eq("id", booking_id).execute()
    if not res.data or not isinstance(res.data, list) or len(res.data) == 0:
        flash("ไม่พบข้อมูลการจอง", "error")
        return redirect(url_for('index'))
    
    booking = res.data[0]
    
    # Security: If not admin, check if it's the customer's own booking
    if not is_admin():
        if booking.get('user_id') != session.get('user_id'):
            flash("คุณไม่มีสิทธิ์เข้าถึงข้อมูลนี้", "error")
            return redirect(url_for('index'))

    # Prepare data for PDF
    receipt_data = {
        'booking_id': booking['id'],
        'guest_name': booking['guest_name'],
        'room_name': booking['rooms']['name'] if booking.get('rooms') else 'N/A',
        'checkin': booking['checkin_date'],
        'checkout': booking['checkout_date'],
        'price': float(booking['total_price']),
        'status': booking['status']
    }
    
    pdf_bytes = generate_receipt_pdf(receipt_data)
    
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"Receipt_BannaResort_{booking_id}.pdf"
    )

@app.route('/admin/search')
def admin_search():
    if not is_admin(): return redirect(url_for('login'))
    
    query = request.args.get('q', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    room_id = request.args.get('room_id', '')
    results = []
    occupied_dates = []
    
    # Fetch all rooms for the dropdown
    rooms_list = admin_supabase.table("rooms").select("id, name, room_number").neq("status", "F").order("name").execute().data
    
    if query or (start_date and end_date) or room_id:
        all_results = []
        
        # 1. Text Search (Expanded to include room details)
        if query:
            # Search by guest name and phone
            res_name = admin_supabase.table("bookings").select("*, rooms(*)").ilike("guest_name", f"%{query}%").execute().data
            res_phone = admin_supabase.table("bookings").select("*, rooms(*)").ilike("guest_phone", f"%{query}%").execute().data
            
            # Search by room name and room number (using !inner to filter by joined table)
            try:
                res_room_name = admin_supabase.table("bookings").select("*, rooms!inner(*)").ilike("rooms.name", f"%{query}%").execute().data
                res_room_num = admin_supabase.table("bookings").select("*, rooms!inner(*)").ilike("rooms.room_number", f"%{query}%").execute().data
                if res_room_name: all_results.extend(res_room_name)
                if res_room_num: all_results.extend(res_room_num)
            except Exception as e:
                print(f"Room search join error: {e}")

            if res_name: all_results.extend(res_name)
            if res_phone: all_results.extend(res_phone)
            
        # 2. Room Filter
        if room_id:
            res_room = admin_supabase.table("bookings").select("*, rooms(*)").eq("room_id", room_id).execute().data
            if res_room: 
                if not all_results: # If only room_id is provided, use this
                    all_results.extend(res_room)
                else: # Intersect with existing results if query or date range also provided
                    existing_ids = {r['id'] for r in all_results}
                    all_results = [r for r in res_room if r['id'] in existing_ids]

        # 3. Date Range Search (Overlap logic)
        if start_date and end_date:
            res_date = admin_supabase.table("bookings")\
                .select("*, rooms(*)")\
                .lt("checkin_date", end_date)\
                .gt("checkout_date", start_date)\
                .execute().data
            
            if not all_results and not query and not room_id:
                all_results.extend(res_date)
            else:
                # Intersect
                date_ids = {r['id'] for r in res_date}
                all_results = [r for r in all_results if r['id'] in date_ids]
        
        # Merge results and remove duplicates by ID
        combined = {r['id']: r for r in all_results}
        results = sorted(combined.values(), key=lambda x: x.get('created_at', ''), reverse=True)

        # If a specific room is selected, calculate all its occupied dates (even outside search range)
        if room_id:
            upcoming_bookings = admin_supabase.table("bookings")\
                .select("checkin_date, checkout_date")\
                .eq("room_id", room_id)\
                .in_("status", ["paid", "pending"])\
                .gte("checkout_date", datetime.now(timezone(timedelta(hours=7))).strftime('%Y-%m-%d'))\
                .order("checkin_date")\
                .execute().data
            
            for b in upcoming_bookings:
                d_start = datetime.strptime(b['checkin_date'], '%Y-%m-%d')
                d_end = datetime.strptime(b['checkout_date'], '%Y-%m-%d')
                curr = d_start
                while curr < d_end: # Don't include checkout day as occupied for the next checkin
                    occupied_dates.append(curr.strftime('%Y-%m-%d'))
                    curr += timedelta(days=1)
            
            # Sort and remove duplicates (though they shouldn't exist if data is clean)
            occupied_dates = sorted(list(set(occupied_dates)))
        
    return render_template('admin/search.html', 
                           results=results, 
                           query=query, 
                           start_date=start_date, 
                           end_date=end_date,
                           room_id=room_id,
                           rooms_list=rooms_list,
                           occupied_dates=occupied_dates)

@app.route('/admin/settings', methods=['GET', 'POST'])
def admin_settings():
    if not is_admin(): return redirect(url_for('login'))
    
    if request.method == 'POST':
        data = {
            "name": request.form.get('name'),
            "phone": request.form.get('phone'),
            "address": request.form.get('address'),
            "promptpay_id": request.form.get('promptpay_id')
        }
        update_resort_settings(data)
        flash("บันทึกข้อมูลรีสอร์ทเรียบร้อยแล้ว", "success")
        return redirect(url_for('admin_settings'))
    
    settings = get_resort_settings()
    return render_template('admin/settings.html', settings=settings)

@app.route('/activities')
def public_activities():
    res = get_attractions(only_active=True)
    attractions = res.data if res.data else []
    return render_template('activities.html', attractions=attractions)

@app.route('/admin/activities', methods=['GET', 'POST'])
def admin_activities():
    if not is_admin(): return redirect(url_for('login'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action in ['add', 'edit']:
            # Handle multiple file uploads
            image_urls = []
            files = request.files.getlist('images')
            for file in files:
                if file and file.filename:
                    url = upload_to_supabase(file, 'attractions')
                    if url:
                        image_urls.append(url)
            
            # If no new images uploaded during edit, keep existing ones
            if action == 'edit' and not image_urls:
                existing_item = get_attractions(id=request.form.get('id'))
                if existing_item.data:
                    image_urls = existing_item.data[0].get('images', [])

            data = {
                "name": request.form.get('name'),
                "description": request.form.get('description'),
                "category": request.form.get('category'),
                "location_url": request.form.get('location_url'),
                "is_active": True if request.form.get('is_active') else False,
                "images": image_urls
            }
            
            if action == 'add':
                add_attraction(data)
                flash("เพิ่มข้อมูลเรียบร้อยแล้ว", "success")
            else:
                attraction_id = request.form.get('id')
                update_attraction(attraction_id, data)
                flash("แก้ไขข้อมูลเรียบร้อยแล้ว", "success")
        elif action == 'delete':
            id = request.form.get('id')
            delete_attraction(id)
            flash("ลบข้อมูลเรียบร้อยแล้ว", "success")
            
        return redirect(url_for('admin_activities'))
        
    res = get_attractions()
    attractions = res.data if res.data else []
    return render_template('admin/activities.html', attractions=attractions)

@app.route('/admin/verify_payment/<payment_id>', methods=['POST'])
def verify_payment(payment_id):
    if not is_admin(): return redirect(url_for('login'))
    
    action = request.form.get('action') # 'approve' or 'reject'
    
    try:
        payment_resp = admin_supabase.table("payments").select("*").eq("id", payment_id).execute()
        if not payment_resp.data:
            flash("ไม่พบข้อมูลการชำระเงิน", "error")
            return redirect(url_for('admin_dashboard'))
            
        payment = payment_resp.data[0]
        booking_id = payment['booking_id']
        
        if action == 'approve':
            admin_supabase.table("payments").update({"status": "verified", "verified_at": datetime.now(timezone.utc).isoformat()}).eq("id", payment_id).execute()
            update_booking_status(booking_id, "paid")
            
            # Update room status to 'O' (Occupied) once paid
            booking_res = admin_supabase.table("bookings").select("room_id").eq("id", booking_id).execute()
            if booking_res.data:
                update_room_status(booking_res.data[0]['room_id'], "O")
                
            flash("ยืนยันการชำระเงินเรียบร้อยแล้ว", "success")
        else:
            # Rejected: Update payment status
            admin_supabase.table("payments").update({"status": "rejected"}).eq("id", payment_id).execute()
            
            # Optional: Cancel booking if rejected to free up the room
            update_booking_status(booking_id, "cancelled")
            booking_res = admin_supabase.table("bookings").select("room_id").eq("id", booking_id).execute()
            if booking_res.data:
                update_room_status(booking_res.data[0]['room_id'], "I")
                
            flash("ปฏิเสธการชำระเงินเรียบร้อยแล้ว และคืนสถานะห้องพักเป็น 'ว่าง'", "info")
            
    except Exception as e:
        flash(f"เกิดข้อผิดพลาดในการประมวลผล: {str(e)}", "error")
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/walkin_confirm/<booking_id>', methods=['POST'])
def admin_walkin_confirm(booking_id):
    if not is_admin(): return redirect(url_for('login'))
    
    try:
        # 1. Fetch booking to get room_id
        res = admin_supabase.table("bookings").select("room_id, total_price").eq("id", booking_id).execute()
        if not res.data:
            flash("ไม่พบข้อมูลการจองในระบบ", "error")
            return redirect(url_for('admin_dashboard'))
            
        booking = res.data[0]
        room_id = booking['room_id']
        amount = float(booking['total_price'])
        
        # 2. Update booking status to 'paid'
        admin_supabase.table("bookings").update({"status": "paid"}).eq("id", booking_id).execute()
        
        # 3. Update room status to 'O' (Occupied)
        # Using a direct update to be 100% sure
        admin_supabase.table("rooms").update({"status": "O"}).eq("id", room_id).execute()
        
        # 4. Create verified payment record
        admin_supabase.table("payments").insert({
            "booking_id": booking_id,
            "amount": amount,
            "status": "verified",
            "slip_url": "walk-in-confirmed",
            "verified_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        
        flash("ดำเนินการยืนยัน Walk-in และอัพเดทสถานะห้องพักเป็น 'ไม่ว่าง' เรียบร้อยแล้ว", "success")
        return redirect(url_for('admin_rooms'))
        
    except Exception as e:
        flash(f"เกิดข้อผิดพลาด: {str(e)}", "error")
        return redirect(url_for('admin_dashboard'))

@app.route('/view_receipt/<booking_id>')
def view_receipt(booking_id):
    # Only admins or the owner of the booking can view the receipt
    is_admin_user = session.get('role') in ['admin', 'super_admin']
    user_id = session.get('user_id')
    
    # Fetch booking with room details
    booking_res = admin_supabase.table("bookings")\
        .select("*, rooms(*)").eq("id", booking_id).execute()
    
    if not booking_res.data:
        flash("ไม่พบข้อมูลการจอง", "error")
        return redirect(url_for('index'))
    
    booking = booking_res.data[0]
    
    # Permission check: Admin or the guest themself
    if not is_admin_user and booking['user_id'] != user_id:
        flash("คุณไม่มีสิทธิ์เข้าถึงใบเสร็จนี้", "error")
        return redirect(url_for('index'))
        
    return render_template('admin/receipt.html', booking=booking)

@app.route('/admin/expenses', methods=['POST'])
def add_expense_route():
    title = request.form.get('title')
    amount = request.form.get('amount')
    category = request.form.get('category')
    
    add_expense({
        "title": title,
        "amount": amount,
        "category": category
    })
    
    flash("บันทึกรายจ่ายเรียบร้อยแล้ว", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/receipt/<booking_id>')
def get_receipt(booking_id):
    booking_resp = admin_supabase.table("bookings").select("*, rooms(name)").eq("id", booking_id).execute()
    if not booking_resp.data:
        return "No booking found", 404
    
    booking = booking_resp.data[0]
    data = {
        "guest_name": booking['guest_name'],
        "room_name": booking['rooms']['name'],
        "checkin": booking['checkin_date'],
        "checkout": booking['checkout_date'],
        "price": float(booking['total_price']),
        "booking_id": str(booking['id'])
    }
    
    pdf_content = generate_receipt_pdf(data)
    
    return send_file(
        io.BytesIO(pdf_content),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"receipt_{booking_id}.pdf"
    )

# --- Error Handlers ---
@app.errorhandler(404)
def page_not_found(e):
    return render_template('index.html'), 404

# --- Admin & User Management ---

@app.route('/admin/users')
def admin_users():
    # Auto-refresh session role from DB
    if session.get('user_id'):
        profile = admin_supabase.table("profiles").select("role").eq("id", session['user_id']).execute()
        if profile.data and len(profile.data) > 0:
            session['role'] = profile.data[0]['role']

    # Only super_admin can see this
    if not is_super_admin(): 
        flash("หน้า 'จัดการแอดมิน' สงวนสิทธิ์สำหรับ Super Admin เท่านั้นครับ (หากคุณเพิ่งได้รับสิทธิ์ กรุณาลอง Refresh หน้าจออีกครั้ง)", "error")
        return redirect(url_for('admin_dashboard'))
    
    admins_resp = admin_supabase.table("profiles")\
        .select("*")\
        .in_("role", ["admin", "super_admin"])\
        .order("role", desc=True)\
        .execute()
    
    return render_template('admin/users.html', admins=admins_resp.data)

@app.route('/admin/add_admin', methods=['POST'])
def add_admin():
    if not is_super_admin(): return redirect(url_for('admin_dashboard'))
    email = request.form.get('email')
    
    # Check limit: 5 admins max (Total includes super_admin + admin)
    admins_count = admin_supabase.table("profiles").select("id", count="exact").in_("role", ["admin", "super_admin"]).execute()
    if admins_count.count >= 6:
        flash("ไม่สามารถเพิ่ม Admin ได้มากกว่า 5 ท่าน (ไม่รวมตัวท่านเองที่เป็น Super Admin)", "error")
        return redirect(url_for('admin_users'))
    
    # Update user role
    res = admin_supabase.table("profiles").update({"role": "admin"}).eq("email", email).execute()
    
    if res.data:
        flash(f"เพิ่ม {email} เป็น Admin เรียบร้อยแล้ว", "success")
    else:
        flash("ไม่พบผู้ใช้งานรายนี้ในระบบ (ผู้ใช้ต้องลงทะเบียนก่อน)", "error")
        
    return redirect(url_for('admin_users'))

@app.route('/admin/remove_user/<user_id>', methods=['POST'])
def remove_user(user_id):
    if not is_super_admin(): return redirect(url_for('admin_dashboard'))
    
    # Check if target is a super_admin
    target = admin_supabase.table("profiles").select("role").eq("id", user_id).execute()
    if target.data and target.data[0]['role'] == 'super_admin':
        flash("ไม่สามารถถอดถอนสิทธิ์ Super Admin ได้", "error")
        return redirect(url_for('admin_users'))

    # Demote to customer
    admin_supabase.table("profiles").update({"role": "customer"}).eq("id", user_id).execute()
    flash("ถอดถอนสิทธิ์เรียบร้อยแล้ว", "info")
    return redirect(url_for('admin_users'))

# --- Resort Types Management ---
@app.route('/admin/resort_types')
def admin_resort_types():
    if not is_admin(): return redirect(url_for('login'))
    types_resp = admin_supabase.table("resort_types").select("*").order("created_at", desc=True).execute()
    return render_template('admin/resort_types.html', resort_types=types_resp.data if types_resp else [])

@app.route('/admin/add_resort_type', methods=['POST'])
def add_resort_type():
    if not is_admin(): return redirect(url_for('login'))
    name = request.form.get('name')
    if name:
        admin_supabase.table("resort_types").insert({"name": name}).execute()
        flash("เพิ่มประเภทรีสอร์ทเรียบร้อยแล้ว", "success")
    return redirect(url_for('admin_resort_types'))

@app.route('/admin/delete_resort_type/<int:type_id>', methods=['POST'])
def delete_resort_type(type_id):
    if not is_admin(): return redirect(url_for('login'))
    try:
        admin_supabase.table("resort_types").delete().eq("id", type_id).execute()
        flash("ลบประเภทรีสอร์ทเรียบร้อยแล้ว", "success")
    except Exception as e:
        flash("ไม่สามารถลบได้ เนื่องจากมีห้องพักที่ใช้ประเภทนี้อยู่", "error")
    return redirect(url_for('admin_resort_types'))

# --- Room Management ---

@app.route('/admin/rooms')
def admin_rooms():
    if not is_admin(): return redirect(url_for('login'))
    
    # We fetch rooms and join with resort_types
    rooms_resp = admin_supabase.table("rooms").select("*, resort_types(name)").neq("status", "F").order("created_at", desc=True).execute()
    rooms = rooms_resp.data if rooms_resp else []
    
    # Fetch available resort types for the dropdowns
    types_resp = admin_supabase.table("resort_types").select("*").order("created_at", desc=True).execute()
    resort_types = types_resp.data if types_resp else []
    
    return render_template('admin/rooms.html', rooms=rooms, resort_types=resort_types)

@app.route('/admin/add_room', methods=['POST'])
def admin_add_room():
    if not is_admin(): return redirect(url_for('login'))
    
    room_number = request.form.get('room_number')
    name = request.form.get('name')
    price = request.form.get('price')
    bed_type = request.form.get('bed_type')
    description = request.form.get('description')
    resort_type_id = request.form.get('resort_type_id')
    
    # Handle multiple image uploads
    image_urls = []
    files = request.files.getlist('images')
    
    for file in files:
        if file and file.filename:
            try:
                ext = file.filename.split('.')[-1].lower()
                filename = f"{uuid.uuid4()}.{ext}"
                file_data = file.read()
                
                # Standardize MIME type
                mime_type = f"image/{ext}"
                if ext in ['jpg', 'jpeg']: mime_type = "image/jpeg"
                elif ext == 'png': mime_type = "image/png"
                
                print(f"Uploading {filename} (Type: {mime_type}) to Supabase Storage...")
                
                # Upload to Supabase Storage
                admin_supabase.storage.from_("room_images").upload(
                    path=filename,
                    file=file_data,
                    file_options={"content-type": mime_type}
                )
                
                # Get Public URL
                url_res = admin_supabase.storage.from_("room_images").get_public_url(filename)
                image_urls.append(url_res)
                print(f"Upload success: {url_res}")
            except Exception as e:
                print(f"Upload error: {e}")
                flash(f"Error uploading image: {str(e)}", "error")

    room_data = {
        "room_number": room_number,
        "name": name,
        "price": float(price),
        "bed_type": bed_type,
        "description": description,
        "images": image_urls, # JSONB array
        "status": "I",
        "resort_type_id": int(resort_type_id) if resort_type_id else None
    }
    
    res = add_room(room_data)
    if res.data:
        flash("เพิ่มห้องพักเรียบร้อยแล้ว", "success")
    else:
        flash("เกิดข้อผิดพลาดในการเพิ่มห้องพัก", "error")
        
    return redirect(url_for('admin_rooms'))

@app.route('/admin/edit_room/<room_id>', methods=['POST'])
def admin_edit_room(room_id):
    if not is_admin(): return redirect(url_for('login'))
    
    room_number = request.form.get('room_number')
    name = request.form.get('name')
    price = request.form.get('price')
    bed_type = request.form.get('bed_type')
    description = request.form.get('description')
    resort_type_id = request.form.get('resort_type_id')
    
    # Get existing room to keep old images
    room_res = get_room_by_id(room_id)
    if not room_res.data:
        flash("ไม่พบข้อมูลห้องพัก", "error")
        return redirect(url_for('admin_rooms'))
        
    image_urls = room_res.data[0].get('images', []) or []
    
    # Handle new image uploads
    files = request.files.getlist('images')
    for file in files:
        if file and file.filename:
            try:
                ext = file.filename.split('.')[-1].lower()
                filename = f"{uuid.uuid4()}.{ext}"
                file_data = file.read()
                
                # Standardize MIME type
                mime_type = f"image/{ext}"
                if ext in ['jpg', 'jpeg']: mime_type = "image/jpeg"
                elif ext == 'png': mime_type = "image/png"
                
                print(f"Uploading {filename} (Type: {mime_type}) to Slips...")
                
                admin_supabase.storage.from_("room_images").upload(
                    path=filename,
                    file=file_data,
                    file_options={"content-type": mime_type}
                )
                
                url_res = admin_supabase.storage.from_("room_images").get_public_url(filename)
                image_urls.append(url_res)
            except Exception as e:
                print(f"Upload error: {e}")
                
    update_data = {
        "room_number": room_number,
        "name": name,
        "price": float(price),
        "bed_type": bed_type,
        "description": description,
        "images": image_urls,
        "resort_type_id": int(resort_type_id) if resort_type_id else None
    }
    
    res = update_room(room_id, update_data)
    if res.data:
        flash("แก้ไขข้อมูลห้องพักเรียบร้อยแล้ว", "success")
    else:
        flash("เกิดข้อผิดพลาดในการแก้ไขข้อมูล", "error")
        
    return redirect(url_for('admin_rooms'))

@app.route('/admin/delete_room/<room_id>', methods=['POST'])
def admin_delete_room(room_id):
    if not is_admin(): return redirect(url_for('login'))
    
    try:
        delete_room(room_id)
        flash("ลบห้องพักออกจากระบบเรียบร้อยแล้ว", "success")
    except Exception as e:
        print(f"Error deleting room: {e}")
        # Could be a foreign key constraint issue
        flash("ไม่สามารถลบห้องพักได้ (อาจมีข้อมูลการจองผูกกับห้องนี้อยู่)", "error")
        
    return redirect(url_for('admin_rooms'))

@app.route('/admin/update_room_status/<room_id>', methods=['POST'])
def admin_update_room_status(room_id):
    if not is_admin(): return redirect(url_for('login'))
    new_status = request.form.get('status')
    if new_status in ['I', 'O', 'R']:
        update_room_status(room_id, new_status)
        flash("อัปเดตสถานะห้องพักเรียบร้อยแล้ว", "success")
    else:
        flash("สถานะไม่ถูกต้อง", "error")
    return redirect(url_for('admin_rooms'))

@app.route('/admin/delete_booking/<booking_id>', methods=['POST'])
def admin_delete_booking(booking_id):
    if not is_admin(): return redirect(url_for('login'))
    
    # Optional: Get room_id to revert status
    try:
        booking_res = admin_supabase.table("bookings").select("room_id").eq("id", booking_id).execute()
        if booking_res.data:
            room_id = booking_res.data[0]['room_id']
            update_room_status(room_id, "I")
    except Exception as e:
        print(f"Error reverting room status: {e}")
    
    res = delete_booking(booking_id)
    if res.data:
        flash("ลบรายการจองเรียบร้อยแล้ว และคืนสถานะห้องพักเป็นว่าง", "info")
    else:
        flash("เกิดข้อผิดพลาดในการลบรายการจอง", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_expense/<expense_id>', methods=['POST'])
def admin_delete_expense(expense_id):
    if not is_admin(): return redirect(url_for('login'))
    res = delete_expense(expense_id)
    if res.data:
        flash("ลบบันทึกรายจ่ายเรียบร้อยแล้ว", "info")
    else:
        flash("ไม่สามารถลบรายจ่ายได้", "error")
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
