"""Auth routes - register, login, me."""
from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from auth import create_token, get_current_user, hash_password, verify_password
from db import get_db
from models import LoginRequest, TokenResponse, UserPublic, UserRegister, new_id, now_iso

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(payload: UserRegister):
    if payload.role == "tenant":
        raise HTTPException(
            status_code=400,
            detail="Tenants are created by landlords. Please register as landlord or contact your landlord.",
        )
    if payload.role == "caretaker":
        raise HTTPException(
            status_code=400,
            detail="Caretakers are added by landlords. Please register as landlord or contact your landlord.",
        )
    if payload.role == "prospect":
        raise HTTPException(
            status_code=400,
            detail="Prospect accounts are created automatically when you book a viewing on the marketplace.",
        )
    if payload.role == "admin":
        raise HTTPException(
            status_code=400,
            detail="Admin accounts cannot be self-registered.",
        )

    db = get_db()
    user_doc = {
        "id": new_id(),
        "email": payload.email.lower(),
        "full_name": payload.full_name,
        "phone": payload.phone,
        "role": payload.role,
        "password_hash": hash_password(payload.password),
        "landlord_id": None,
        "unit_id": None,
        "created_at": now_iso(),
    }
    try:
        await db["users"].insert_one(user_doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Email already registered")

    token = create_token(user_doc["id"], user_doc["role"])
    user_doc.pop("password_hash", None)
    user_doc.pop("_id", None)
    return TokenResponse(access_token=token, user=UserPublic(**user_doc))


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    db = get_db()
    user = await db["users"].find_one({"email": payload.email.lower()})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.get("suspended"):
        raise HTTPException(
            status_code=403,
            detail="Account suspended. Contact platform administrator.",
        )
    token = create_token(user["id"], user["role"])
    user.pop("password_hash", None)
    user.pop("_id", None)
    return TokenResponse(access_token=token, user=UserPublic(**user))


@router.get("/me", response_model=UserPublic)
async def me(user: dict = Depends(get_current_user)):
    return UserPublic(**user)
