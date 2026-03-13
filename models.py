"""Pydantic models for request/response validation."""

from pydantic import BaseModel, EmailStr


# --- Auth ---

class UserRegister(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class ChangePassword(BaseModel):
    current_password: str
    new_password: str


# --- Profile ---

class ProfileCreate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    company_name: str | None = None
    job_title: str | None = None
    bio: str | None = None
    website: str | None = None
    linkedin: str | None = None
    address: str | None = None


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    company_name: str | None = None
    job_title: str | None = None
    bio: str | None = None
    website: str | None = None
    linkedin: str | None = None
    address: str | None = None


class ProfileResponse(BaseModel):
    id: int
    user_id: int
    slug: str
    full_name: str | None
    email: str | None
    phone: str | None
    company_name: str | None
    job_title: str | None
    bio: str | None
    profile_picture_url: str | None
    website: str | None
    linkedin: str | None
    address: str | None
    created_at: object
    updated_at: object
