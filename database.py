"""Azure SQL Database connection and operations for contacts."""

import os
from contextlib import contextmanager

from dotenv import load_dotenv
from mssql_python import connect

load_dotenv()

# Azure SQL connection - configure via environment variables
DB_SERVER = os.getenv("DB_SERVER", "")  # e.g. myserver.database.windows.net
DB_NAME = os.getenv("DB_NAME", "")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")


def get_connection_string() -> str:
    """Build Azure SQL connection string for mssql-python (SQL authentication).
    Matches Azure sample: server, port 1433, user id, password, database.
    """
    if not DB_SERVER:
        raise ValueError(
            "DB_SERVER is not set. Create a .env file with DB_SERVER=your-server.database.windows.net"
        )
    port = os.getenv("DB_PORT", "1433")
    server_with_port = f"{DB_SERVER},{port}" if port else DB_SERVER
    return (
        f"Server={server_with_port};"
        f"Database={DB_NAME};"
        f"UID={DB_USER};"
        f"PWD={DB_PASSWORD};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
    )


@contextmanager
def get_connection():
    """Get a database connection. Creates users and profiles tables if they don't exist."""
    conn = connect(get_connection_string())
    try:
        cursor = conn.cursor()

        # Users table - for registration and login
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'users')
            CREATE TABLE dbo.users (
                id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                email NVARCHAR(255) NOT NULL,
                password_hash NVARCHAR(255) NOT NULL,
                created_at DATETIME2 NOT NULL DEFAULT GETDATE(),
                updated_at DATETIME2 NOT NULL DEFAULT GETDATE(),
                CONSTRAINT UQ_users_email UNIQUE (email)
            );
        """)

        # Profiles table - business card data linked to user
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'profiles')
            CREATE TABLE dbo.profiles (
                id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                user_id INT NOT NULL,
                slug NVARCHAR(50) NOT NULL,
                full_name NVARCHAR(255) NULL,
                email NVARCHAR(255) NULL,
                phone NVARCHAR(50) NULL,
                company_name NVARCHAR(255) NULL,
                job_title NVARCHAR(255) NULL,
                bio NVARCHAR(500) NULL,
                profile_picture_url NVARCHAR(500) NULL,
                website NVARCHAR(255) NULL,
                linkedin NVARCHAR(255) NULL,
                address NVARCHAR(500) NULL,
                created_at DATETIME2 NOT NULL DEFAULT GETDATE(),
                updated_at DATETIME2 NOT NULL DEFAULT GETDATE(),
                CONSTRAINT FK_profiles_user FOREIGN KEY (user_id) REFERENCES dbo.users(id) ON DELETE CASCADE,
                CONSTRAINT UQ_profiles_slug UNIQUE (slug)
            );
        """)

        # Legacy contacts table - kept for backward compatibility
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'business_card_contacts')
            CREATE TABLE dbo.business_card_contacts (
                id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                name NVARCHAR(255) NOT NULL DEFAULT '',
                phone NVARCHAR(50) NOT NULL DEFAULT ''
            );
        """)
        conn.commit()
        yield conn
    finally:
        conn.close()


# --- Users ---

def create_user(email: str, password_hash: str) -> int:
    """Insert a new user. Returns user id."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO dbo.users (email, password_hash) VALUES (?, ?)",
            (email, password_hash),
        )
        conn.commit()
        cursor.execute("SELECT @@IDENTITY")
        row = cursor.fetchone()
        return int(row[0]) if row else 0


def get_user_by_email(email: str) -> tuple | None:
    """Get user by email. Returns (id, email, password_hash) or None."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, email, password_hash FROM dbo.users WHERE email = ?",
            (email,),
        )
        return cursor.fetchone()


def get_user_by_id(user_id: int) -> tuple | None:
    """Get user by id. Returns (id, email, password_hash) or None."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, email, password_hash FROM dbo.users WHERE id = ?",
            (user_id,),
        )
        return cursor.fetchone()


