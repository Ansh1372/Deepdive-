import re
from sentence_transformers import CrossEncoder
from backend.utils.logger import get_logger

logger = get_logger("reranker")

reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

# Confidence threshold for ms-marco-MiniLM-L-6-v2
# This model outputs raw logits (not 0-1), typically ranging from -10 to +10
# Scores below this indicate the documents likely don't contain a direct answer
CONFIDENCE_THRESHOLD = 5.0

# Open-ended queries that don't need a specific fact — the cross-encoder
# always scores these low because they're not factual lookups.
# For these queries, confidence is always "sufficient" if we have any docs.
_OPEN_ENDED_PATTERNS = re.compile(
    r"^\s*(summarize|summary|summarise|give me a summary|"
    r"what (is this|are the main|are the key)|"
    r"explain|overview|outline|describe|"
    r"key (points|takeaways|highlights|ideas)|"
    r"main (points|ideas|topics|concepts)|"
    r"tell me about|what does this (say|cover|discuss)|"
    r"give (me |an? )?(overview|summary|recap))",
    re.IGNORECASE,
)

# Score we return for open-ended queries — above CONFIDENCE_THRESHOLD so
# the sufficiency check passes and the UI shows "High confidence"
_OPEN_ENDED_CONFIDENCE = 7.5


def is_open_ended(query: str) -> bool:
    """Return True if the query is a summarization / open-ended request."""
    return bool(_OPEN_ENDED_PATTERNS.match(query.strip()))


def rerank(query, docs, top_k=6):
    """Rerank documents using cross-encoder. Returns (docs, scores, confidence).

    For open-ended queries (summarize, explain, overview…) the cross-encoder
    score is meaningless — it was trained on factual QA pairs.  We still rerank
    to surface the most relevant chunks first, but we override the confidence
    score so the UI doesn't misleadingly show LOW CONFIDENCE on a summarization
    request that has perfectly good content to work with.
    """
    if not docs:
        logger.warning("No documents to rerank")
        return [], [], 0.0

    open_ended = is_open_ended(query)
    logger.info(f"Reranking {len(docs)} docs for query: '{query[:50]}...' | open_ended={open_ended}")

    pairs = [(query, doc.page_content) for doc in docs]
    scores = reranker.predict(pairs)

    scored_docs = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
    top_scored = scored_docs[:top_k]
    top_docs = [doc for _, doc in top_scored]
    top_scores = [float(score) for score, _ in top_scored]

    if open_ended:
        # Override: we have content, summarization is always possible
        confidence = _OPEN_ENDED_CONFIDENCE
        logger.info(f"Open-ended query — overriding confidence to {confidence} (raw max: {max(top_scores):.3f})")
    else:
        confidence = max(top_scores) if top_scores else 0.0
        logger.info(f"Top {top_k} scores: {[f'{s:.3f}' for s in top_scores]}")
        logger.info(f"Confidence: {confidence:.3f} (threshold: {CONFIDENCE_THRESHOLD})")

    return top_docs, top_scores, confidence
