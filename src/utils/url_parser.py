import re

def extract_video_url(text: str) -> str:
    """Extract video URL from text"""
    if not text:
        return None

    patterns = [
        # YouTube
        (
            r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
            lambda m: f"https://www.youtube.com/watch?v={m.group(1)}"
        ),
        # Vimeo
        (
            r'(?:https?://)?(?:www\.)?vimeo\.com/(\d+)',
            lambda m: f"https://vimeo.com/{m.group(1)}"
        ),
        # X/Twitter specific - match x.com/USERNAME/status/NUM and allow URLs with or without www
        (
            r'(https?://(?:www\.)?x\.com/[\w\d_]+/status/\d+)',
            lambda m: m.group(1)
        ),
        # twitter.com as well, for broader support (optional)
        (
            r'(https?://(?:www\.)?twitter\.com/[\w\d_]+/status/\d+)',
            lambda m: m.group(1)
        ),
        # Direct video file URLs
        (
            r'(https?://[^\s]+\.(mp4|mkv|webm|avi|mov|flv|wmv|m4v)(\?.*)?)',
            lambda m: m.group(1)
        )
    ]

    for pattern, formatter in patterns:
        # Ensure to match the entire URL, not just part (consider using findall if multiple URLs are present)
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return formatter(match)
    return None
