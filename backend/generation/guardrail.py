import re
from backend.generation.chain import get_llm
from backend.utils.logger import get_logger

logger = get_logger("guardrail")

# Keyword blocklist for instant rejection
BLOCKED_KEYWORDS = [
    "hack", "exploit", "malware", "virus", "ransomware",
    "kill", "murder", "bomb", "weapon", "terrorist",
    "nude", "porn", "xxx", "sexual",
    "ignore your instructions", "ignore previous", "you are now",
    "forget your rules", "disregard all",
]

# Prompt injection patterns
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions|prompts|rules)",
    r"you\s+are\s+now\s+a",
    r"pretend\s+you\s+are",
    r"act\s+as\s+if",
    r"system\s*:\s*",
]


def check_guardrail(question: str) -> dict:
    """
    Check if a question passes the guardrail.
    Returns: {"allowed": True/False, "reason": str}
    """
    question_lower = question.lower().strip()
    logger.info(f"Guardrail check: '{question[:50]}...'")

    # Step 1: Keyword blocklist (instant)
    for keyword in BLOCKED_KEYWORDS:
        if re.search(r'\b' + re.escape(keyword) + r'\b', question_lower):
            logger.warning(f"BLOCKED by keyword: '{keyword}'")
            return {
                "allowed": False,
                "reason": "I can't help with that type of request. Please ask questions related to the ingested content."
            }

    # Step 2: Prompt injection patterns (instant)
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, question_lower):
            logger.warning(f"BLOCKED by injection pattern: '{pattern}'")
            return {
                "allowed": False,
                "reason": "I can only answer questions about the ingested content."
            }

    # Step 3: Empty or too short
    if len(question_lower) < 2:
        return {
            "allowed": False,
            "reason": "Please ask a more specific question."
        }

    # Step 4: LLM check for edge cases
    llm = get_llm("fast")
    prompt = f"""You are a content safety classifier. Determine if this user question is appropriate for a document Q&A system.

The system answers questions about content the user has uploaded (articles, videos, PDFs).
Users may ask about text, images, summaries, authors, topics, or any aspect of the uploaded content.

Only block questions that are clearly harmful, dangerous, or completely unrelated to any form of content analysis.

Question: "{question}"

Respond with ONLY one word:
- "ALLOW" if the question could reasonably relate to uploaded content (summaries, details, images, authors, topics, etc.)
- "BLOCK" if the question is clearly harmful or has zero relation to content Q&A (e.g., "how to make a bomb")

Answer:"""

    response = llm.invoke(prompt)
    verdict = response.content.strip().upper()

    if "BLOCK" in verdict:
        logger.warning(f"BLOCKED by LLM check")
        return {
            "allowed": False,
            "reason": "I can only answer questions related to the ingested content. Please rephrase your question."
        }

    logger.info("Guardrail: PASSED")
    return {"allowed": True, "reason": ""}
