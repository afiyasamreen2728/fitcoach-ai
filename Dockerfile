FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for better layer caching
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy application code
COPY backend ./backend
COPY frontend ./frontend

ENV PORT=8000
EXPOSE 8000

# Run from inside backend/ so main.py's relative frontend path resolves correctly
WORKDIR /app/backend
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
