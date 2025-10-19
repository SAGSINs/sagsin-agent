# Multi-stage build for Python gRPC application
# Supports both metric-agent and file-agent via AGENT_MODE env var
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and merge requirements from both agents
COPY metric-agent/requirements.txt ./requirements-metric.txt
COPY file-agent/requirements.txt ./requirements-file.txt

# Combine and deduplicate requirements
RUN cat requirements-metric.txt requirements-file.txt | sort -u > requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim as production

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping \
    iproute2 \
    net-tools \
    iperf3 \
    dnsutils \
 && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Add local bin to PATH
ENV PATH=/root/.local/bin:$PATH

# Copy both agents
COPY metric-agent/ ./metric-agent/
COPY file-agent/ ./file-agent/

# Create necessary directories
RUN mkdir -p /topology \
    /app/file-agent/send-file \
    /app/file-agent/receive-file \
    /app/file-agent/relay-cache

# Metric agent settings
ENV GRPC_TARGET=192.168.100.10:50051
ENV INTERVAL_SEC=5
ENV RETRY_BACKOFF_SEC=2
ENV MAX_BACKOFF_SEC=30
ENV TOPOLOGY_FILE=/topology/topology.json

# File agent settings
ENV NODE_HOST=0.0.0.0
ENV NODE_PORT=7000
ENV HEURISTIC_ADDR=192.168.100.3:50052

# Copy entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Expose file agent port
EXPOSE 7000

# Use entrypoint to run both agents
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]