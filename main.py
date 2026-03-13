import io
import logging
import os
import uuid

import qrcode
from fastapi import Depends, File, FastAPI, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import random

from auth import create_access_token, decode_token, hash_password, verify_password
from database import (
    create_profile as db_create_profile,
    create_user as db_create_user,
    get_contact as db_get_contact,
    get_profile_by_slug,
    get_profile_by_user_id,
    get_user_by_email,
    get_user_by_id,
    save_contact as db_save_contact,
    seed_contacts,
    update_profile as db_update_profile,
    update_profile_picture,
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

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

# Create uploads directory if it doesn't exist
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Serve uploaded files (must be before routes that might conflict)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

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


@app.post("/api/profile/picture")
async def upload_profile_picture(
    file: UploadFile = File(...),
    user: tuple[int, str] = Depends(get_current_user),
):
    """
    Upload profile picture. Requires valid JWT and existing profile.
    Accepts: jpg, jpeg, png, webp. Max 5 MB.
    """
    user_id, _ = user
    profile = get_profile_by_user_id(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Create one first.")

    # Validate file extension
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read and validate file size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max 5 MB.")

    # Save file: user_id_timestamp.ext (e.g. 1_1709820000.jpg)
    filename = f"{user_id}_{uuid.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(content)

    # Store URL path in database (e.g. /uploads/1_abc123.jpg)
    url_path = f"/uploads/{filename}"
    update_profile_picture(user_id, url_path)

    return {"profile_picture_url": url_path}


# --- Public card (no auth - for QR scan) ---

@app.get("/api/card/{slug}")
def get_public_card(slug: str):
    """
    Get business card by slug. No auth required.
    Used when someone scans the QR code - returns full profile for display/save.
    """
    profile = get_profile_by_slug(slug)
    if not profile:
        raise HTTPException(status_code=404, detail="Card not found")
    return profile


@app.get("/api/card/{slug}/vcard")
def get_vcard(slug: str):
    """
    Download vCard (.vcf) for business card. No auth required.
    Scan QR → open card page → tap 'Save to contacts' → this endpoint.
    """
    profile = get_profile_by_slug(slug)
    if not profile:
        raise HTTPException(status_code=404, detail="Card not found")

    def vcard_escape(s: str | None) -> str:
        if not s:
            return ""
        return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    full_name = profile.get("full_name") or "Contact"
    parts = full_name.strip().split(maxsplit=1)
    given = parts[0] if parts else ""
    family = parts[1] if len(parts) > 1 else ""

    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"FN:{vcard_escape(full_name)}",
        f"N:{vcard_escape(family)};{vcard_escape(given)};;;",
    ]
    if profile.get("phone"):
        lines.append(f"TEL;TYPE=CELL:{vcard_escape(profile['phone'])}")
    if profile.get("email"):
        lines.append(f"EMAIL:{vcard_escape(profile['email'])}")
    if profile.get("company_name"):
        lines.append(f"ORG:{vcard_escape(profile['company_name'])}")
    if profile.get("job_title"):
        lines.append(f"TITLE:{vcard_escape(profile['job_title'])}")
    if profile.get("website"):
        lines.append(f"URL:{vcard_escape(profile['website'])}")
    if profile.get("address"):
        lines.append(f"ADR;TYPE=WORK:;;{vcard_escape(profile['address'])};;;;")
    if profile.get("bio"):
        lines.append(f"NOTE:{vcard_escape(profile['bio'])}")
    lines.append("END:VCARD")

    vcard_content = "\r\n".join(lines)
    filename = f"{full_name.replace(' ', '_')}.vcf" if full_name else "contact.vcf"
    return Response(
        content=vcard_content,
        media_type="text/vcard",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/qr")
def get_qr_code(user: tuple[int, str] = Depends(get_current_user)):
    """
    Generate QR code image for current user's business card.
    QR encodes: {BASE_URL}/api/card/{slug}
    Returns PNG image. Requires valid JWT and existing profile.
    """
    user_id, _ = user
    profile = get_profile_by_user_id(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Create one first.")
    slug = profile["slug"]
    card_url = f"{BASE_URL.rstrip('/')}/api/card/{slug}"
    img = qrcode.make(card_url)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return Response(content=buffer.getvalue(), media_type="image/png")


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