def update_user_password(user_id: int, password_hash: str) -> None:
    """Update user password."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE dbo.users SET password_hash = ?, updated_at = GETDATE() WHERE id = ?",
            (password_hash, user_id),
        )
        conn.commit()


# --- Profiles ---

def create_profile(
    user_id: int,
    slug: str,
    full_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    company_name: str | None = None,
    job_title: str | None = None,
    bio: str | None = None,
    website: str | None = None,
    linkedin: str | None = None,
    address: str | None = None,
) -> int:
    """Insert a new profile. Returns profile id."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO dbo.profiles
            (user_id, slug, full_name, email, phone, company_name, job_title, bio, website, linkedin, address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                slug,
                full_name or None,
                email or None,
                phone or None,
                company_name or None,
                job_title or None,
                bio or None,
                website or None,
                linkedin or None,
                address or None,
            ),
        )
        conn.commit()
        cursor.execute("SELECT @@IDENTITY")
        row = cursor.fetchone()
        return int(row[0]) if row else 0


def get_profile_by_user_id(user_id: int) -> dict | None:
    """Get profile by user_id. Returns dict or None."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, slug, full_name, email, phone, company_name, job_title,
                   bio, profile_picture_url, website, linkedin, address, created_at, updated_at
            FROM dbo.profiles WHERE user_id = ?
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "user_id": row[1],
            "slug": row[2],
            "full_name": row[3],
            "email": row[4],
            "phone": row[5],
            "company_name": row[6],
            "job_title": row[7],
            "bio": row[8],
            "profile_picture_url": row[9],
            "website": row[10],
            "linkedin": row[11],
            "address": row[12],
            "created_at": row[13],
            "updated_at": row[14],
        }


def get_profile_by_slug(slug: str) -> dict | None:
    """Get profile by slug (for public card view). Returns dict or None."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, slug, full_name, email, phone, company_name, job_title,
                   bio, profile_picture_url, website, linkedin, address, created_at, updated_at
            FROM dbo.profiles WHERE slug = ?
            """,
            (slug,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "user_id": row[1],
            "slug": row[2],
            "full_name": row[3],
            "email": row[4],
            "phone": row[5],
            "company_name": row[6],
            "job_title": row[7],
            "bio": row[8],
            "profile_picture_url": row[9],
            "website": row[10],
            "linkedin": row[11],
            "address": row[12],
            "created_at": row[13],
            "updated_at": row[14],
        }


def update_profile(user_id: int, **fields: str | None) -> None:
    """Update profile fields for given user_id. Pass only fields to update."""
    if not fields:
        return
    allowed = {
        "full_name", "email", "phone", "company_name", "job_title",
        "bio", "website", "linkedin", "address",
    }
    updates = []
    values = []
    for k, v in fields.items():
        if k in allowed:
            updates.append(f"{k} = ?")
            values.append(v)
    if not updates:
        return
    updates.append("updated_at = GETDATE()")
    values.append(user_id)
    sql = f"UPDATE dbo.profiles SET {', '.join(updates)} WHERE user_id = ?"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, values)
        conn.commit()


def update_profile_picture(user_id: int, profile_picture_url: str) -> None:
    """Update profile picture URL for user."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE dbo.profiles SET profile_picture_url = ?, updated_at = GETDATE() WHERE user_id = ?",
            (profile_picture_url, user_id),
        )
        conn.commit()


# --- Legacy contacts (kept for backward compatibility) ---

def get_contact() -> tuple[str, str]:
    """Get the most recent contact (name, phone). Returns empty strings if no row."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT TOP 1 name, phone FROM dbo.business_card_contacts ORDER BY id DESC")
        row = cursor.fetchone()
        if row:
            return (row[0] or "", row[1] or "")
        return ("", "")


def save_contact(name: str, phone: str) -> tuple[str, str]:
    """Insert a new contact and return (name, phone)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO dbo.business_card_contacts (name, phone) VALUES (?, ?)", (name, phone))
        conn.commit()
    return (name, phone)


def seed_contacts(contacts: list[tuple[str, str]]) -> int:
    """Recreate table and insert multiple contacts. Returns count inserted."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS dbo.business_card_contacts")
        cursor.execute("""
            CREATE TABLE dbo.business_card_contacts (
                id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                name NVARCHAR(255) NOT NULL DEFAULT '',
                phone NVARCHAR(50) NOT NULL DEFAULT ''
            );
        """)
        for name, phone in contacts:
            cursor.execute("INSERT INTO dbo.business_card_contacts (name, phone) VALUES (?, ?)", (name, phone))
        conn.commit()
    return len(contacts)
