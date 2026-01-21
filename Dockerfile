# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /src

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    postgresql-client \
    curl \
    ffmpeg \
    aria2 \
    libffi-dev \
    libssl-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install -U yt-dlp


# Copy application files (refactored modules)
COPY api.py .
COPY main.py .
COPY run_api.sh .

# Copy module directories
COPY src/ ./src/

# Make run_api.sh executable
RUN chmod +x run_api.sh

# Set environment variables (can be overridden at runtime)
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/src

# Expose port for FastAPI
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run both Telegram bot and FastAPI server
CMD ["./run_api.sh"]

