from datetime import datetime

def format_duration(seconds: int) -> str:
    """Format duration compactly: 2723 → 45m"""
    if seconds == 0:
        return "0m"
    
    mins = seconds // 60
    if mins < 60:
        return f"{mins}m"
    
    hours = mins // 60
    remaining_mins = mins % 60
    return f"{hours}h{remaining_mins}m" if remaining_mins > 0 else f"{hours}h"

def format_date_compact(timestamp: str) -> str:
    """Format date compactly: 2026-01-06T13:22:47 → 6/1"""
    try:
        dt = datetime.fromisoformat(timestamp)
        return f"{dt.day}/{dt.month}"
    except:
        return "N/A"

def truncate_with_ellipsis(text: str, max_len: int) -> str:
    """Smart truncate with ellipsis"""
    if len(text) <= max_len:
        return text
    return text[:max_len-3] + "..."

def format_source_emoji(source_type: str) -> str:
    """Get emoji for source type"""
    emoji_map = {
        "audio": "🎵",
        "video": "🎬",
        "voice_message": "🎤",
        "url": "🔗"
    }
    return emoji_map.get(source_type, "📄")

