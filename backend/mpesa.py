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


def should_use_demo_fallback(resp: dict) -> bool:
    """Demo fallback fires ONLY in pure demo mode (no Daraja credentials at all)
    or when the live STK push call FAILED and degraded to a synthetic response (resp["_demo"]=True).

    Importantly: we no longer schedule the demo callback for every real STK push.
    The previous behaviour caused false-positive 'paid' marks when the user
    didn't enter their PIN within the demo-fallback window.
    """
    if resp.get("_demo"):
        return True
    if is_demo_mode():
        return True
    return False


def fallback_delay_seconds() -> float:
    return 4.0 if is_demo_mode() else 6.0


async def query_stk_status(checkout_request_id: str) -> dict:
    """Hit Safaricom Daraja /mpesa/stkpushquery/v1/query to learn the REAL status
    of an STK push (paid / cancelled / timeout / still pending).

    Response includes ResultCode (0 = success, other = failure) and ResultDesc.
    """
    token = await get_access_token()
    shortcode = os.environ["MPESA_SHORTCODE"]
    passkey = os.environ["MPESA_PASSKEY"]
    timestamp = generate_timestamp()
    password = generate_password(shortcode, passkey, timestamp)
    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "CheckoutRequestID": checkout_request_id,
    }
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"{_base_url()}/mpesa/stkpushquery/v1/query"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, headers=headers, json=payload)
        # Safaricom returns 500 with a JSON body for some error states
        try:
            return resp.json()
        except Exception:
            return {"ResultCode": "1", "ResultDesc": f"Query failed HTTP {resp.status_code}", "_status": resp.status_code}


def _base_url() -> str:
    env = os.environ.get("MPESA_ENVIRONMENT", "sandbox")
    return (
        "https://sandbox.safaricom.co.ke"
        if env == "sandbox"
        else "https://api.safaricom.co.ke"
    )


_TOKEN_CACHE: dict = {"token": None, "expires_at": 0.0}


async def get_access_token() -> str:
    """Cache the access token for ~55 min (Safaricom expires it at 3599s).

    Without caching, Safaricom rate-limits the oauth endpoint at ~1/sec and
    starts returning 429/403 which then surfaces to the user as 'M-Pesa request failed'.
    """
    import time
    now = time.time()
    if _TOKEN_CACHE.get("token") and _TOKEN_CACHE.get("expires_at", 0) > now:
        return _TOKEN_CACHE["token"]
    url = f"{_base_url()}/oauth/v1/generate?grant_type=client_credentials"
    auth = (os.environ["MPESA_CONSUMER_KEY"], os.environ["MPESA_CONSUMER_SECRET"])
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, auth=auth)
        resp.raise_for_status()
        data = resp.json()
        token = data["access_token"]
        ttl = int(data.get("expires_in", 3599))
        _TOKEN_CACHE["token"] = token
        _TOKEN_CACHE["expires_at"] = now + ttl - 30  # refresh 30s before expiry
        return token


def _sanitize_text(s: str, max_len: int) -> str:
    """Safaricom's XSLT pipeline chokes on ampersands & angle brackets in TransactionDesc + AccountReference.

    Strip anything outside alphanumeric, dash, underscore, space, period — and truncate to max_len.
    """
    if not s:
        return ""
    cleaned = "".join(c if (c.isalnum() or c in "-_ .") else " " for c in s).strip()
    return cleaned[:max_len] or "Payment"


