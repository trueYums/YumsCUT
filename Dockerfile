FROM python:3.11-slim

# System dependencies: ffmpeg + fonts for drawtext
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        fonts-dejavu-core \
        fontconfig \
        && fc-cache -f \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Data directory (overridden by the named volume at runtime)
RUN mkdir -p /data

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
