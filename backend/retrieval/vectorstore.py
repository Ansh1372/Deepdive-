import os
import threading
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

# Global embedding model — loaded once, shared across all sessions (thread-safe read)
_embeddings = None
_embeddings_lock = threading.Lock()


def get_embeddings():
    """Return a singleton embeddings instance (thread-safe lazy init)."""
    global _embeddings
    if _embeddings is None:
        with _embeddings_lock:
            if _embeddings is None:  # double-checked locking
                _embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return _embeddings


def create_vectorstore(chunks, save_path="vectorstore"):
    """Create FAISS vectorstore and save to disk.
    
    FAISS.from_documents is CPU-bound and not thread-safe during build,
    so each call creates its own index and saves it atomically.
    """
    embeddings = get_embeddings()
    vectorstore = FAISS.from_documents(chunks, embeddings)
    vectorstore.save_local(save_path)
    return vectorstore


def load_vectorstore_by_id(path):
    """Load vectorstore from a specific path (read-only, thread-safe)."""
    if os.path.exists(path):
        return FAISS.load_local(path, get_embeddings(), allow_dangerous_deserialization=True)
    return None


def load_vectorstore():
    """Load default vectorstore from disk if available."""
    if os.path.exists("vectorstore"):
        return FAISS.load_local("vectorstore", get_embeddings(), allow_dangerous_deserialization=True)
    return None
