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
        # youtube-transcript-api 0.6.x uses get_transcript() class method
        # Falls back to any available language if English not found
        transcript_list = YouTubeTranscriptApi.get_transcript(
            video_id,
            languages=["en", "en-US", "en-GB", "a.en"],
        )
        return " ".join(snippet["text"] for snippet in transcript_list)
    except Exception:
        try:
            # Last resort: fetch whatever transcript is available in any language
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            return " ".join(snippet["text"] for snippet in transcript_list)
        except Exception as e:
            raise ValueError(f"Could not fetch transcript for video {video_id}: {e}")
