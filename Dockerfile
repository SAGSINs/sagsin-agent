# Multi-stage build for Python gRPC application
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim as production

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Add local bin to PATH
ENV PATH=/root/.local/bin:$PATH

# Copy proto files first
COPY proto/ ./proto/

# Copy application code
COPY agent/ ./agent/

# Set environment variables with defaults
ENV GRPC_TARGET=192.168.100.10:50051
ENV INTERVAL_SEC=5
ENV RETRY_BACKOFF_SEC=2
ENV MAX_BACKOFF_SEC=30

# Expose gRPC port
EXPOSE 50051

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.settimeout(3); s.connect(('localhost', 50051)); s.close()" || exit 1

# Run the application
CMD ["python", "-m", "agent.agent"]