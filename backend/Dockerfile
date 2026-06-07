FROM python:3.10-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first (avoids pip pulling the CUDA 2GB build)
RUN pip install --no-cache-dir \
    torch==2.4.1+cpu \
    --extra-index-url https://download.pytorch.org/whl/cpu

# Install remaining Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Pre-download ML models into the image ──────────────────────────────────
# Models are baked into the image at build time so:
#   1. Container startup is instant (no HuggingFace download on first run)
#   2. App works even if HuggingFace is unreachable at runtime
#   3. No more 502s caused by slow model loading blocking the health check
RUN python -c "\
from sentence_transformers import SentenceTransformer, CrossEncoder; \
print('Downloading embedding model...'); \
SentenceTransformer('all-MiniLM-L6-v2'); \
print('Downloading cross-encoder reranker...'); \
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2'); \
print('All models cached successfully.') \
"

# Set HuggingFace to offline mode at runtime — use only the baked-in cache
# This prevents any attempted network calls to huggingface.co on startup
ENV TRANSFORMERS_OFFLINE=1
ENV HF_DATASETS_OFFLINE=1
# ───────────────────────────────────────────────────────────────────────────

# Copy application code
COPY backend/ ./backend/
COPY .env* ./

# Create sessions directory
RUN mkdir -p sessions

EXPOSE 8001

CMD ["python", "-m", "uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8001"]
