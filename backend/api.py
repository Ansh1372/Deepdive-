import hashlib
import json
import os
import tempfile
import threading
import traceback
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.ingest.router import ingest
from backend.processing.chunker import chunk_text
from backend.retrieval.vectorstore import create_vectorstore, load_vectorstore_by_id, get_embeddings
from backend.retrieval.retriever import create_hybrid_retriever
from backend.reranker.reranker import rerank
from backend.retrieval.query_transform import rewrite_query, generate_multi_queries
from backend.retrieval.compressor import compress_docs
from backend.retrieval.web_search import web_search_fallback
from backend.generation.chain import build_chain
from backend.generation.guardrail import check_guardrail
from backend.utils.logger import get_logger
from backend.utils.rate_limiter import limiter
from backend.utils.metrics import metrics, generate_request_id
from backend.utils.redis_client import get_chat_history, save_chat_history

logger = get_logger("api")

app = FastAPI(title="Deepdive API", version="1.0.0")

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Mount downloads directory
DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
app.mount("/downloads", StaticFiles(directory=DOWNLOADS_DIR), name="downloads")


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions and return a clean error response."""
    logger.error(f"[ERROR] Unhandled exception: {type(exc).__name__}: {str(exc)}")
    logger.debug(f"[ERROR] Traceback:\n{traceback.format_exc()}")
    metrics.record_error()
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again."},
    )

# CORS — allow local dev + production (EC2 serves on port 80 via nginx)
# In production the frontend proxies /api/* to the backend, so same-origin applies.
# We still allow the direct backend port for health checks and API tools.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # nginx proxies requests so CORS is same-origin in prod
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session storage + a global lock for session creation
sessions = {}
_sessions_lock = threading.Lock()   # guards creation of new session entries
chain = build_chain()

SESSIONS_DIR = "sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)


def _source_hash(source: str) -> str:
    """Generate a short hash from the source URL."""
    return hashlib.md5(source.encode()).hexdigest()[:12]


class IngestRequest(BaseModel):
    source: str


class ChatRequest(BaseModel):
    question: str
    session_id: str
    use_web: bool = False


class IngestResponse(BaseModel):
    session_id: str
    chunks_count: int
    message: str
    cached: bool = False


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def get_metrics():
    """Get API metrics and observability data."""
    return metrics.get_metrics()


@app.get("/sessions")
def list_sessions():
    """List all available cached sessions."""
    available = []
    if os.path.exists(SESSIONS_DIR):
        for name in os.listdir(SESSIONS_DIR):
            meta_path = os.path.join(SESSIONS_DIR, name, "meta.json")
            if os.path.exists(meta_path):
                with open(meta_path) as f:
                    meta = json.load(f)
                available.append({"session_id": name, "source": meta.get("source", "unknown")})
    return {"sessions": available}


@app.post("/ingest", response_model=IngestResponse)
@limiter.limit("5/minute")
def ingest_source(request: Request, body: IngestRequest):
    """Ingest a URL (YouTube/webpage) or PDF path. Reuses cache if available."""
    metrics.record_request()
    session_id = _source_hash(body.source)
    logger.info(f"[INGEST] Source: '{body.source}' | Session: {session_id}")

    # Check if already ingested and cached (fast path — no lock needed for read)
    if session_id in sessions:
        logger.info(f"[INGEST] Cache hit (in-memory) for session {session_id}")
        return IngestResponse(
            session_id=session_id,
            chunks_count=len(sessions[session_id]["chunks"]),
            message=f"Using cached data for {body.source}",
            cached=True,
        )

    # Check if saved on disk
    session_dir = os.path.join(SESSIONS_DIR, session_id)
    vectorstore_path = os.path.join(session_dir, "vectorstore")
    chunks_path = os.path.join(session_dir, "chunks.json")

    if os.path.exists(vectorstore_path) and os.path.exists(chunks_path):
        # Load from disk — acquire lock only when writing to sessions dict
        vectorstore = load_vectorstore_by_id(vectorstore_path)
        with open(chunks_path) as f:
            chunks_data = json.load(f)

        from langchain_core.documents import Document
        chunks = [Document(page_content=c["content"], metadata=c["metadata"]) for c in chunks_data]
        retriever = create_hybrid_retriever(vectorstore, chunks)

        with _sessions_lock:
            sessions[session_id] = {
                "vectorstore": vectorstore,
                "retriever": retriever,
                "chunks": chunks,
                "chat_history": [],
                "lock": threading.Lock(),   # per-session lock for chat_history mutations
            }

        return IngestResponse(
            session_id=session_id,
            chunks_count=len(chunks),
            message=f"Loaded cached data for {body.source}",
            cached=True,
        )

    # Fresh ingestion
    try:
        text = ingest(body.source)
    except ValueError as e:
        logger.warning(f"[INGEST] Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[INGEST] Unexpected error during ingestion: {type(e).__name__}: {e}")
        metrics.record_error()
        raise HTTPException(status_code=500, detail=f"Failed to ingest source: {str(e)}")

    chunks = chunk_text(text, source=body.source)

    # Save vectorstore to session-specific directory
    os.makedirs(session_dir, exist_ok=True)
    vectorstore = create_vectorstore(chunks, save_path=vectorstore_path)

    # Save chunks metadata for reload
    chunks_data = [{"content": c.page_content, "metadata": c.metadata} for c in chunks]
    with open(chunks_path, "w") as f:
        json.dump(chunks_data, f)

    # Save source metadata
    with open(os.path.join(session_dir, "meta.json"), "w") as f:
        json.dump({"source": body.source}, f)

    retriever = create_hybrid_retriever(vectorstore, chunks)

    with _sessions_lock:
        sessions[session_id] = {
            "vectorstore": vectorstore,
            "retriever": retriever,
            "chunks": chunks,
            "chat_history": [],
            "lock": threading.Lock(),   # per-session lock for chat_history mutations
        }

    return IngestResponse(
        session_id=session_id,
        chunks_count=len(chunks),
        message=f"Successfully ingested {body.source}",
        cached=False,
    )


@app.post("/upload-pdf", response_model=IngestResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """Upload a PDF file and ingest it."""
    logger.info(f"[UPLOAD] Received file: {file.filename}")

    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # Save to temp file
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, file.filename)
    with open(temp_path, "wb") as f:
        content = await file.read()
        f.write(content)

    session_id = _source_hash(file.filename)
    logger.info(f"[UPLOAD] Session: {session_id} | File: {file.filename}")

    # Ingest the PDF
    try:
        from backend.ingest.pdf import get_pdf_text
        text = get_pdf_text(temp_path)
    except ValueError as e:
        logger.warning(f"[UPLOAD] PDF extraction error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[UPLOAD] Unexpected error: {type(e).__name__}: {e}")
        metrics.record_error()
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

    chunks = chunk_text(text, source=file.filename)

    # Save vectorstore
    session_dir = os.path.join(SESSIONS_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)
    vectorstore_path = os.path.join(session_dir, "vectorstore")
    vectorstore = create_vectorstore(chunks, save_path=vectorstore_path)

    # Save chunks
    chunks_data = [{"content": c.page_content, "metadata": c.metadata} for c in chunks]
    chunks_path = os.path.join(session_dir, "chunks.json")
    with open(chunks_path, "w") as f:
        json.dump(chunks_data, f)

    with open(os.path.join(session_dir, "meta.json"), "w") as f:
        json.dump({"source": file.filename}, f)

    retriever = create_hybrid_retriever(vectorstore, chunks)

    with _sessions_lock:
        sessions[session_id] = {
            "vectorstore": vectorstore,
            "retriever": retriever,
            "chunks": chunks,
            "chat_history": [],
            "lock": threading.Lock(),
        }

    # Cleanup temp file
    os.remove(temp_path)

    return IngestResponse(
        session_id=session_id,
        chunks_count=len(chunks),
        message=f"Successfully uploaded {file.filename}",
        cached=False,
    )


@app.post("/chat")
@limiter.limit("20/minute")
def chat(request: Request, body: ChatRequest):
    """Chat with the ingested content. Returns streamed response."""
    import time
    request_id = generate_request_id()
    metrics.record_request()
    logger.info(f"[CHAT][{request_id}] Question: '{body.question}' | Session: {body.session_id}")
    session = sessions.get(body.session_id)
    if not session:
        logger.error(f"[CHAT][{request_id}] Session not found: {body.session_id}")
        metrics.record_error()
        raise HTTPException(status_code=404, detail="Session not found. Please ingest a source first.")

    retriever = session["retriever"]
    chat_history = list(session["chat_history"])  # snapshot to avoid race during pipeline build

    # Merge with Redis-persisted history (Redis wins — it survives restarts)
    redis_history = get_chat_history(body.session_id)
    if redis_history:
        chat_history = redis_history

    # Pipeline metadata tracking
    pipeline = {"original_query": body.question, "steps": []}
    total_start = time.time()

    # Guardrail check
    logger.info("[CHAT] Step 0: Guardrail check")
    t0 = time.time()
    guardrail_result = check_guardrail(body.question)
    pipeline["steps"].append({"name": "Guardrail Check", "time": round(time.time() - t0, 2), "result": "passed"})
    if not guardrail_result["allowed"]:
        pipeline["steps"][-1]["result"] = "blocked"
        logger.warning(f"[CHAT] Question BLOCKED: {guardrail_result['reason']}")
        def blocked_response():
            msg = guardrail_result["reason"].replace("\n", "\\n")
            yield f"data: {msg}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(blocked_response(), media_type="text/event-stream")

    # Format chat history
    history_str = _format_history(chat_history)

    # ---------------------------------------------------------
    # Intent Classifier: Does the user want a file/report generated?
    # ---------------------------------------------------------
    logger.info("[CHAT] Intent Classification")
    from backend.generation.chain import get_llm
    intent_llm = get_llm("fast")
    intent_prompt = f"""Is the user asking to generate, download, create, or output a file, report, spreadsheet, or PDF?
