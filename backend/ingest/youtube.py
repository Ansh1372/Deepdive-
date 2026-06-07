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
        transcript_list = YouTubeTranscriptApi().fetch(video_id)
        return " ".join(snippet.text for snippet in transcript_list)
    except Exception as e:
        raise ValueError(f"Could not fetch transcript for video {video_id}: {e}")
