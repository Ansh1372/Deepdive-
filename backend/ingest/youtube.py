import os
from google import genai

def get_youtube_transcript(video_url: str) -> str:
    """Extract transcript or detailed summary from YouTube using Gemini."""
    # Ensure it's a full URL so Gemini can access it
    url = video_url
    if "youtube.com" not in url and "youtu.be" not in url:
        url = f"https://www.youtube.com/watch?v={video_url}"

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY environment variable is not set. "
            "Please provide a Gemini API key to enable YouTube processing."
        )

    try:
        client = genai.Client(api_key=api_key)
        
        prompt = (
            f"Please provide a full, detailed transcript for this YouTube video. "
            f"If a transcript is not available, provide a very detailed summary "
            f"of all the information spoken and shown in the video. Video URL: {url}"
        )

        result = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt]
        )
        
        text = result.text.strip()
        if not text:
            raise ValueError("Gemini returned an empty response.")
            
        return text

    except Exception as e:
        raise ValueError(f"Could not process YouTube video with Gemini. Try another video or a webpage/PDF. ({type(e).__name__}: {str(e)})")
