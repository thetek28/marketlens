FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data output && \
    useradd -m -r -s /bin/bash marketlens && \
    chown -R marketlens:marketlens /app

USER marketlens

ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV MLENS_DATA_DIR=/app/data
ENV MLENS_OUTPUT_DIR=/app/output

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["python", "-m", "uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
