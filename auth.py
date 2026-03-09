"""JWT and password utilities for authentication."""

import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from jose import JWTError, jwt
from passlib.hash import bcrypt

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))
JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Hash a plain password using bcrypt."""
    return bcrypt.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    return bcrypt.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    """Create a JWT access token. Include 'sub' (subject) as user_id string."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Decode and verify a JWT. Returns payload dict or None if invalid."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None
