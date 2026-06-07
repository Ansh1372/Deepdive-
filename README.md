# Deepdive — AI-Powered Content Q&A

> Chat with any YouTube video, webpage, or PDF using a production-grade RAG pipeline powered by LLaMA 3.3 70B.

🔗 **Live Demo:** [ansh1372-deepdive.hf.space](https://ansh1372-deepdive.hf.space) &nbsp;|&nbsp; 💻 **GitHub:** [Ansh1372/Deepdive-](https://github.com/Ansh1372/Deepdive-)

![Python](https://img.shields.io/badge/Python-3.10-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?style=flat&logo=react&logoColor=black)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat&logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat)

---

## What it does

Paste a YouTube URL, webpage link, or upload a PDF. Deepdive ingests the content, indexes it into a FAISS vector store, and lets you have a full conversation with it. Every response streams token by token with cited sources and a live pipeline breakdown.

When the ingested content isn't enough to answer your question, the system automatically falls back to a live DuckDuckGo web search — no manual switching needed.

---

## Demo

| Ingest a source | Chat with it |
|:---:|:---:|
| Paste any URL or upload PDF | Ask specific questions, get streamed answers with sources |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    React Frontend (Nginx)                │
│              Streaming SSE  ·  Session history           │
└───────────────────────┬─────────────────────────────────┘
                        │ REST + SSE
┌───────────────────────▼─────────────────────────────────┐
│                   FastAPI Backend                        │
│                                                         │
│  /ingest ──► YouTube Transcript                         │
│           ├─ Web Scraper (Trafilatura + Gemini Vision)  │
│           └─ PDF Parser (pdfplumber)                    │
│                │                                        │
│          RecursiveCharacterTextSplitter                 │
│                │                                        │
│     FAISS vectorstore (saved per session to disk)       │
│                                                         │
│  /chat ───► 1. Guardrail check (blocklist + LLM)        │
│             2. Query rewriting (LLM)                    │
│             3. Multi-query fan-out (3 variations)       │
│             4. Hybrid retrieval (FAISS + BM25, merged)  │
│             5. Cross-encoder reranking                  │
│             6. Contextual compression (LLM per chunk)   │
│             7. Sufficiency check → web search fallback  │
│             8. Streaming generation (LLaMA 3.3 70B)     │
│                                                         │
└──────────┬──────────────────────────┬───────────────────┘
           │                          │
    ┌──────▼──────┐          ┌────────▼────────┐
    │    Redis    │          │   FAISS + Disk  │
    │ Chat history│          │ Vector indexes  │
    │  (24h TTL) │          │  (per session)  │
    └─────────────┘          └─────────────────┘
```

---

## Tech Stack

### Backend
| Component | Technology |
|-----------|-----------|
| API Framework | FastAPI + Uvicorn |
| LLM | LLaMA 3.3 70B via Groq API |
| Embeddings | `all-MiniLM-L6-v2` (HuggingFace, local) |
| Vector Store | FAISS CPU (per-session, disk-persisted) |
| Keyword Search | BM25 (`rank-bm25`) |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Orchestration | LangChain |
| Session Storage | Redis (chat history, 24h TTL) |
| YouTube | `youtube-transcript-api` |
| Web Scraping | Trafilatura |
| Image Understanding | Google Gemini 2.5 Flash (optional) |
| PDF Parsing | pdfplumber |
| Rate Limiting | slowapi (5/min ingest, 20/min chat) |

### Frontend
| Component | Technology |
|-----------|-----------|
| Framework | React 18 + Vite |
| Streaming | Server-Sent Events (SSE) |
| Markdown | react-markdown |
| Serving | Nginx |

### Infrastructure
| Component | Technology |
|-----------|-----------|
| Containers | Docker Compose |
| Deployment | AWS EC2 (t2.micro free tier) |

---

## RAG Pipeline — 7 Steps Per Query

```
User question
    │
    ▼
① Guardrail       — keyword blocklist + LLM binary classifier (ALLOW/BLOCK)
    │
    ▼
② Query Rewrite   — LLM rewrites query using chat history for context
    │
    ▼
③ Multi-Query     — LLM generates 3 variations → 4 total queries
    │
    ▼
④ Hybrid Retrieval — FAISS semantic search + BM25 keyword search, merged & deduplicated
    │
    ▼
⑤ Cross-Encoder Reranking — ms-marco-MiniLM scores every (query, doc) pair jointly
    │
    ▼
⑥ Contextual Compression — LLM trims each chunk to only the relevant excerpt
    │
    ▼
⑦ Sufficiency Check — LLM decides if context is enough; triggers DuckDuckGo if not
    │
    ▼
Streaming generation → token chunks + sources + pipeline metadata (SSE)
```

---

## Features

- **Multi-source ingestion** — YouTube, webpages, PDFs, with image understanding via Gemini Vision
- **Hybrid retrieval** — FAISS semantic + BM25 keyword, merged and deduplicated
- **Cross-encoder reranking** — significantly higher precision than bi-encoder dot-product
- **Agentic web fallback** — LLM decides when to search the web, no manual toggle
- **Streaming responses** — token-by-token with sources and per-step pipeline timing
- **Persistent chat history** — Redis with 24h TTL, survives container restarts
- **LLM-as-judge evaluation** — faithfulness, relevancy, context precision, correctness
- **Observability** — MetricsTracker with P95 latency, per-step timing, error rates
- **Guardrails** — two-layer safety (keyword + LLM classifier)
- **Rate limiting** — IP-based via slowapi

---

## Quick Start (Local)

### Prerequisites
- Docker Desktop installed and running
- Groq API key (free at [console.groq.com](https://console.groq.com))
- Gemini API key (optional, for image understanding)

### Run

```bash
# 1. Clone
git clone https://github.com/Ansh1372/Deepdive-.git
cd Deepdive-

# 2. Set up environment
cp .env.example .env
# Edit .env and add your GROQ_API_KEY

# 3. Start everything
docker compose up --build

# Frontend → http://localhost:3000
# Backend API → http://localhost:8001
# API docs → http://localhost:8001/docs
```

First build takes ~10 minutes (downloads ML models). Subsequent builds use cache and take ~20 seconds.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/ingest` | Ingest a URL (YouTube / webpage) |
| `POST` | `/upload-pdf` | Upload and ingest a PDF file |
| `POST` | `/chat` | Stream chat response (SSE) |
| `GET` | `/sessions` | List all cached sessions |
| `GET` | `/metrics` | Observability metrics (requests, latency, P95) |

### Chat response format (SSE)

```
data: token chunk\n\n          ← streamed answer tokens
event: sources\n
data: [{...}]\n\n              ← cited source chunks
event: pipeline\n
data: {...}\n\n                ← per-step timing and metadata
data: [DONE]\n\n               ← stream end
```

---

## Evaluation

Run the LLM-as-judge evaluation suite:

```bash
docker exec -it deepdive-backend-1 python -m backend.evaluation.evaluate
```

Scores 4 metrics using the LLM as evaluator:

| Metric | What it measures |
|--------|-----------------|
| Faithfulness | Are claims grounded in retrieved context? |
| Answer Relevancy | Does the answer address the question? |
| Context Precision | Are retrieved chunks relevant to the query? |
| Correctness | Does the answer match ground truth? |

Results saved to `evaluation_results.json`.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | ✅ Yes | Groq API key for LLaMA 3.3 70B |
| `GEMINI_API_KEY` | Optional | Enables image understanding on web pages |
| `REDIS_URL` | Auto-set | Set by Docker Compose — `redis://redis:6379` |

---

## Project Structure

```
deepdive/
├── backend/
│   ├── api.py                  # FastAPI app, all endpoints
│   ├── ingest/
│   │   ├── youtube.py          # YouTube transcript extraction
│   │   ├── webpage.py          # Web scraping + Gemini Vision
│   │   ├── pdf.py              # PDF text extraction
│   │   └── router.py           # Source type detection
│   ├── processing/
│   │   └── chunker.py          # RecursiveCharacterTextSplitter
│   ├── retrieval/
│   │   ├── vectorstore.py      # FAISS (thread-safe singleton embeddings)
│   │   ├── retriever.py        # HybridRetriever (FAISS + BM25)
│   │   ├── query_transform.py  # Query rewriting + multi-query
│   │   ├── compressor.py       # LLM contextual compression
│   │   └── web_search.py       # DuckDuckGo fallback
│   ├── reranker/
│   │   └── reranker.py         # Cross-encoder reranking
│   ├── generation/
│   │   ├── chain.py            # LangChain generation chain
│   │   └── guardrail.py        # Safety layer
│   ├── utils/
│   │   ├── redis_client.py     # Redis chat history (with fallback)
│   │   ├── metrics.py          # Observability tracker
│   │   ├── logger.py           # Structured logging
│   │   └── rate_limiter.py     # slowapi config
│   ├── evaluation/
│   │   ├── evaluate.py         # LLM-as-judge evaluation
│   │   └── test_data.py        # Test dataset
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx             # Root component, session management
│   │   ├── api.js              # API client with SSE streaming
│   │   └── components/
│   │       ├── ChatWindow.jsx  # Chat interface
│   │       ├── IngestForm.jsx  # URL input + PDF upload
│   │       ├── Sidebar.jsx     # Session history
│   │       ├── MessageBubble.jsx
│   │       ├── PipelinePanel.jsx
│   │       ├── SourcePanel.jsx
│   │       └── Dashboard.jsx   # Metrics view
│   ├── package.json
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml          # Local development
├── docker-compose.prod.yml     # AWS EC2 production
├── .env.example
└── README.md
```

---

## License

MIT
