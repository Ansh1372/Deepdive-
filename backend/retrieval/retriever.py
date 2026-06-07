from rank_bm25 import BM25Okapi
from backend.utils.logger import get_logger

logger = get_logger("retriever")


def create_hybrid_retriever(vectorstore, chunks):
    """Create a hybrid retriever combining FAISS semantic + BM25 keyword search."""
    logger.info(f"Creating hybrid retriever with {len(chunks)} chunks")
    return HybridRetriever(vectorstore, chunks)


class HybridRetriever:
    """Custom hybrid retriever: 50% semantic (FAISS) + 50% keyword (BM25)."""

    def __init__(self, vectorstore, chunks, k=4):
        self.vectorstore = vectorstore
        self.chunks = chunks
        self.k = k

        tokenized_docs = [doc.page_content.lower().split() for doc in chunks]
        self.bm25 = BM25Okapi(tokenized_docs)
        logger.debug(f"BM25 index built with {len(chunks)} documents")

    def invoke(self, query: str):
        """Retrieve docs using both semantic and keyword search, then merge."""
        logger.debug(f"Hybrid search for: '{query[:50]}...'")

        # Semantic results
        semantic_docs = self.vectorstore.similarity_search(query, k=self.k)
        logger.debug(f"  FAISS returned {len(semantic_docs)} docs")

        # BM25 results
        tokenized_query = query.lower().split()
        bm25_scores = self.bm25.get_scores(tokenized_query)
        top_indices = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:self.k]
        bm25_docs = [self.chunks[i] for i in top_indices]
        logger.debug(f"  BM25 returned {len(bm25_docs)} docs")

        # Merge and deduplicate
        seen = set()
        merged = []
        for doc in semantic_docs + bm25_docs:
            content_hash = hash(doc.page_content)
            if content_hash not in seen:
                seen.add(content_hash)
                merged.append(doc)

        logger.info(f"  Merged: {len(merged)} unique docs (from {len(semantic_docs)} semantic + {len(bm25_docs)} BM25)")
        return merged[:self.k * 2]
