"""Pydantic models for the Nairobi Rental Management System."""
from datetime import datetime, timezone
from typing import Literal, Optional, List
from pydantic import BaseModel, Field, EmailStr, ConfigDict
import uuid


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


Role = Literal["landlord", "tenant", "caretaker", "prospect", "admin"]
BillType = Literal["rent", "water", "electricity", "service", "other"]
BillStatus = Literal["pending", "partial", "paid", "overdue"]
PaymentStatus = Literal["pending", "succeeded", "failed", "cancelled", "refunded"]
IssueStatus = Literal["open", "in_progress", "resolved", "closed"]
IssuePriority = Literal["low", "medium", "high", "urgent"]
ViewingStatus = Literal["pending_payment", "scheduled", "completed", "cancelled"]
PayoutStatus = Literal["pending", "paid"]
ApprovalStatus = Literal["pending", "approved", "rejected"]
PropertyCategory = Literal[
    "apartment", "bedsitter", "single_room", "self_contained",
    "standalone", "compound", "airbnb",
]
PROPERTY_CATEGORIES = (
    "apartment", "bedsitter", "single_room", "self_contained",
    "standalone", "compound", "airbnb",
)
VIEWING_FEE_KES = 200
DEFAULT_COMMISSION_RATE = 0.035  # 3.5%


# ============ USER ============
class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    phone: str
    role: Role


class UserRegister(UserBase):
    password: str = Field(min_length=6)


class UserPublic(UserBase):
    id: str
    landlord_id: Optional[str] = None
    unit_id: Optional[str] = None
    approval_status: Optional[ApprovalStatus] = None
    suspended: Optional[bool] = False
    created_at: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


# ============ PROPERTY ============
class PropertyCreate(BaseModel):
    name: str
    address: str
    description: Optional[str] = ""
    category: Optional[PropertyCategory] = "apartment"


class PropertyUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    category: Optional[PropertyCategory] = None
    featured: Optional[bool] = None


class Property(BaseModel):
    id: str
    landlord_id: str
    name: str
    address: str
    description: Optional[str] = ""
    category: PropertyCategory = "apartment"
    featured: bool = False
    images: List[str] = []
    units_count: int = 0
    approval_status: ApprovalStatus = "pending"
    rejection_reason: Optional[str] = ""
    created_at: str
# ============ UNIT ============
class UnitCreate(BaseModel):
    property_id: str
    unit_number: str
    rent_amount: float
    bedrooms: int = 1
    description: Optional[str] = ""


class Unit(UnitCreate):
    id: str
    landlord_id: str
    tenant_id: Optional[str] = None
    occupied: bool = False
    created_at: str


# ============ TENANT ASSIGNMENT ============
class TenantCreate(BaseModel):
    email: EmailStr
    full_name: str
    phone: str
    password: str = Field(min_length=6)
    unit_id: str


class CaretakerCreate(BaseModel):
    email: EmailStr
    full_name: str
    phone: str
    password: str = Field(min_length=6)


# ============ BILL ============
class BillCreate(BaseModel):
    tenant_id: str
    unit_id: str
    bill_type: BillType
    amount: float
    period: str  # YYYY-MM
    due_date: str  # ISO date
    description: Optional[str] = ""


class Bill(BaseModel):
    id: str
    landlord_id: str
    property_id: str
    unit_id: str
    tenant_id: str
    bill_type: BillType
    amount: float
    amount_paid: float = 0
    period: str
    due_date: str
    status: BillStatus = "pending"
    description: str = ""
    created_at: str


# ============ PAYMENT ============
class PaymentInitiate(BaseModel):
    bill_id: str
    phone_number: str  # 2547XXXXXXXX
    amount: Optional[float] = None  # optional override (partial)


class Payment(BaseModel):
    id: str
    bill_id: Optional[str] = None
    viewing_id: Optional[str] = None
    tenant_id: Optional[str] = None
    prospect_id: Optional[str] = None
    landlord_id: str
    amount: float
    phone_number: str
    status: PaymentStatus = "pending"
    checkout_request_id: Optional[str] = None
    merchant_request_id: Optional[str] = None
    mpesa_receipt: Optional[str] = None
    result_desc: Optional[str] = None
    idempotency_key: Optional[str] = None
    purpose: Optional[str] = None
    commission_rate: Optional[float] = None
    commission_amount: Optional[float] = None
    net_to_landlord: Optional[float] = None
    refund_reason: Optional[str] = None
    refunded_at: Optional[str] = None
    created_at: str
    updated_at: str


# ============ ISSUE ============
class IssueCreate(BaseModel):
    title: str
    description: str
    priority: IssuePriority = "medium"


class IssueUpdate(BaseModel):
    status: Optional[IssueStatus] = None
    assigned_to: Optional[str] = None
    priority: Optional[IssuePriority] = None


class IssueMessage(BaseModel):
    id: str
    issue_id: str
    author_id: str
    author_name: str
    author_role: Role
    body: str
    created_at: str


class IssueMessageCreate(BaseModel):
    body: str


class Issue(BaseModel):
    id: str
    landlord_id: str
    tenant_id: str
    unit_id: str
    property_id: str
    title: str
    description: str
    priority: IssuePriority = "medium"
    status: IssueStatus = "open"
    assigned_to: Optional[str] = None  # caretaker id
    created_at: str
    updated_at: str


