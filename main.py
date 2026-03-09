import logging
import uuid

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

import random

from auth import create_access_token, decode_token, hash_password, verify_password
from database import (
    create_profile as db_create_profile,
    create_user as db_create_user,
    get_contact as db_get_contact,
    get_profile_by_user_id,
    get_user_by_email,
    get_user_by_id,
    save_contact as db_save_contact,
    seed_contacts,
    update_profile as db_update_profile,
    update_user_password,
)
from models import ChangePassword, ProfileCreate, ProfileUpdate, UserLogin, UserRegister

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> tuple[int, str]:
    """
    Dependency that validates JWT and returns (user_id, email).
    Use Depends(get_current_user) on any route that requires login.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid token")
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return (user_id, user[1])  # (id, email)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Business Card API")

# Allow frontend (Next.js on port 3000) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ContactInput(BaseModel):
    name: str = ""
    phone: str = ""


# --- Auth routes ---

@app.post("/api/auth/register")
def register(data: UserRegister):
    """Register a new user. Email must be unique."""
    user = get_user_by_email(data.email)
    if user:
        raise HTTPException(status_code=400, detail="Email already registered")
    password_hash = hash_password(data.password)
    db_create_user(data.email, password_hash)
    return {"message": "Registered successfully"}


@app.post("/api/auth/login")
def login(data: UserLogin):
    """Login with email and password. Returns JWT access token."""
    user = get_user_by_email(data.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    user_id, email, password_hash = user
    if not verify_password(data.password, password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token({"sub": str(user_id)})
    return {"access_token": token, "token_type": "bearer"}


@app.post("/api/auth/change-password")
def change_password(data: ChangePassword, user: tuple[int, str] = Depends(get_current_user)):
    """Change password. Requires valid JWT."""
    user_id, _ = user
    db_user = get_user_by_id(user_id)
    if not db_user:
        raise HTTPException(status_code=401, detail="User not found")
    _, _, password_hash = db_user
    if not verify_password(data.current_password, password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    new_hash = hash_password(data.new_password)
    update_user_password(user_id, new_hash)
    return {"message": "Password updated successfully"}


# --- Profile routes ---

@app.get("/api/profile")
def get_profile(user: tuple[int, str] = Depends(get_current_user)):
    """Get current user's profile. Requires valid JWT."""
    user_id, _ = user
    profile = get_profile_by_user_id(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Create one first.")
    return profile


@app.post("/api/profile")
def create_profile(data: ProfileCreate, user: tuple[int, str] = Depends(get_current_user)):
    """Create a new profile for the current user. Requires valid JWT."""
    user_id, _ = user
    existing = get_profile_by_user_id(user_id)
    if existing:
        raise HTTPException(status_code=400, detail="Profile already exists. Use PUT to update.")
    slug = uuid.uuid4().hex[:12]
    db_create_profile(
        user_id=user_id,
        slug=slug,
        full_name=data.full_name,
        email=data.email,
        phone=data.phone,
        company_name=data.company_name,
        job_title=data.job_title,
        bio=data.bio,
        website=data.website,
        linkedin=data.linkedin,
        address=data.address,
    )
    profile = get_profile_by_user_id(user_id)
    return profile


@app.put("/api/profile")
def update_profile(data: ProfileUpdate, user: tuple[int, str] = Depends(get_current_user)):
    """Update current user's profile. Requires valid JWT."""
    user_id, _ = user
    existing = get_profile_by_user_id(user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Profile not found. Create one first.")
    fields = data.model_dump(exclude_unset=True)
    db_update_profile(user_id, **fields)
    profile = get_profile_by_user_id(user_id)
    return profile


# --- Legacy contact routes ---

@app.get("/api/contact")
def get_contact():
    """Returns stored name and phone from Azure SQL database."""
    try:
        name, phone = db_get_contact()
        return {"name": name, "phone": phone}
    except Exception as e:
        logger.exception("GET /api/contact failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/contact")
def save_contact(data: ContactInput):
    """Receives name and phone from frontend, stores in Azure SQL, and returns them."""
    try:
        name, phone = db_save_contact(data.name, data.phone)
        return {"name": name, "phone": phone}
    except Exception as e:
        logger.exception("POST /api/contact failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/seed")
def seed_random_contacts():
    """Seed 20 random contact records."""
    first_names = [
        "James", "Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia", "Mason", "Isabella",
        "William", "Mia", "Alexander", "Charlotte", "Elijah", "Amelia", "Benjamin", "Harper", "Lucas", "Evelyn",
    ]
    last_names = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
        "Wilson", "Anderson", "Taylor", "Thomas", "Moore", "Jackson", "Martin", "Lee", "Thompson", "White",
    ]
    contacts = [
        (f"{random.choice(first_names)} {random.choice(last_names)}", f"{random.randint(200, 999)}{random.randint(200, 999)}{random.randint(1000, 9999)}")
        for _ in range(20)
    ]
    try:
        count = seed_contacts(contacts)
        return {"status": "ok", "inserted": count, "contacts": [{"name": n, "phone": p} for n, p in contacts]}
    except Exception as e:
        logger.exception("Seed failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
