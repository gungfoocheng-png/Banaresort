from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
import os

def generate_receipt_pdf(data):
    """
    Generate a PDF receipt.
    Expected data keys: guest_name, room_name, checkin, checkout, price, booking_id
    """
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Note: For Thai fonts, we would need to register a .ttf file.
    # For now, we'll use fallback, but in a real app, we'd include THSarabun.ttf
    # try:
    #     pdfmetrics.registerFont(TTFont('THSarabun', 'path/to/THSarabun.ttf'))
    #     p.setFont('THSarabun', 16)
    # except:
    p.setFont("Helvetica-Bold", 24)

    # Header
    p.drawCentredString(width/2, height - 3*cm, "ใบเสร็จรับเงิน / RECEIPT")
    p.setFont("Helvetica", 14)
    p.drawCentredString(width/2, height - 4*cm, "บ้านนารีสอร์ท (Baan Na Resort)")
    
    p.line(2*cm, height - 5*cm, width - 2*cm, height - 5*cm)

    # Content
    y = height - 6*cm
    p.drawString(2*cm, y, f"หมายเลขจอง (Booking ID): {data['booking_id']}")
    y -= 1*cm
    p.drawString(2*cm, y, f"ชื่อลูกค้า (Customer): {data['guest_name']}")
    y -= 1*cm
    p.drawString(2*cm, y, f"ห้องพัก (Room): {data['room_name']}")
    y -= 1*cm
    p.drawString(2*cm, y, f"เช็คอิน (Check-in): {data['checkin']}")
    y -= 1*cm
    p.drawString(2*cm, y, f"เช็คเอาท์ (Check-out): {data['checkout']}")
    
    p.line(2*cm, y - 1*cm, width - 2*cm, y - 1*cm)
    
    y -= 2*cm
    p.setFont("Helvetica-Bold", 18)
    p.drawString(2*cm, y, "ยอดรวม (Total Price):")
    p.drawRightString(width - 2*cm, y, f"{data['price']:,} บาท (THB)")

    p.setFont("Helvetica", 12)
    p.drawCentredString(width/2, 4*cm, "ขอบคุณที่ใช้บริการบ้านนารีสอร์ท")
    p.drawCentredString(width/2, 3.5*cm, "Thank you for staying with us!")

    p.showPage()
    p.save()

    buffer.seek(0)
    return buffer.getvalue()
