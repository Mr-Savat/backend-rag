FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python packages with optimizations
RUN pip install --no-cache-dir -r requirements.txt && \
    # Clean up unnecessary files to reduce image size
    find /usr/local/lib/python3.12/site-packages -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.12/site-packages -type d -name "test" -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.12/site-packages -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run the application
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]