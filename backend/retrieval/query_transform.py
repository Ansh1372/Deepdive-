from backend.generation.chain import get_llm
from backend.utils.logger import get_logger

logger = get_logger("query_transform")


def rewrite_query(question: str, chat_history: str) -> str:
    """Rewrite user question into a better search query using context."""
    logger.info(f"Rewriting query: '{question}'")
    llm = get_llm("fast")
    prompt = f"""Given the conversation history and the user's question, 
rewrite it into a clear, standalone search query optimized for retrieval.
Fix any spelling mistakes or typos in the question.
If the user says "it" or "this", understand they are referring to the ingested content/document.
Only return the rewritten query, nothing else.

Chat history: {chat_history}
User question: {question}
Rewritten query:"""

    response = llm.invoke(prompt)
    rewritten = response.content.strip()
    logger.info(f"Rewritten to: '{rewritten}'")
    return rewritten


def generate_multi_queries(question: str) -> list:
    """Generate 3 different versions of the question for broader retrieval."""
    logger.info(f"Generating multi-queries from: '{question}'")
    llm = get_llm("fast")
    prompt = f"""Generate 3 different versions of this question to improve search coverage.
Each version should use different words but mean the same thing.
Return only the 3 questions, one per line. No numbering.

Original question: {question}"""

    response = llm.invoke(prompt)
    queries = [q.strip() for q in response.content.strip().split("\n") if q.strip()]
    queries = queries[:3]
    for i, q in enumerate(queries):
        logger.debug(f"  Variation {i+1}: '{q}'")
    logger.info(f"Generated {len(queries)} query variations")
    return queries
