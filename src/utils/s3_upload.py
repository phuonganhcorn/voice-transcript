"""
S3 upload module.
Handles uploading files (images, videos, audio) to AWS S3.
"""
import os
import logging
import boto3
import mimetypes
from src.config import Config

logger = logging.getLogger(__name__)

# Initialize S3 client
s3_client = None

def init_s3_client():
    """Initialize S3 client from config."""
    global s3_client
    if Config.S3_ACCESS_KEY_ID and Config.S3_SECRET_ACCESS_KEY:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=Config.S3_ACCESS_KEY_ID,
            aws_secret_access_key=Config.S3_SECRET_ACCESS_KEY,
            region_name=Config.S3_REGION,
        )
        logger.info("S3 client initialized")
    else:
        logger.warning("S3 credentials not set. S3 upload will not be available.")


def upload_file_to_s3(local_path, s3_path, content_type=None):
    """
    Upload file to S3.
    
    Args:
        local_path: Path to local file
        s3_path: S3 key (path + filename, e.g., "videos/video.mp4")
        content_type: Optional content type. If not provided, will be auto-detected
    
    Returns:
        str: Public URL of uploaded file, or None on error
    """
    if not s3_client:
        logger.error("S3 client not initialized")
        return None
    
    if not os.path.exists(local_path):
        logger.error(f"File not found: {local_path}")
        return None
    
    try:
        # Auto-detect content type if not provided
        if content_type is None:
            content_type, _ = mimetypes.guess_type(local_path)
            if content_type is None:
                # Fallback based on extension
                ext = os.path.splitext(local_path)[1].lower()
                if ext == '.webp':
                    content_type = 'image/webp'
                elif ext in ['.mp4', '.mov', '.avi', '.wmv', '.webm']:
                    content_type = 'video/mp4'
                elif ext in ['.mp3', '.wav', '.m4a']:
                    content_type = 'audio/mpeg'
                elif ext in ['.txt', '.text']:
                    content_type = 'text/plain; charset=utf-8'
                else:
                    content_type = 'application/octet-stream'
        
        # Ensure UTF-8 charset for text files
        if content_type and 'text' in content_type and 'charset' not in content_type:
            content_type = f"{content_type}; charset=utf-8"
        
        # Upload file with proper Content-Type
        s3_client.upload_file(
            Filename=local_path,
            Bucket=Config.S3_BUCKET,
            Key=s3_path,
            ExtraArgs={"ContentType": content_type}
        )
        
        # Generate public URL
        url = f"https://{Config.S3_BUCKET}.s3.{Config.S3_REGION}.amazonaws.com/{s3_path}"
        logger.info(f"Uploaded file to S3: {url}")
        return url
        
    except Exception as e:
        logger.error(f"Error uploading file to S3: {e}")
        return None


def upload_image_webp(local_path, s3_path):
    """
    Upload WEBP image to S3.
    
    Args:
        local_path: Path to local WEBP file
        s3_path: S3 key (e.g., "images/pic.webp")
    
    Returns:
        str: Public URL of uploaded file, or None on error
    """
    return upload_file_to_s3(local_path, s3_path, content_type="image/webp")


def upload_video(local_path, s3_path):
    """
    Upload video to S3.
    
    Args:
        local_path: Path to local video file
        s3_path: S3 key (e.g., "videos/video.mp4")
    
    Returns:
        str: Public URL of uploaded file, or None on error
    """
    return upload_file_to_s3(local_path, s3_path)


def upload_audio(local_path, s3_path):
    """
    Upload audio file to S3.
    
    Args:
        local_path: Path to local audio file
        s3_path: S3 key (e.g., "audio/audio.mp3")
    
    Returns:
        str: Public URL of uploaded file, or None on error
    """
    return upload_file_to_s3(local_path, s3_path)

