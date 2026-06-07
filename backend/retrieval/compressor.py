from backend.generation.chain import get_llm
from backend.utils.logger import get_logger

logger = get_logger("compressor")


def compress_docs(question: str, docs) -> list:
    """Compress retrieved docs to only the relevant parts for the question."""
    if not docs:
        return []

    logger.info(f"Compressing {len(docs)} docs for question: '{question[:50]}...'")
    llm = get_llm()

    compressed = []
    for i, doc in enumerate(docs):
        prompt = f"""Extract only the parts of the following text that are relevant to answering the question.
If nothing is relevant, respond with "NOT_RELEVANT".
Keep the extracted text concise but complete. Do not add any new information.

Question: {question}

Text: {doc.page_content}

Relevant extract:"""

        response = llm.invoke(prompt)
        extract = response.content.strip()

        if extract and extract != "NOT_RELEVANT":
            doc.page_content = extract
            compressed.append(doc)
            logger.debug(f"  Doc {i+1}: compressed {len(doc.page_content)} -> {len(extract)} chars")
        else:
            logger.debug(f"  Doc {i+1}: filtered out (not relevant)")

    logger.info(f"Compression complete: {len(compressed)}/{len(docs)} docs kept")
    return compressed
