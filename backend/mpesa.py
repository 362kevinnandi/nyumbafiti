"""M-Pesa Daraja STK Push client with demo fallback."""
import asyncio
import base64
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx


def _eat_now() -> datetime:
    """East Africa Time (UTC+3, no DST)."""
    return datetime.now(timezone.utc) + timedelta(hours=3)


def generate_timestamp() -> str:
    return _eat_now().strftime("%Y%m%d%H%M%S")


def generate_password(shortcode: str, passkey: str, timestamp: str) -> str:
    data = f"{shortcode}{passkey}{timestamp}".encode()
    return base64.b64encode(data).decode()


def is_demo_mode() -> bool:
    """Return True when real Daraja credentials are missing."""
    return not (os.environ.get("MPESA_CONSUMER_KEY") and os.environ.get("MPESA_CONSUMER_SECRET"))


def _base_url() -> str:
    env = os.environ.get("MPESA_ENVIRONMENT", "sandbox")
    return (
        "https://sandbox.safaricom.co.ke"
        if env == "sandbox"
        else "https://api.safaricom.co.ke"
    )


async def get_access_token() -> str:
    url = f"{_base_url()}/oauth/v1/generate?grant_type=client_credentials"
    auth = (os.environ["MPESA_CONSUMER_KEY"], os.environ["MPESA_CONSUMER_SECRET"])
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, auth=auth)
        resp.raise_for_status()
        return resp.json()["access_token"]


async def stk_push(
    phone: str,
    amount: float,
    account_ref: str,
    description: str,
    callback_url: str,
) -> dict:
    """Initiate STK push. In demo mode returns simulated response."""
    if is_demo_mode():
        # Demo mode - generate fake IDs that look real
        ts = generate_timestamp()
        return {
            "MerchantRequestID": f"demo-{ts}",
            "CheckoutRequestID": f"ws_CO_demo_{ts}",
            "ResponseCode": "0",
            "ResponseDescription": "Success. Request accepted for processing (DEMO MODE).",
            "CustomerMessage": "Demo STK push - payment will auto-confirm in a few seconds.",
            "_demo": True,
        }

    token = await get_access_token()
    shortcode = os.environ["MPESA_SHORTCODE"]
    passkey = os.environ["MPESA_PASSKEY"]
    timestamp = generate_timestamp()
    password = generate_password(shortcode, passkey, timestamp)

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(round(amount)),
        "PartyA": phone,
        "PartyB": shortcode,
        "PhoneNumber": phone,
        "CallBackURL": callback_url,
        "AccountReference": account_ref[:20],
        "TransactionDesc": (description or "Rental payment")[:13],
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    url = f"{_base_url()}/mpesa/stkpush/v1/processrequest"
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()


def normalize_phone(phone: str) -> str:
    """Normalize Kenyan phone to 2547XXXXXXXX format."""
    phone = phone.strip().replace(" ", "").replace("-", "").replace("+", "")
    if phone.startswith("0") and len(phone) == 10:
        phone = "254" + phone[1:]
    elif phone.startswith("7") and len(phone) == 9:
        phone = "254" + phone
    return phone


async def schedule_demo_callback(checkout_request_id: str, callback_func, delay: float = 4.0):
    """Simulate a Safaricom callback after a delay (demo mode only)."""
    await asyncio.sleep(delay)
    fake_payload = {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": f"demo-{checkout_request_id}",
                "CheckoutRequestID": checkout_request_id,
                "ResultCode": 0,
                "ResultDesc": "The service request is processed successfully.",
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": 0},
                        {"Name": "MpesaReceiptNumber", "Value": f"DEMO{datetime.utcnow().strftime('%H%M%S')}"},
                        {"Name": "TransactionDate", "Value": int(_eat_now().strftime("%Y%m%d%H%M%S"))},
                        {"Name": "PhoneNumber", "Value": 254700000000},
                    ]
                },
            }
        }
    }
    await callback_func(fake_payload)
