import trafilatura
from backend.ingest.image_extractor import extract_image_descriptions
from backend.utils.logger import get_logger

logger = get_logger("ingest.webpage")


def get_webpage_text(url: str) -> str:
    """Extract main text content + image descriptions from any web page."""
    logger.info(f"Fetching webpage: {url}")

    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise ValueError(f"Could not fetch URL: {url}")

    # Extract text
    text = trafilatura.extract(downloaded)
    if not text:
        raise ValueError(f"Could not extract text from: {url}")

    logger.info(f"Extracted {len(text)} chars of text")

    # Extract image descriptions (if Gemini key is set)
    image_text = extract_image_descriptions(downloaded, url)
    if image_text:
        text = text + "\n\n--- Image Content ---\n\n" + image_text
        logger.info(f"Added {len(image_text)} chars of image descriptions")

    return text
