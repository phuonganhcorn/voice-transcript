import os
from dotenv import load_dotenv

# Load .env file (try multiple paths)
load_dotenv()  # Current directory
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))  # Project root
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))  # Parent directory

class Config:
    """Configuration class to hold all config variables"""
    
    # Telegram API
    API_ID = int(os.getenv("API_ID", "39142499"))
    API_HASH = os.getenv("API_HASH", "7842d61250e35d0b734e07bd1ad7be3b")
    SESSION_NAME = os.getenv("SESSION_NAME", "session_name")
    
    # OpenRouter API
    OPENROUTER_API_KEY = "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"
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")
    
    # File paths
    USERS_FILE = os.getenv("USERS_FILE", "users.json")
    CONTEXT_DIR = os.getenv("CONTEXT_DIR", "user_contexts")
    
    # Limits
    MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "4096"))  # Telegram message limit
    MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "10"))  # Maximum file size for transcription
    
    # YouTube cookies file path (optional, for bypassing bot detection)
    YOUTUBE_COOKIES_FILE = os.getenv("YOUTUBE_COOKIES_FILE", None)  # Path to cookies.txt file
    YOUTUBE_COOKIES_FROM_BROWSER = os.getenv("YOUTUBE_COOKIES_FROM_BROWSER", None)  # Browser name: chrome, firefox, edge
    YOUTUBE_PROXY = os.getenv("YOUTUBE_PROXY", None)  # Proxy URL (e.g., http://proxy:port) for residential IP
    
    # S3 Configuration
    S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID")
    S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY")
    S3_BUCKET = os.getenv("S3_BUCKET")
    S3_REGION = os.getenv("S3_REGION", "us-east-1")
    
    # Database Configuration (Supabase)
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
    DATABASE_URL = os.getenv("DATABASE_URL")  # Supabase PostgreSQL connection string
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")

# Telegram API
API_ID = Config.API_ID
API_HASH = Config.API_HASH
SESSION_NAME = Config.SESSION_NAME

# OpenRouter API
OPENROUTER_API_KEY = Config.OPENROUTER_API_KEY
OPENROUTER_MODEL = Config.OPENROUTER_MODEL

# Debug: Print config status
print(f"🔧 Config loaded:")
print(f"   API_ID: {API_ID}")
print(f"   OPENROUTER_MODEL: {OPENROUTER_MODEL}")
print(f"   OPENROUTER_API_KEY: {'✅ SET' if OPENROUTER_API_KEY else '❌ NOT SET'}")
if OPENROUTER_API_KEY:
    print(f"   Key preview: {OPENROUTER_API_KEY[:20]}...")
print(f"   S3_BUCKET: {'✅ SET' if Config.S3_BUCKET else '❌ NOT SET'}")
print(f"   SUPABASE_URL: {'✅ SET' if Config.SUPABASE_URL else '❌ NOT SET'}")
print(f"   DATABASE_URL: {'✅ SET' if Config.DATABASE_URL else '❌ NOT SET (need DB_PASSWORD)'}")

# File paths
USERS_FILE = Config.USERS_FILE
CONTEXT_DIR = Config.CONTEXT_DIR

# Limits
MAX_MESSAGE_LENGTH = Config.MAX_MESSAGE_LENGTH
MAX_FILE_SIZE_MB = Config.MAX_FILE_SIZE_MB