# ============ VIEWING ============
class ViewingCreate(BaseModel):
    unit_id: str
    prospect_name: str
    prospect_email: EmailStr
    prospect_phone: str
    scheduled_date: str  # ISO date YYYY-MM-DD
    scheduled_time: str  # HH:MM
    notes: Optional[str] = ""


class Viewing(BaseModel):
    id: str
    unit_id: str
    property_id: str
    landlord_id: str
    prospect_id: str
    prospect_name: str
    prospect_email: str
    prospect_phone: str
    scheduled_date: str
    scheduled_time: str
    notes: str = ""
    status: ViewingStatus = "pending_payment"
    viewing_fee: float = VIEWING_FEE_KES
    payment_id: Optional[str] = None
    created_at: str
    updated_at: str


# ============ PHASE 2: COMMUNITY HUB ============
AnnouncementScope = Literal["global", "property"]


class AnnouncementCreate(BaseModel):
    scope: AnnouncementScope
    property_id: Optional[str] = None  # required when scope=property
    title: str
    body: str
    pinned: bool = False


class Announcement(BaseModel):
    id: str
    scope: AnnouncementScope
    property_id: Optional[str] = None
    landlord_id: Optional[str] = None
    author_id: str
    author_name: str
    author_role: Role
    title: str
    body: str
    attachments: List[str] = []
    pinned: bool = False
    created_at: str
    updated_at: str


class ForumThreadCreate(BaseModel):
    property_id: str
    title: str
    body: str


class ForumThread(BaseModel):
    id: str
    property_id: str
    landlord_id: str
    author_id: str
    author_name: str
    author_role: Role
    title: str
    body: str
    attachments: List[str] = []
    pinned: bool = False
    locked: bool = False
    replies_count: int = 0
    last_reply_at: Optional[str] = None
    created_at: str
    updated_at: str


class ForumReplyCreate(BaseModel):
    body: str


class ForumReply(BaseModel):
    id: str
    thread_id: str
    author_id: str
    author_name: str
    author_role: Role
    body: str
    attachments: List[str] = []
    created_at: str


# ============ PHASE 3: YARD SALE MARKETPLACE ============
YardSaleStatus = Literal["active", "sold", "removed"]
YardSaleCategory = Literal[
    "electronics", "furniture", "appliances", "clothing",
    "books", "kitchen", "sports", "other",
]
YARD_SALE_CATEGORIES = (
    "electronics", "furniture", "appliances", "clothing",
    "books", "kitchen", "sports", "other",
)
YARD_SALE_FEATURE_FEE_KES = 100
YARD_SALE_FEATURE_DAYS = 7


class YardSaleListing(BaseModel):
    id: str
    seller_id: str  # tenant user id
    seller_name: str
    seller_phone: str
    landlord_id: Optional[str] = None
    property_id: Optional[str] = None
    title: str
    description: str
    price: float
    category: YardSaleCategory = "other"
    images: List[str] = []
    featured: bool = False
    featured_until: Optional[str] = None
    status: YardSaleStatus = "active"
    created_at: str
    updated_at: str


class YardSaleUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category: Optional[YardSaleCategory] = None
    status: Optional[YardSaleStatus] = None


# ============ PHASE 4: LEASES ============
LeaseStatus = Literal["draft", "sent", "signed", "cancelled"]


class LeaseCreate(BaseModel):
    tenant_id: str
    unit_id: str
    rent_amount: float
    deposit_amount: float = 0
    start_date: str  # YYYY-MM-DD
    end_date: str
    terms: str = ""


class Lease(BaseModel):
    id: str
    landlord_id: str
    tenant_id: str
    tenant_name: str
    unit_id: str
    property_id: str
    rent_amount: float
    deposit_amount: float
    start_date: str
    end_date: str
    terms: str
    pdf_path: Optional[str] = None
    status: LeaseStatus = "draft"
    signed_at: Optional[str] = None
    signed_ip: Optional[str] = None
    created_at: str
    updated_at: str


# ============ PHASE 4: VISITOR PASSES (QR) ============
VisitorPassStatus = Literal["active", "used", "expired", "cancelled"]


class VisitorPassCreate(BaseModel):
    visitor_name: str
    visitor_phone: Optional[str] = ""
    expected_time: str  # ISO datetime
    notes: Optional[str] = ""


class VisitorPass(BaseModel):
    id: str
    token: str  # unique QR code token
    tenant_id: str
    tenant_name: str
    landlord_id: str
    property_id: str
    unit_id: str
    visitor_name: str
    visitor_phone: str
    expected_time: str
    notes: str = ""
    status: VisitorPassStatus = "active"
    used_at: Optional[str] = None
    used_by_caretaker_id: Optional[str] = None
    used_by_caretaker_name: Optional[str] = None
    expires_at: str
    created_at: str


# ============ PHASE 4: NOTIFICATIONS ============
NotificationKind = Literal[
    "bill_due", "announcement", "issue_update", "forum_reply",
    "lease_pending", "lease_signed", "visitor_arrived", "payment_succeeded",
    "yard_sale_featured", "system",
]


class Notification(BaseModel):
    id: str
    user_id: str
    kind: NotificationKind
    title: str
    body: str
    link: Optional[str] = None
    read: bool = False
    created_at: str
