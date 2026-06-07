from langchain_text_splitters import RecursiveCharacterTextSplitter
from backend.utils.logger import get_logger

logger = get_logger("chunker")


def chunk_text(text, source="unknown", chunk_size=1000, overlap=200):
    """Split text into chunks for embedding."""
    logger.info(f"Chunking {len(text)} chars (chunk_size={chunk_size}, overlap={overlap})")

    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    chunks = splitter.create_documents(
        [text],
        metadatas=[{"source": source, "chunk_index": 0}]
    )
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = i

    logger.info(f"Created {len(chunks)} chunks from source: '{source[:50]}'")
    return chunks
