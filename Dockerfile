# GTM-OS — Multi-stage Docker build
# Stage 1: Build frontend
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Python application
FROM python:3.11-slim
WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dep resolution
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml .
COPY src/ src/
COPY primitives/ primitives/

# Install Python deps
RUN uv pip install --system -e ".[composio,vec]"

# Copy built frontend
COPY --from=frontend-build /app/frontend/dist /app/src/gtm_os/server/frontend_dist

# Create data directory
RUN mkdir -p /app/data

# Environment
ENV GTM_OS_DATA_DIR=/app/data
ENV GTM_OS_PRIMITIVES_DIR=/app/primitives

EXPOSE 3000

CMD ["gtm-os", "start", "--host", "0.0.0.0", "--no-open"]
