import os
import re
import requests
import yt_dlp
from backend.utils.logger import get_logger

logger = get_logger("youtube")


def _extract_video_id(url: str) -> str:
    """Extract YouTube video ID from any URL format."""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return url  # assume it's already a video ID


def _get_transcript_via_supadata(video_id: str) -> str:
    """
    Fetch transcript using Supadata proxy API.
    Works on HuggingFace Spaces because Supadata's servers make the YouTube request.
    Requires SUPADATA_API_KEY env var (free tier: 100 requests/day).
    Sign up at: https://supadata.ai
    """
    api_key = os.getenv("SUPADATA_API_KEY")
    if not api_key:
        raise EnvironmentError("SUPADATA_API_KEY not set")

    logger.info(f"[YOUTUBE] Trying Supadata transcript proxy for video: {video_id}")
    resp = requests.get(
        "https://api.supadata.ai/v1/youtube/transcript",
        params={"videoId": video_id, "lang": "en", "text": "true"},
        headers={"x-api-key": api_key},
        timeout=30,
    )

    if resp.status_code == 402:
        raise ValueError("Supadata free quota exceeded for today. Try again tomorrow or use a local instance.")
    if resp.status_code == 404:
        raise ValueError("No transcript available for this video (no captions found).")
    resp.raise_for_status()

    data = resp.json()
    content = data.get("content", "")
    if not content or not content.strip():
        raise ValueError("Supadata returned an empty transcript.")

    logger.info(f"[YOUTUBE] Supadata transcript fetched: {len(content)} chars")
    return content.strip()


def _get_transcript_via_ytdlp(url: str) -> str:
    """
    Fetch transcript directly using yt-dlp.
    Works locally but blocked on HuggingFace Spaces.
    """
    logger.info(f"[YOUTUBE] Trying yt-dlp for: {url}")
    ydl_opts = {
        'writesubtitles': True,
        'writeautomaticsub': True,
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'extractor_retries': 1,
        'socket_timeout': 10,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    subs = info.get('subtitles', {}).get('en') or info.get('automatic_captions', {}).get('en')
    if not subs:
        raise ValueError("No English captions (manual or auto) found for this video.")

    json3_url = next((s['url'] for s in subs if s['ext'] == 'json3'), None)
    if not json3_url:
        raise ValueError("Could not find a parseable transcript format (JSON3).")

    response = requests.get(json3_url, timeout=15)
    response.raise_for_status()
    data = response.json()

    transcript_pieces = []
    for e in data.get('events', []):
        if 'segs' in e:
            for seg in e['segs']:
                text = seg.get('utf8', '').replace('\n', ' ')
                if text.strip():
                    transcript_pieces.append(text)

    transcript_text = re.sub(r'\s+', ' ', ' '.join(transcript_pieces)).strip()
    if not transcript_text:
        raise ValueError("Transcript is empty.")

    logger.info(f"[YOUTUBE] yt-dlp transcript fetched: {len(transcript_text)} chars")
    return transcript_text


def get_youtube_transcript(video_url: str) -> str:
    """
    Extract transcript from a YouTube video.

    Strategy:
    1. Try Supadata proxy API (works everywhere, including HuggingFace Spaces).
       Requires SUPADATA_API_KEY env var.
    2. Fall back to yt-dlp direct (works locally, blocked on HF).
    """
    if "youtube.com" not in video_url and "youtu.be" not in video_url:
        video_url = f"https://www.youtube.com/watch?v={video_url}"

    video_id = _extract_video_id(video_url)

    # --- Strategy 1: Supadata (proxy — works on HF) ---
    supadata_key = os.getenv("SUPADATA_API_KEY")
    if supadata_key:
        try:
            return _get_transcript_via_supadata(video_id)
        except EnvironmentError:
            pass  # key not set, fall through
        except ValueError as e:
            # Meaningful user-facing errors from Supadata (quota, no captions, etc.)
            raise
        except Exception as e:
            logger.warning(f"[YOUTUBE] Supadata failed: {e}. Falling back to yt-dlp.")

    # --- Strategy 2: yt-dlp (direct — works locally) ---
    try:
        return _get_transcript_via_ytdlp(video_url)
    except yt_dlp.utils.DownloadError as e:
        err_str = str(e).lower()
        if "private video" in err_str:
            raise ValueError("This video is private. Please try a different video.")
        elif "premieres in" in err_str:
            raise ValueError("This video has not premiered yet.")
        raise ValueError(f"Could not fetch video info. ({str(e)})")
    except Exception as e:
        raise ValueError(
            f"Could not fetch transcript. On HuggingFace, add a SUPADATA_API_KEY to your secrets. "
            f"On local Docker, YouTube works without any extra keys. ({type(e).__name__}: {str(e)})"
        )
