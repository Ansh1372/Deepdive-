import requests
import trafilatura
from backend.generation.chain import get_llm
from backend.utils.logger import get_logger

logger = get_logger("web_search")

DUCKDUCKGO_URL = "https://html.duckduckgo.com/html/"


def _search_duckduckgo(query: str, max_results: int = 3) -> list:
    """Search DuckDuckGo and return a list of result URLs."""
    logger.info(f"DuckDuckGo search: '{query}'")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.post(
            DUCKDUCKGO_URL,
            data={"q": query},
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()

        # Extract URLs from DuckDuckGo HTML results
        import re
        # DuckDuckGo uses redirect links, extract the actual URLs
        urls = re.findall(r'href="(https?://[^"]+)"', resp.text)

        # Filter out DuckDuckGo internal links
        filtered = []
        for url in urls:
            if "duckduckgo.com" in url:
                continue
            if any(skip in url for skip in ["ad_domain", "javascript:", "mailto:"]):
                continue
            filtered.append(url)

        unique_urls = list(dict.fromkeys(filtered))[:max_results]
        logger.info(f"Found {len(unique_urls)} search results")
        return unique_urls

    except Exception as e:
        logger.error(f"DuckDuckGo search failed: {e}")
        return []


def _fetch_page_content(url: str, max_chars: int = 2000) -> str:
    """Fetch and extract text content from a URL."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded)
            if text and len(text) > 50:
                return text[:max_chars]
    except Exception as e:
        logger.debug(f"Failed to fetch {url}: {e}")
    return ""


def web_search_fallback(question: str) -> str:
    """Search the internet for additional context when document retrieval is insufficient."""
    logger.info(f"Web search fallback for: '{question[:60]}...'")

    llm = get_llm()

    # Generate a search-optimized query
    prompt = f"""Convert this question into a concise web search query (max 8 words).
Focus on the specific information needed.
Question: {question}
Search query:"""

    response = llm.invoke(prompt)
    search_query = response.content.strip().strip('"').strip("'")
    logger.info(f"Search query: '{search_query}'")

    # Search DuckDuckGo
    urls = _search_duckduckgo(search_query)

    if not urls:
        # Fallback to Wikipedia direct
        logger.info("DuckDuckGo returned no results, trying Wikipedia direct")
        wiki_url = f"https://en.wikipedia.org/wiki/{search_query.replace(' ', '_')}"
        content = _fetch_page_content(wiki_url, max_chars=3000)
        if content:
            return content
        return ""

    # Fetch content from top results
    all_content = []
    for url in urls:
        logger.debug(f"Fetching: {url}")
        content = _fetch_page_content(url, max_chars=1500)
        if content:
            all_content.append(f"[Source: {url}]\n{content}")
            if len("\n\n".join(all_content)) > 3000:
                break

    if all_content:
        combined = "\n\n---\n\n".join(all_content)
        logger.info(f"Web search collected {len(combined)} chars from {len(all_content)} sources")
        return combined[:4000]

    logger.warning("Web search returned no useful content")
    return ""
