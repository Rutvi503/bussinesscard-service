# Business Card API - FastAPI service
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py database.py ./

# Run on port 8000
EXPOSE 8000

# Run uvicorn (DB credentials via env vars at runtime)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