async def stk_push(
    phone: str,
    amount: float,
    account_ref: str,
    description: str,
    callback_url: str,
) -> dict:
    """Initiate STK push. In demo mode returns simulated response.

    If real Daraja fails AND MPESA_DEMO_FALLBACK=true, gracefully degrade to a
    simulated response so end-to-end tests continue working (e.g. when the
    sandbox keys + passkey + shortcode aren't perfectly matched).
    """
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

    try:
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
            "AccountReference": _sanitize_text(account_ref, 20),
            "TransactionDesc": _sanitize_text(description or "Rental payment", 13),
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
    except Exception as exc:
        # If a fallback is allowed, log + return a synthetic accepted response so the demo callback
        # safety net still settles the payment. Real production should set MPESA_DEMO_FALLBACK=false.
        if os.environ.get("MPESA_DEMO_FALLBACK", "false").lower() in ("true", "1", "yes"):
            ts = generate_timestamp()
            return {
                "MerchantRequestID": f"fallback-{ts}",
                "CheckoutRequestID": f"ws_CO_fallback_{ts}",
                "ResponseCode": "0",
                "ResponseDescription": f"Sandbox rejected request — falling back to demo. Original error: {exc}",
                "CustomerMessage": "Sandbox unavailable. We'll auto-confirm in ~15s for testing.",
                "_demo": True,
            }
        raise


def normalize_phone(phone: str) -> str:
    """Normalize Kenyan phone to 2547XXXXXXXX format."""
    phone = phone.strip().replace(" ", "").replace("-", "").replace("+", "")
    if phone.startswith("0") and len(phone) == 10:
        phone = "254" + phone[1:]
    elif phone.startswith("7") and len(phone) == 9:
        phone = "254" + phone
    return phone


async def schedule_demo_callback(checkout_request_id: str, callback_func, delay: Optional[float] = None):
    """Simulate a Safaricom callback after a delay (demo mode + sandbox-fallback safety net)."""
    await asyncio.sleep(delay if delay is not None else fallback_delay_seconds())
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


async def schedule_status_poll(
    checkout_request_id: str,
    callback_func,
    poll_intervals=(15, 30, 50, 75, 100),
):
    """For real Daraja STK pushes: query Safaricom at intervals to learn the true status.

    - ResultCode == "0" → success → synthesize a success callback (so payments_router can settle it).
    - ResultCode != "0" AND not a "still being processed" code → failure → synthesize failure callback.
    - Any other state at the final interval → mark failed (timeout / user never entered PIN).
    """
    for delay in poll_intervals:
        await asyncio.sleep(delay - sum(p for p in poll_intervals if p < delay))
        try:
            data = await query_stk_status(checkout_request_id)
        except Exception as exc:
            data = {"ResultCode": "-1", "ResultDesc": f"Query error: {exc}"}
        code = str(data.get("ResultCode", ""))
        desc = data.get("ResultDesc", "") or data.get("errorMessage", "")
        # "1032" = user cancelled; "1037" = timeout (DS unable to reach phone); "1" = insufficient funds; "0" = success
        # "500.001.1001" = "still being processed" — keep polling
        if code == "0":
            await callback_func(_synth_callback(checkout_request_id, 0, desc or "Success"))
            return
        if code in ("1032", "1037", "1", "1019", "1025", "1031", "2001"):
            await callback_func(_synth_callback(checkout_request_id, int(code) if code.isdigit() else 1032, desc or "Cancelled/timeout"))
            return
        if "still being processed" not in (desc or "").lower() and code not in ("", "500.001.1001"):
            # Some other definite failure
            await callback_func(_synth_callback(checkout_request_id, 1, desc or "Unknown failure"))
            return
        # else: keep polling
    # Final timeout — mark failed so tenant can retry
    await callback_func(_synth_callback(checkout_request_id, 1037, "STK push timed out — user did not respond"))


def _synth_callback(checkout_request_id: str, result_code: int, result_desc: str) -> dict:
    """Build a Safaricom-shape callback payload from a status query result."""
    metadata = []
    if result_code == 0:
        metadata = [
            {"Name": "Amount", "Value": 0},
            {"Name": "MpesaReceiptNumber", "Value": f"STK{datetime.utcnow().strftime('%H%M%S')}"},
            {"Name": "TransactionDate", "Value": int(_eat_now().strftime("%Y%m%d%H%M%S"))},
            {"Name": "PhoneNumber", "Value": 254700000000},
        ]
    return {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": f"poll-{checkout_request_id}",
                "CheckoutRequestID": checkout_request_id,
                "ResultCode": result_code,
                "ResultDesc": result_desc,
                "CallbackMetadata": {"Item": metadata} if metadata else {},
            }
        }
    }