User Question: "{body.question}"
Reply ONLY with the exact word 'FILE' or 'CHAT'."""
    try:
        intent_resp = intent_llm.invoke(intent_prompt)
        intent = intent_resp.content.strip().upper()
    except Exception as e:
        logger.error(f"[CHAT][{request_id}] Intent classification failed: {e}")
        intent = "CHAT"
        
    if "FILE" in intent:
        logger.info(f"[CHAT][{request_id}] User intent is FILE. Delegating to Agent.")
        from backend.generation.agent import generate_and_run_script
        
        # Build context from retriever (we do a quick retrieval for the agent)
        quick_docs = retriever.invoke(body.question)
        agent_context = "\n\n".join(doc.page_content for doc in quick_docs)
        
        # Call agent
        agent_response = generate_and_run_script(body.question, agent_context, history_str)
        
        # Stream the agent response back as a normal chat message
        def agent_stream():
            import json as json_lib
            formatted_response = agent_response.replace("\n", "\\n")
            yield f"data: {formatted_response}\n\n"
            
            # Send empty sources and pipeline to satisfy frontend
            yield f"event: sources\ndata: {json_lib.dumps([])}\n\n"
            pipeline["steps"].append({"name": "Agentic Execution (E2B)", "time": 0, "detail": "File generated"})
            yield f"event: pipeline\ndata: {json_lib.dumps(pipeline)}\n\n"
            yield "data: [DONE]\n\n"
            
            # Save history
            with session.get("lock", threading.Lock()):
                chat_history.append({"role": "human", "content": body.question})
                chat_history.append({"role": "assistant", "content": agent_response})
                updated_history = _summarize_chat_history(chat_history)
                session["chat_history"] = updated_history
                save_chat_history(body.session_id, updated_history)

        return StreamingResponse(agent_stream(), media_type="text/event-stream")
    # ---------------------------------------------------------

    # Query rewriting
    logger.info("[CHAT] Step 1: Query rewriting")
    t0 = time.time()
    try:
        rewritten = rewrite_query(body.question, history_str)
    except Exception as e:
        logger.error(f"[CHAT][{request_id}] Query rewriting failed: {e}")
        rewritten = body.question  # fallback to original
    pipeline["steps"].append({"name": "Query Rewriting", "time": round(time.time() - t0, 2), "detail": rewritten})

    # Multi-query generation
    logger.info("[CHAT] Step 2: Multi-query generation")
    t0 = time.time()
    try:
        multi_queries = generate_multi_queries(rewritten)
    except Exception as e:
        logger.error(f"[CHAT][{request_id}] Multi-query generation failed: {e}")
        multi_queries = []  # fallback to just the rewritten query
    all_queries = [rewritten] + multi_queries
    pipeline["steps"].append({"name": "Multi-Query Generation", "time": round(time.time() - t0, 2), "detail": f"{len(multi_queries)} variations"})
    logger.info(f"[CHAT] Total queries to search: {len(all_queries)}")

    # Hybrid retrieval
    logger.info("[CHAT] Step 3: Hybrid retrieval for all queries")
    t0 = time.time()
    all_docs = []
    seen = set()
    for i, q in enumerate(all_queries):
        docs = retriever.invoke(q)
        for doc in docs:
            h = hash(doc.page_content)
            if h not in seen:
                seen.add(h)
                all_docs.append(doc)
    pipeline["steps"].append({"name": "Hybrid Retrieval", "time": round(time.time() - t0, 2), "detail": f"{len(all_docs)} unique docs"})
    logger.info(f"[CHAT] Retrieved {len(all_docs)} unique docs total")

    # Reranking
    logger.info("[CHAT] Step 4: Reranking")
    t0 = time.time()
    confidence = 0.0
    try:
        reranked_docs, rerank_scores, confidence = rerank(rewritten, all_docs, top_k=4)
    except Exception as e:
        logger.error(f"[CHAT][{request_id}] Reranking failed: {e}")
        reranked_docs = all_docs[:4]
        rerank_scores = []
        confidence = 0.0
    pipeline["steps"].append({
        "name": "Reranking",
        "time": round(time.time() - t0, 2),
        "detail": f"Top {len(reranked_docs)} selected | confidence: {confidence:.2f}"
    })

    # Contextual compression
    logger.info("[CHAT] Step 5: Contextual compression")
    t0 = time.time()
    try:
        compressed_docs = compress_docs(rewritten, reranked_docs)
    except Exception as e:
        logger.error(f"[CHAT][{request_id}] Compression failed: {e}")
        compressed_docs = reranked_docs
    used_fallback = False
    if not compressed_docs:
        logger.warning("[CHAT] Compression filtered all docs — falling back to uncompressed")
        compressed_docs = reranked_docs
        used_fallback = True
    pipeline["steps"].append({
        "name": "Contextual Compression",
        "time": round(time.time() - t0, 2),
        "detail": f"{len(compressed_docs)} docs kept" + (" (fallback)" if used_fallback else "")
    })

    # Agentic Decision: Use LLM to judge if context is sufficient to answer the question
    from backend.generation.chain import get_llm
    web_context = ""

    context_for_check = "\n\n".join(doc.page_content for doc in compressed_docs)

    t0 = time.time()
    sufficiency_llm = get_llm("fast")
    sufficiency_prompt = f"""You are a STRICT factual validator. Check if the context EXPLICITLY contains the answer to the question.

