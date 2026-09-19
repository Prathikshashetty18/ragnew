FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered output for real-time logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0 \
    HF_HOME=/home/appuser/.cache/huggingface \
    DATABASE_URL=sqlite:////app/data/clinical_rag_v2.db \
    UPLOAD_DIR=/app/data/uploads \
    VECTOR_STORE_DIR=/app/data/vector_store \
    SEED_DIR=/app/backend/seed_data

# Install gosu for secure privilege dropping and curl for health probes
RUN apt-get update && \
    apt-get install -y --no-install-recommends gosu curl && \
    rm -rf /var/lib/apt/lists/*

# Create unprivileged application user
RUN useradd -m -u 10001 -s /bin/bash appuser

WORKDIR /app

# Ensure persistent directories and Hugging Face cache exist with correct ownership
RUN mkdir -p /app/data/uploads /app/data/vector_store /home/appuser/.cache/huggingface && \
    chown -R appuser:appuser /app /home/appuser

# Install CPU-only PyTorch explicitly to avoid massive CUDA download
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install verified pinned dependencies
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Pre-download and cache embedding and cross-encoder models into HF_HOME
# Fails the build immediately if model download fails, ensuring no broken images
RUN python3 -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
SentenceTransformer('all-MiniLM-L6-v2'); \
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')" && \
    chown -R appuser:appuser /home/appuser/.cache

# Copy backend application source code
COPY --chown=appuser:appuser backend/ /app/backend/

WORKDIR /app/backend

EXPOSE 8000

# Ensure persistent storage volume is writable by appuser, then drop root privileges to appuser
CMD ["sh", "-c", "mkdir -p /app/data/uploads /app/data/vector_store && chown -R appuser:appuser /app/data && exec gosu appuser uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8000}\" --workers 1"]
