import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import random

from database import get_contact as db_get_contact, save_contact as db_save_contact, seed_contacts

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
