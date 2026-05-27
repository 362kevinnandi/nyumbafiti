"""Nairobi Rental Management - Main FastAPI app."""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import APIRouter, Depends, FastAPI
from fastapi.staticfiles import StaticFiles  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402

from auth import get_current_user  # noqa: E402
from db import ensure_indexes, get_client, get_db  # noqa: E402
from routers.auth_router import router as auth_router  # noqa: E402
from routers.bills_router import router as bills_router  # noqa: E402
from routers.issues_router import router as issues_router  # noqa: E402
from routers.payments_router import router as payments_router  # noqa: E402
from routers.properties_router import router as properties_router  # noqa: E402
from routers.users_router import router as users_router  # noqa: E402
from routers.viewings_router import router as viewings_router  # noqa: E402
from routers.admin_router import router as admin_router  # noqa: E402
from routers.oversight_router import router as oversight_router  # noqa: E402
from routers.community_router import router as community_router  # noqa: E402
from routers.notifications_router import router as notifications_router  # noqa: E402
from routers.yardsale_router import router as yardsale_router  # noqa: E402
from routers.leases_router import router as leases_router  # noqa: E402
from routers.visitors_router import router as visitors_router  # noqa: E402
from routers.ai_router import router as ai_router  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("rental-mgmt")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_indexes()
    await _seed_admin()
    await _migrate_approval_status()
    logger.info("Indexes ensured. App ready.")
    yield
    get_client().close()


async def _migrate_approval_status():
    """Backfill approval_status='approved' for pre-existing rows so legacy demo data works."""
    db = get_db()
    prop_res = await db["properties"].update_many(
        {"approval_status": {"$exists": False}},
        {"$set": {"approval_status": "approved"}},
    )
    # Backfill Phase 1 fields
    await db["properties"].update_many(
        {"featured": {"$exists": False}},
        {"$set": {"featured": False}},
    )
    # Phase 5: simplified category taxonomy migration
    legacy_map = {
        "bedsitter": ("apartment", "bedsitter"),
        "single_room": ("apartment", "single_room"),
        "self_contained": ("apartment", "1br"),
        "standalone": ("own_compound", None),
        "compound": ("own_compound", None),
        "airbnb": ("apartment", "1br"),
    }
    for legacy, (new_cat, new_sub) in legacy_map.items():
        await db["properties"].update_many(
            {"category": legacy},
            {"$set": {"category": new_cat, "sub_type": new_sub}},
        )
    await db["properties"].update_many(
        {"category": {"$exists": False}},
        {"$set": {"category": "apartment", "sub_type": None}},
    )
    await db["properties"].update_many(
        {"sub_type": {"$exists": False}},
        {"$set": {"sub_type": None}},
    )
    # Phase 5: rental/lease tenancy_types
    await db["properties"].update_many(
        {"tenancy_types": {"$exists": False}},
        {"$set": {"tenancy_types": ["rental"]}},
    )
    # Phase 5: tenant tenancy_type default
    await db["users"].update_many(
        {"role": "tenant", "tenancy_type": {"$exists": False}},
        {"$set": {"tenancy_type": "rental"}},
    )
    # Phase 5: lease agreement_type default
    await db["leases"].update_many(
        {"agreement_type": {"$exists": False}},
        {"$set": {"agreement_type": "lease"}},
    )
    user_res = await db["users"].update_many(
        {"role": {"$in": ["tenant", "caretaker", "security"]}, "approval_status": {"$exists": False}},
        {"$set": {"approval_status": "approved"}},
    )
    if prop_res.modified_count or user_res.modified_count:
        logger.info(
            "Migrated approval_status on %d properties and %d users",
            prop_res.modified_count,
            user_res.modified_count,
        )


async def _seed_admin():
    """Idempotently ensure a super-admin user exists from env vars."""
    from auth import hash_password
    from models import new_id, now_iso

    admin_email = os.environ.get("ADMIN_EMAIL", "").lower().strip()
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    if not admin_email or not admin_password:
        logger.info("ADMIN_EMAIL / ADMIN_PASSWORD not set — skipping admin seed.")
        return
    db = get_db()
    existing = await db["users"].find_one({"email": admin_email})
    if existing:
        if existing.get("role") != "admin":
            logger.warning(
                "User %s exists with role=%s, not promoting automatically.",
                admin_email,
                existing.get("role"),
            )
        return
    await db["users"].insert_one({
        "id": new_id(),
        "email": admin_email,
        "full_name": os.environ.get("ADMIN_FULL_NAME", "Platform Admin"),
        "phone": os.environ.get("ADMIN_PHONE", "254700000000"),
        "role": "admin",
        "password_hash": hash_password(admin_password),
        "landlord_id": None,
        "unit_id": None,
        "created_at": now_iso(),
    })
    logger.info("Seeded admin user: %s", admin_email)


