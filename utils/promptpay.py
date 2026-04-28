import promptpay
import qrcode
import io
import base64
import os

def generate_promptpay_qr(amount, pp_id=None):
    """
    Generate a PromptPay QR code image as a base64 string.
    """
    if not pp_id:
        pp_id = os.getenv("PROMPTPAY_ID", "0812345678")
    
    # Generate PromptPay payload
    payload = promptpay.generate(pp_id, amount)
    
    # Create QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save to buffer
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    
    # Convert to base64
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return img_str
