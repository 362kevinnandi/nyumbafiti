"""In-app notification helpers — called from other routers when events occur."""
from typing import Iterable, Optional

from db import get_db
from models import new_id, now_iso


async def notify_user(
    user_id: str,
    kind: str,
    title: str,
    body: str,
    link: Optional[str] = None,
) -> None:
    db = get_db()
    doc = {
        "id": new_id(),
        "user_id": user_id,
        "kind": kind,
        "title": title,
        "body": body,
        "link": link,
        "read": False,
        "created_at": now_iso(),
    }
    await db["notifications"].insert_one(doc)


async def notify_many(
    user_ids: Iterable[str],
    kind: str,
    title: str,
    body: str,
    link: Optional[str] = None,
) -> None:
    db = get_db()
    now = now_iso()
    docs = [
        {
            "id": new_id(),
            "user_id": uid,
            "kind": kind,
            "title": title,
            "body": body,
            "link": link,
            "read": False,
            "created_at": now,
        }
        for uid in user_ids
        if uid
    ]
    if docs:
        await db["notifications"].insert_many(docs)