RULES:
1. Search the context for the EXACT information requested.
2. "What is X's age?" → Look for a birth date or age number IN the context. If not found → INSUFFICIENT.
3. "What is X's score?" → Look for the specific score/number IN the context. If not found → INSUFFICIENT.
4. "Summarize this" or "What is this about?" → If context has content to summarize → SUFFICIENT.
5. The context being ABOUT the same topic is NOT enough. The SPECIFIC answer must be explicitly written.
6. Do NOT use your training knowledge. ONLY the text below counts.

EXAMPLES:
- Context talks about "Virat Kohli won IPL final" → Question "What is Virat's age?" → INSUFFICIENT (age not mentioned)
- Context talks about "Kohli scored 75 runs" → Question "How many runs did Kohli score?" → SUFFICIENT (75 is there)
- Context talks about "Python basics" → Question "Summarize this" → SUFFICIENT (there's content to summarize)

Context: {context_for_check[:1500]}

Question: {body.question}

Is the SPECIFIC answer explicitly written in the context above? Reply ONLY: "SUFFICIENT" or "INSUFFICIENT"."""

    try:
        sufficiency_response = sufficiency_llm.invoke(sufficiency_prompt)
        is_sufficient = "SUFFICIENT" in sufficiency_response.content.strip().upper()
    except Exception as e:
        logger.error(f"[CHAT][{request_id}] Sufficiency check failed: {e}")
        is_sufficient = True  # Default to trusting the context if check fails

    sufficiency_time = round(time.time() - t0, 2)
    pipeline["steps"].append({
        "name": "Context Sufficiency Check",
        "time": sufficiency_time,
        "detail": "Sufficient ✓" if is_sufficient else "Insufficient → web search"
    })

    if not is_sufficient:
        logger.warning(f"[CHAT] Context INSUFFICIENT for question — triggering web search")
        t0 = time.time()
        try:
            web_context = web_search_fallback(rewritten)
        except Exception as e:
            logger.error(f"[CHAT][{request_id}] Web search fallback failed: {e}")
            web_context = ""
        pipeline["steps"].append({
            "name": "⚡ Web Search Fallback",
            "time": round(time.time() - t0, 2),
            "detail": f"Found {len(web_context)} chars from internet"
        })
    else:
        logger.info(f"[CHAT] Context is sufficient — answering from ingested document")

    # Build final context — merge document context with web fallback if used
    context = "\n\n".join(doc.page_content for doc in compressed_docs)
    if web_context:
        context = context + "\n\n[Additional context from web search]:\n" + web_context
    logger.info(f"[CHAT] Step 6: Generating answer (context: {len(context)} chars, web_augmented: {bool(web_context)})")
    pipeline["confidence"] = round(confidence, 3)
    pipeline["web_augmented"] = bool(web_context)

    # Stream response
    def generate():
        import json as json_lib
        gen_start = time.time()
        full_answer = ""
        try:
            for chunk in chain.stream({"context": context, "question": body.question, "chat_history": history_str}):
                full_answer += chunk
                encoded_chunk = chunk.replace("\n", "\\n")
                yield f"data: {encoded_chunk}\n\n"
        except Exception as e:
            logger.error(f"[CHAT][{request_id}] Generation failed: {type(e).__name__}: {e}")
            error_msg = "Sorry, an error occurred while generating the answer. Please try again."
            yield f"data: {error_msg}\n\n"
            metrics.record_error()

        # Update chat history — use per-session lock to prevent concurrent mutation
        with session.get("lock", threading.Lock()):
            chat_history.append({"role": "human", "content": body.question})
            chat_history.append({"role": "assistant", "content": full_answer})
            updated_history = _summarize_chat_history(chat_history)
            session["chat_history"] = updated_history
            # Persist to Redis so history survives container restarts
            save_chat_history(body.session_id, updated_history)

        # Send citations/sources
        sources = []
        for doc in compressed_docs:
            sources.append({
                "content": doc.page_content[:150] + "..." if len(doc.page_content) > 150 else doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "chunk_index": doc.metadata.get("chunk_index", 0),
            })
        yield f"event: sources\ndata: {json_lib.dumps(sources)}\n\n"

        # Send pipeline metadata
        pipeline["steps"].append({"name": "Answer Generation", "time": round(time.time() - gen_start, 2), "detail": f"{len(full_answer)} chars"})
        pipeline["total_time"] = round(time.time() - total_start, 2)
        pipeline["rewritten_query"] = rewritten
        pipeline["variations"] = multi_queries
        pipeline["request_id"] = request_id
        yield f"event: pipeline\ndata: {json_lib.dumps(pipeline)}\n\n"

        # Record metrics
        metrics.record_chat(pipeline["total_time"])
        for step in pipeline["steps"]:
            metrics.record_pipeline_step(step["name"], step["time"])

        logger.info(f"[CHAT][{request_id}] Answer generated: {len(full_answer)} chars | Total: {pipeline['total_time']}s")
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


def _format_history(history):
    if not history:
        return "No previous conversation."
    lines = []
    for msg in history:
        role = "Human" if msg["role"] == "human" else "Assistant"
        lines.append(f"{role}: {msg['content']}")
    return "\n".join(lines)

def _summarize_chat_history(history):
    """Summarizes older conversation history to save tokens while preserving context."""
    # Keep last 2 pairs (4 messages) intact, summarize the rest if history gets too long (>6 messages)
    if len(history) <= 6:
        return history
    
    from backend.generation.chain import get_llm
    from langchain_core.messages import HumanMessage
    llm = get_llm("fast")
    
    old_messages = history[:-4]
    recent_messages = history[-4:]
    
    old_text = _format_history(old_messages)
    prompt = f"Summarize the following older conversation history concisely, preserving all key context, facts, and topics discussed:\n\n{old_text}"
    
    try:
        logger.info(f"Summarizing older conversation history ({len(old_messages)} messages) to save tokens...")
        summary_resp = llm.invoke([HumanMessage(content=prompt)])
        summary = summary_resp.content.strip()
    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        # Fallback to truncating if LLM summary fails
        return history[-6:]
        
    return [{"role": "assistant", "content": f"[Summary of previous conversation]: {summary}"}] + recent_messages