app = FastAPI(title="Nairobi Rental Management", lifespan=lifespan)
# Mount under /api/uploads so the K8s ingress (which only routes /api/* to backend)
# correctly serves uploaded property images via the public REACT_APP_BACKEND_URL.
# Kept the legacy /uploads mount for any internal/dev usage.
app.mount("/api/uploads", StaticFiles(directory="uploads"), name="api_uploads")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"message": "Nairobi Rental Management API", "status": "ok"}


@api_router.get("/dashboard/stats")
async def dashboard_stats(user: dict = Depends(get_current_user)):
    db = get_db()
    if user["role"] == "admin":
        from routers.admin_router import platform_stats
        return await platform_stats(user)
    if user["role"] == "landlord":
        properties = await db["properties"].count_documents({"landlord_id": user["id"]})
        units = await db["units"].count_documents({"landlord_id": user["id"]})
        occupied = await db["units"].count_documents(
            {"landlord_id": user["id"], "occupied": True}
        )
        tenants = await db["users"].count_documents(
            {"landlord_id": user["id"], "role": "tenant"}
        )
        # outstanding arrears
        pipeline = [
            {"$match": {"landlord_id": user["id"], "status": {"$in": ["pending", "partial", "overdue"]}}},
            {"$group": {"_id": None, "total": {"$sum": {"$subtract": ["$amount", "$amount_paid"]}}}},
        ]
        agg = await db["bills"].aggregate(pipeline).to_list(1)
        arrears = agg[0]["total"] if agg else 0
        # this month collection
        from datetime import datetime, timezone
        period = datetime.now(timezone.utc).strftime("%Y-%m")
        coll_pipe = [
            {"$match": {"landlord_id": user["id"], "status": "succeeded"}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
        ]
        coll = await db["payments"].aggregate(coll_pipe).to_list(1)
        total_collected = coll[0]["total"] if coll else 0
        open_issues = await db["issues"].count_documents(
            {"landlord_id": user["id"], "status": {"$in": ["open", "in_progress"]}}
        )
        return {
            "properties": properties,
            "units": units,
            "occupied_units": occupied,
            "vacant_units": units - occupied,
            "tenants": tenants,
            "arrears": arrears,
            "total_collected": total_collected,
            "open_issues": open_issues,
            "period": period,
        }
    elif user["role"] == "tenant":
        pipeline = [
            {"$match": {"tenant_id": user["id"], "status": {"$in": ["pending", "partial", "overdue"]}}},
            {"$group": {"_id": None, "total": {"$sum": {"$subtract": ["$amount", "$amount_paid"]}}}},
        ]
        agg = await db["bills"].aggregate(pipeline).to_list(1)
        arrears = agg[0]["total"] if agg else 0
        pending_bills = await db["bills"].count_documents(
            {"tenant_id": user["id"], "status": {"$in": ["pending", "partial", "overdue"]}}
        )
        open_issues = await db["issues"].count_documents(
            {"tenant_id": user["id"], "status": {"$in": ["open", "in_progress"]}}
        )
        paid_bills = await db["bills"].count_documents(
            {"tenant_id": user["id"], "status": "paid"}
        )
        return {
            "arrears": arrears,
            "pending_bills": pending_bills,
            "open_issues": open_issues,
            "paid_bills": paid_bills,
        }
    else:  # caretaker or prospect
        if user["role"] == "prospect":
            total = await db["viewings"].count_documents({"prospect_id": user["id"]})
            scheduled = await db["viewings"].count_documents(
                {"prospect_id": user["id"], "status": "scheduled"}
            )
            pending = await db["viewings"].count_documents(
                {"prospect_id": user["id"], "status": "pending_payment"}
            )
            completed = await db["viewings"].count_documents(
                {"prospect_id": user["id"], "status": "completed"}
            )
            return {
                "total_viewings": total,
                "scheduled": scheduled,
                "pending": pending,
                "completed": completed,
            }
        assigned = await db["issues"].count_documents(
            {"assigned_to": user["id"], "status": {"$in": ["open", "in_progress"]}}
        )
        resolved = await db["issues"].count_documents(
            {"assigned_to": user["id"], "status": "resolved"}
        )
        unassigned = await db["issues"].count_documents(
            {"landlord_id": user.get("landlord_id"), "assigned_to": None, "status": "open"}
        )
        return {
            "assigned_open": assigned,
            "resolved": resolved,
            "unassigned_open": unassigned,
        }


api_router.include_router(auth_router)
api_router.include_router(properties_router)
api_router.include_router(users_router)
api_router.include_router(bills_router)
api_router.include_router(payments_router)
api_router.include_router(issues_router)
api_router.include_router(viewings_router)
api_router.include_router(admin_router)
api_router.include_router(oversight_router)
api_router.include_router(community_router)
api_router.include_router(notifications_router)
api_router.include_router(yardsale_router)
api_router.include_router(leases_router)
api_router.include_router(visitors_router)
api_router.include_router(ai_router)

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
