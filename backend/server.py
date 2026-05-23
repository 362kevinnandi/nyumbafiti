"""Nairobi Rental Management - Main FastAPI app."""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import APIRouter, Depends, FastAPI  # noqa: E402
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("rental-mgmt")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_indexes()
    logger.info("Indexes ensured. App ready.")
    yield
    get_client().close()


app = FastAPI(title="Nairobi Rental Management", lifespan=lifespan)

api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"message": "Nairobi Rental Management API", "status": "ok"}


@api_router.get("/dashboard/stats")
async def dashboard_stats(user: dict = Depends(get_current_user)):
    db = get_db()
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

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
