# Business Card Service

Backend API for the Business Card frontend. Stores and serves contact info (name, phone).

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/contact` | Returns stored name and phone |
| POST | `/api/contact` | Saves name and phone (JSON: `{ "name": "...", "phone": "..." }`) |
| GET | `/api/health` | Health check |

## Connect Frontend + Backend

The frontend lives in the **bussiness-card** repo (sibling folder). To run both together:

### 1. Start the backend (this repo)

```bash
cd backend
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend runs at **http://localhost:8000**

### 2. Start the frontend (bussiness-card repo)

```bash
cd ../bussiness-card
cp .env.example .env.local   # Optional: API URL defaults to http://localhost:8000
npm install
npm run dev
```

Frontend runs at **http://localhost:3000**

### 3. Use the app

1. Open **http://localhost:3000** in your browser
2. Enter name and phone – they are saved to the backend
3. Refresh the page – data from the backend appears

## Environment

- **Frontend**: Set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `.env.local` if the backend uses a different URL.
