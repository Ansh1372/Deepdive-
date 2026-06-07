"""
Redis client for persistent chat history storage.

Chat history is stored in Redis with a 24-hour TTL per session.
If Redis is unavailable (not configured, connection error), the app
falls back to in-memory storage transparently — no crash, no data loss.

Key format:  chat_history:<session_id>
Value:       JSON list of {"role": "human"|"assistant", "content": "..."}
TTL:         24 hours (resets on each write)
"""

import json
import os
from backend.utils.logger import get_logger

logger = get_logger("redis_client")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
CHAT_HISTORY_TTL = 60 * 60 * 24  # 24 hours in seconds
_client = None


def _get_client():
    """Lazy-init Redis client. Returns None if Redis is not available."""
    global _client
    if _client is not None:
        return _client
    try:
        import redis
        client = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        client.ping()  # test the connection
        _client = client
        logger.info(f"Redis connected: {REDIS_URL}")
        return _client
    except Exception as e:
        logger.warning(f"Redis not available ({e}) — falling back to in-memory chat history")
        return None


def get_chat_history(session_id: str) -> list:
    """Load chat history from Redis. Returns [] if not found or Redis unavailable."""
    client = _get_client()
    if client is None:
        return []
    try:
        raw = client.get(f"chat_history:{session_id}")
        if raw:
            return json.loads(raw)
        return []
    except Exception as e:
        logger.warning(f"Redis get failed for {session_id}: {e}")
        return []


def save_chat_history(session_id: str, history: list) -> None:
    """Persist chat history to Redis with 24h TTL. No-op if Redis unavailable."""
    client = _get_client()
    if client is None:
        return
    try:
        client.setex(
            f"chat_history:{session_id}",
            CHAT_HISTORY_TTL,
            json.dumps(history[-10:]),  # keep last 10 messages (5 turns)
        )
    except Exception as e:
        logger.warning(f"Redis save failed for {session_id}: {e}")


def delete_chat_history(session_id: str) -> None:
    """Delete chat history from Redis. No-op if Redis unavailable."""
    client = _get_client()
    if client is None:
        return
    try:
        client.delete(f"chat_history:{session_id}")
    except Exception as e:
        logger.warning(f"Redis delete failed for {session_id}: {e}")
