FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY online_backend/requirements.txt /app/requirements.txt
COPY online_db/requirements.txt /app/db_requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt -r /app/db_requirements.txt

# Copy application code
COPY online_backend/ /app/online_backend/
COPY online_db/ /app/online_db/

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

# Run
CMD ["uvicorn", "online_backend.app:create_app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--factory"]
