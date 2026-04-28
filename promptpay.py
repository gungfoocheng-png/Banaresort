
def crc16(data: str) -> str:
    """
    CRC-16/CCITT-FALSE implementation.
    """
    crc = 0xFFFF
    for byte in data.encode('ascii'):
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return f"{crc:04X}"

def generate(pp_id: str, amount: float = None) -> str:
    """
    Pure Python implementation of PromptPay QR payload generation.
    """
    # Payload Format Indicator
    payload = "000201"
    
    # Point of Initiation Method (12 for dynamic/amount, 11 for static)
    payload += "010212" if amount else "010211"
    
    # Merchant Account Information (PromptPay)
    # GUID + Account ID
    pp_id = str(pp_id).replace("-", "").replace(" ", "")
    if len(pp_id) == 10: # Mobile
        account_id = "011300" + pp_id
    else: # National ID
        account_id = "0213" + pp_id
        
    merchant_info = "0010A000000677010111" + account_id
    payload += f"29{len(merchant_info):02}{merchant_info}"
    
    # Country Code
    payload += "5802TH"
    
    # Currency (764 for THB)
    payload += "5303764"
    
    # Amount
    if amount:
        amount_str = f"{amount:.2f}"
        payload += f"54{len(amount_str):02}{amount_str}"
        
    # CRC
    payload += "6304"
    payload += crc16(payload)
    
    return payload
