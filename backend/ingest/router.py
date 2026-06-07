import os
from backend.ingest.youtube import get_youtube_transcript
from backend.ingest.webpage import get_webpage_text
from backend.ingest.pdf import get_pdf_text
from backend.utils.logger import get_logger

logger = get_logger("ingest.router")


def ingest(source: str) -> str:
    """Detect source type and route to correct parser."""
    logger.info(f"Ingesting source: '{source}'")

    if source.endswith(".pdf"):
        logger.info("Detected: PDF file")
        text = get_pdf_text(source)
    elif "youtube.com" in source or "youtu.be" in source:
        logger.info("Detected: YouTube URL")
        text = get_youtube_transcript(source)
    elif source.startswith("http"):
        logger.info("Detected: Web page URL")
        text = get_webpage_text(source)
    elif os.path.exists(source) or os.path.exists(os.path.expanduser(source)):
        logger.info("Detected: Local file")
        text = get_pdf_text(source)
    else:
        logger.error(f"Unknown source type: {source}")
        raise ValueError(f"Unknown source type: {source}")

    logger.info(f"Ingestion complete: {len(text)} characters extracted")
    return text
