#!/bin/bash

# Script to run FastAPI server

echo "🚀 Starting FastAPI server..."
echo "📝 API Documentation will be available at: http://localhost:8000/docs"
echo "🔧 Alternative docs at: http://localhost:8000/redoc"
echo ""

# Check if running in Docker (check for /.dockerenv or DOCKER env var)

echo "🐳 Running in Docker - skipping Telegram bot"
echo "📡 Starting FastAPI server only..."

echo "🔎 yt-dlp version: $(yt-dlp --version 2>/dev/null || echo 'yt-dlp not found')"
# Run uvicorn without reload in Docker
uvicorn api:app --host 0.0.0.0 --port 8000


