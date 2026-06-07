# ── Stage 1: Build React frontend ─────────────────────────────────────────
FROM node:18-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python backend + nginx in one container ──────────────────────
FROM python:3.10-slim

WORKDIR /app

# System dependencies — nginx + supervisor (process manager)
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    supervisor \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first
RUN pip install --no-cache-dir \
    torch==2.4.1+cpu \
    --extra-index-url https://download.pytorch.org/whl/cpu

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download ML models into the image (no runtime HuggingFace calls)
RUN python -c "\
from sentence_transformers import SentenceTransformer, CrossEncoder; \
print('Downloading embedding model...'); \
SentenceTransformer('all-MiniLM-L6-v2'); \
print('Downloading cross-encoder...'); \
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2'); \
print('Done.') \
"

# HuggingFace offline mode — use cached models only
ENV TRANSFORMERS_OFFLINE=1
ENV HF_DATASETS_OFFLINE=1

# Copy backend code
COPY backend/ ./backend/

# Copy built frontend from stage 1
COPY --from=frontend-build /app/frontend/dist /usr/share/nginx/html

# nginx config — serve frontend on port 7860, proxy /api/ to backend on 8001
COPY hf-nginx.conf /etc/nginx/conf.d/default.conf
RUN rm -f /etc/nginx/sites-enabled/default

# Supervisor config — runs nginx + uvicorn together
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Sessions directory
RUN mkdir -p /app/sessions

# HuggingFace Spaces requires port 7860
EXPOSE 7860

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
