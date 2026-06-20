import yt_dlp
import requests
import json

def get_youtube_transcript(video_url: str) -> str:
    """Extract transcript from YouTube using yt-dlp to bypass blocks."""
    url = video_url
    if "youtube.com" not in url and "youtu.be" not in url:
        url = f"https://www.youtube.com/watch?v={video_url}"

    try:
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
            
        # Try to get english manual subtitles, fallback to auto captions
        subs = info.get('subtitles', {}).get('en') or info.get('automatic_captions', {}).get('en')
        
        if not subs:
            raise ValueError("No English captions (manual or auto) found for this video.")
            
        # Find the JSON3 format which is structured and easy to parse
        json3_url = next((s['url'] for s in subs if s['ext'] == 'json3'), None)
        
        if not json3_url:
            raise ValueError("Could not find a parseable transcript format (JSON3).")
            
        # Download and parse the JSON3 transcript
        response = requests.get(json3_url)
        response.raise_for_status()
        data = response.json()
        
        # Extract text segments from events
        events = data.get('events', [])
        transcript_pieces = []
        for e in events:
            if 'segs' in e:
                for seg in e['segs']:
                    text = seg.get('utf8', '').replace('\n', ' ')
                    if text.strip():
                        transcript_pieces.append(text)
                        
        transcript_text = ' '.join(transcript_pieces)
        
        # Clean up weird spacing from youtube JSON3 (e.g. "I  think  if  people")
        import re
        transcript_text = re.sub(r'\s+', ' ', transcript_text).strip()
        
        if not transcript_text:
            raise ValueError("Transcript is empty.")
            
        return transcript_text

    except yt_dlp.utils.DownloadError as e:
        err_str = str(e).lower()
        if "private video" in err_str:
            raise ValueError("This video is private. Please try a different video.")
        elif "premieres in" in err_str:
            raise ValueError("This video has not premiered yet.")
        raise ValueError(f"Could not fetch video info. ({str(e)})")
        
    except Exception as e:
        raise ValueError(f"Could not fetch transcript for this video. Try a webpage/PDF instead. ({type(e).__name__}: {str(e)})")
