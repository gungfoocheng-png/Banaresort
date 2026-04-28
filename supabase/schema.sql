-- Baan Na Resort Database Schema

-- 1. Profiles Table (Extends Supabase Auth)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    role TEXT DEFAULT 'customer' CHECK (role IN ('super_admin', 'admin', 'customer')),
    full_name TEXT,
    display_name TEXT,
    phone TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Rooms Table
CREATE TABLE IF NOT EXISTS public.rooms (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'available' CHECK (status IN ('available', 'maintenance', 'occupied', 'reserved')),
    images TEXT[] DEFAULT '{}',
    -- Map coordinates: JSON structure like {"x": 10, "y": 20, "width": 5, "height": 5}
    map_coords JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Bookings Table
CREATE TABLE IF NOT EXISTS public.bookings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id INTEGER REFERENCES public.rooms(id) ON DELETE CASCADE,
    user_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL, -- Null for Walk-ins
    guest_name TEXT NOT NULL,
    guest_phone TEXT NOT NULL,
    guest_email TEXT,
    checkin_date DATE NOT NULL,
    checkout_date DATE NOT NULL,
    total_price DECIMAL(10, 2) NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'paid', 'cancelled', 'expired')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL -- Set to created_at + 1 hour in code
);

-- 4. Payments Table
CREATE TABLE IF NOT EXISTS public.payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id UUID REFERENCES public.bookings(id) ON DELETE CASCADE,
    slip_url TEXT,
    amount DECIMAL(10, 2) NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'verified', 'rejected')),
    verified_at TIMESTAMPTZ,
    verified_by UUID REFERENCES public.profiles(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Expenses Table
CREATE TABLE IF NOT EXISTS public.expenses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    description TEXT,
    category TEXT CHECK (category IN ('utility', 'maintenance', 'salary', 'other')),
    created_by UUID REFERENCES public.profiles(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS (Optional, since Flask handles logic, but good practice)
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rooms ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bookings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.expenses ENABLE ROW LEVEL SECURITY;

-- Seed Data: Sample Rooms
INSERT INTO public.rooms (name, price, description, map_coords) VALUES
('บ้านนา 1 (Standard)', 1200.00, 'ห้องพักมาตรฐาน เตียงเดี่ยว วิวทุ่งนา', '{"x": 10, "y": 10, "label": "A1"}'),
('บ้านนา 2 (Standard)', 1200.00, 'ห้องพักมาตรฐาน เตียงเดี่ยว วิวทุ่งนา', '{"x": 25, "y": 10, "label": "A2"}'),
('บ้านนา 3 (Superior)', 1500.00, 'ห้องพักกว้างขวาง พร้อมสิ่งอำนวยความสะดวกครบครัน', '{"x": 40, "y": 10, "label": "A3"}'),
('บ้านนา 4 (Superior)', 1500.00, 'ห้องพักกว้างขวาง พร้อมสิ่งอำนวยความสะดวกครบครัน', '{"x": 55, "y": 10, "label": "A4"}'),
('เรือนไทย 1 (Deluxe)', 2500.00, 'บ้านไม้ทรงไทยดั้งเดิมบรรยากาศอบอุ่น', '{"x": 10, "y": 35, "label": "B1"}'),
('เรือนไทย 2 (Deluxe)', 2500.00, 'บ้านไม้ทรงไทยดั้งเดิมบรรยากาศอบอุ่น', '{"x": 25, "y": 35, "label": "B2"}'),
('ริมน้ำ 1 (VIP)', 3500.00, 'บ้านพักติดริมน้ำ บรรยากาศสุดส่วนตัว', '{"x": 50, "y": 50, "label": "V1"}'),
('ริมน้ำ 2 (VIP)', 3500.00, 'บ้านพักติดริมน้ำ บรรยากาศสุดส่วนตัว', '{"x": 70, "y": 50, "label": "V2"}'),
('ครอบครัว 1', 4500.00, 'บ้านพักขนาดใหญ่สำหรับครอบครัว 4-6 ท่าน', '{"x": 10, "y": 70, "label": "F1"}'),
('ครอบครัว 2', 4500.00, 'บ้านพักขนาดใหญ่สำหรับครอบครัว 4-6 ท่าน', '{"x": 30, "y": 70, "label": "F2"}');
