from youtube_transcript_api import YouTubeTranscriptApi


def get_youtube_transcript(video_url: str) -> str:
    """Extract transcript from YouTube URL or video ID."""
    if "youtube.com" in video_url or "youtu.be" in video_url:
        if "v=" in video_url:
            video_id = video_url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in video_url:
            video_id = video_url.split("youtu.be/")[1].split("?")[0]
        else:
            video_id = video_url
    else:
        video_id = video_url

    try:
        # youtube-transcript-api 0.6.x — try English first, then any language
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(
                video_id,
                languages=["en", "en-US", "en-GB", "a.en"],
            )
        except Exception:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)

        return " ".join(snippet["text"] for snippet in transcript_list)

    except Exception as e:
        err_str = str(e).lower()

        # Network / SSL errors — typically a platform firewall blocking YouTube
        if any(x in err_str for x in ["ssl", "connectionpool", "max retries", "eof", "network", "timeout"]):
            raise ValueError(
                "YouTube is not accessible from this server. "
                "Try pasting a webpage URL or uploading a PDF instead."
            )

        # Video has no transcript / captions disabled
        if any(x in err_str for x in ["transcript", "disabled", "no transcript", "could not retrieve"]):
            raise ValueError(
                "This video has no captions or transcripts available. "
                "Try a video that has subtitles enabled, or use a webpage/PDF."
            )

        # Video is private, age-restricted, or unavailable
        if any(x in err_str for x in ["private", "unavailable", "not available", "age"]):
            raise ValueError(
                "This video is private, age-restricted, or unavailable. "
                "Please try a different video."
            )

        # Generic fallback
        raise ValueError(
            f"Could not fetch transcript for this video. "
            f"Try a different video or use a webpage/PDF instead. ({type(e).__name__})"
        )
