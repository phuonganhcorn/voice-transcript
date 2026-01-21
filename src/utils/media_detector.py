from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument, DocumentAttributeAudio

def is_photo(media) -> bool:
    """Check if media is photo"""
    if isinstance(media, MessageMediaPhoto):
        return True
    if isinstance(media, MessageMediaDocument):
        doc = media.document
        if doc:
            if hasattr(doc, 'mime_type') and doc.mime_type and doc.mime_type.lower().startswith('image/'):
                return True
            if hasattr(doc, 'attributes'):
                image_exts = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico']
                for attr in doc.attributes:
                    if hasattr(attr, 'file_name') and attr.file_name:
                        if any(attr.file_name.lower().endswith(ext) for ext in image_exts):
                            return True
    return False

def is_voice_or_audio(media) -> bool:
    """Check if media is voice message or audio file"""
    if not isinstance(media, MessageMediaDocument):
        return False
    
    doc = media.document
    if not doc:
        return False
    
    # Check mime type
    if hasattr(doc, 'mime_type') and doc.mime_type:
        if doc.mime_type.startswith('audio/'):
            return True
    
    # Check attributes for voice or audio
    if hasattr(doc, 'attributes'):
        for attr in doc.attributes:
            # Voice messages have DocumentAttributeAudio with voice=True
            if isinstance(attr, DocumentAttributeAudio):
                return True
            # Check file extensions
            if hasattr(attr, 'file_name') and attr.file_name:
                audio_exts = ['.m4a', '.mp3', '.wav', '.ogg', '.flac', '.aac', '.opus']
                if any(attr.file_name.lower().endswith(ext) for ext in audio_exts):
                    return True
    
    return False

def is_video(media) -> bool:
    """Check if media is video file"""
    if not isinstance(media, MessageMediaDocument):
        return False
    
    doc = media.document
    if not doc:
        return False
    
    # Check mime type for video
    if hasattr(doc, 'mime_type') and doc.mime_type:
        if doc.mime_type.startswith('video/'):
            return True
    
    # Check file extensions for video
    if hasattr(doc, 'attributes'):
        for attr in doc.attributes:
            if hasattr(attr, 'file_name') and attr.file_name:
                video_exts = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm', '.m4v', '.mpeg', '.mpg']
                if any(attr.file_name.lower().endswith(ext) for ext in video_exts):
                    return True
    
    return False

