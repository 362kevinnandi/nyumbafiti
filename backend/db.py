import os
from motor.motor_asyncio import AsyncIOMotorClient

_client: AsyncIOMotorClient | None = None
_db = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return _client


def get_db():
    global _db
    if _db is None:
        _db = get_client()[os.environ["DB_NAME"]]
    return _db


async def ensure_indexes():
    db = get_db()
    await db["users"].create_index("email", unique=True)
    await db["payments"].create_index("idempotency_key", unique=True, sparse=True)
    await db["payments"].create_index("checkout_request_id")
    await db["bills"].create_index([("tenant_id", 1), ("status", 1)])
    await db["bills"].create_index([("property_id", 1), ("period", 1)])
    await db["units"].create_index("property_id")
    await db["issues"].create_index([("status", 1), ("created_at", -1)])
    await db["viewings"].create_index([("landlord_id", 1), ("status", 1)])
    await db["viewings"].create_index("prospect_id")
    await db["units"].create_index([("occupied", 1), ("rent_amount", 1)])
