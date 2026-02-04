FROM python:3.11-slim-bookworm

WORKDIR /app

# Install system dependencies for libtorrent and ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libboost-system-dev \
    libboost-python-dev \
    libboost-chrono-dev \
    libboost-random-dev \
    libssl-dev \
    pkg-config \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies (libtorrent via pip)
RUN pip install --no-cache-dir -r requirements.txt || \
    (pip install --no-cache-dir fastapi uvicorn requests python-dotenv aiohttp beautifulsoup4 lxml && \
     echo "Note: libtorrent may need manual installation")

# Copy application code
COPY *.py ./

# Expose port
EXPOSE 8000

# Create cache directory for torrents
RUN mkdir -p /tmp/streamtv_torrents

# Health check (utilise python au lieu de curl)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

# Run the application
CMD ["python", "main_production.py"]
