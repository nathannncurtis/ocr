FROM python:3.11-slim

# Install system dependencies including jbig2enc
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    jbig2 \
    qpdf \
    ghostscript \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (for better Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Copy jbig2topdf.py to expected location
RUN cp jbig2enc/jbig2topdf.py /usr/local/bin/jbig2topdf.py

# Set environment variable for Docker detection
ENV DOCKER_CONTAINER=1

# Create input/output directories
RUN mkdir -p /input /output

# Default command
CMD ["python", "FINAL.py", "--help"]