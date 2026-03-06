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
    """Get a database connection. Creates contacts table if it doesn't exist."""
    conn = connect(get_connection_string())
    try:
        cursor = conn.cursor()
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
