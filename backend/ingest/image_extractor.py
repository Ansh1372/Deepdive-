import os
import re
import requests
from backend.utils.logger import get_logger

logger = get_logger("image_extractor")


def _get_gemini_client():
    """Get Gemini client using the new google-genai SDK."""
    try:
        from google import genai
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            return None
        client = genai.Client(api_key=api_key)
        return client
    except ImportError:
        logger.warning("google-genai not installed — skipping image processing")
        return None


def extract_images_from_html(html: str, base_url: str) -> list:
    """Extract image URLs from HTML content."""
    img_pattern = r'<img[^>]+src=["\']([^"\']+)["\']'
    img_urls = re.findall(img_pattern, html)

    # Filter: only keep meaningful images (skip icons, logos, tiny images)
    filtered = []
    for url in img_urls:
        if not url.startswith("http"):
            if url.startswith("/"):
                from urllib.parse import urlparse
                parsed = urlparse(base_url)
                url = f"{parsed.scheme}://{parsed.netloc}{url}"
            else:
                url = f"{base_url.rstrip('/')}/{url}"

        skip_patterns = ["icon", "logo", "avatar", "favicon", "sprite", "pixel", "tracking"]
        if any(p in url.lower() for p in skip_patterns):
            continue

        filtered.append(url)

    logger.info(f"Found {len(filtered)} content images (from {len(img_urls)} total)")
    return filtered[:3]


def describe_image(image_url: str) -> str:
    """Use Gemini Vision to describe an image."""
    client = _get_gemini_client()
    if not client:
        return ""

    try:
        logger.debug(f"Describing image: {image_url[:60]}...")

        response = requests.get(image_url, timeout=10)
        if response.status_code != 200:
            logger.debug(f"  Failed to download image: {response.status_code}")
            return ""

        from google.genai import types

        image_part = types.Part.from_bytes(
            data=response.content,
            mime_type=response.headers.get("content-type", "image/jpeg"),
        )

        result = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=["Describe this image in detail. Focus on any data, charts, diagrams, or informational content shown.", image_part],
        )

        description = result.text.strip()
        logger.info(f"  Image described: {len(description)} chars")
        return description

    except Exception as e:
        logger.error(f"  Image description failed: {e}")
        return ""


def extract_image_descriptions(html: str, base_url: str) -> str:
    """Extract and describe all content images from a page."""
    import time

    if not os.getenv("GEMINI_API_KEY"):
        return ""

    img_urls = extract_images_from_html(html, base_url)
    if not img_urls:
        return ""

    logger.info(f"Processing {len(img_urls)} images with Gemini Vision")
    descriptions = []

    for i, url in enumerate(img_urls):
        if i > 0:
            time.sleep(4)  # Respect free tier rate limits
        desc = describe_image(url)
        if desc:
            descriptions.append(f"[Image content]: {desc}")

    combined = "\n\n".join(descriptions)
    logger.info(f"Total image descriptions: {len(combined)} chars")
    return combined
