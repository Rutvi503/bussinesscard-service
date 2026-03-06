from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Business Card API")

# Allow frontend (Next.js on port 3000) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store for name and phone
stored_name: str = ""
stored_phone: str = ""


class ContactInput(BaseModel):
    name: str = ""
    phone: str = ""


@app.get("/api/contact")
def get_contact():
    """Returns stored name and phone."""
    return {"name": stored_name, "phone": stored_phone}


@app.post("/api/contact")
def save_contact(data: ContactInput):
    """Receives name and phone, stores them, and returns them."""
    global stored_name, stored_phone
    stored_name = data.name
    stored_phone = data.phone
    return {"name": stored_name, "phone": stored_phone}


@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
