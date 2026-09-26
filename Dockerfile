# ==============================================================================
# Stage 1: Build React 19 Frontend Web Visualizer
# ==============================================================================
FROM node:22-alpine AS frontend-builder

WORKDIR /app/web

# Install frontend dependencies
COPY web/package.json web/package-lock.json* ./
RUN npm ci || npm install

# Copy frontend source files and build production static bundle
COPY web/ ./
RUN npm run build

# ==============================================================================
# Stage 2: Production Python 3.13 Runtime
# ==============================================================================
FROM python:3.13-slim AS runtime

LABEL org.opencontainers.image.title="NouSetsu"
LABEL org.opencontainers.image.description="Agentic Document-Level Cross-Chapter Novel Translation System"
LABEL org.opencontainers.image.licenses="MIT"

# Install system utilities (curl for container healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Astral uv package manager for fast, reliable dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Environment configurations
ENV PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1 \
    HOST=0.0.0.0 \
    PORT=5173 \
    NOVEL_PROJECTS_DIR=/app/project

WORKDIR /app

# Copy project definition and source code for installation
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install dependencies and nouSetsu package into system python
RUN uv pip install --system -e .

# Copy built web frontend assets from Stage 1
COPY --from=frontend-builder /app/web/dist ./web/dist
COPY web/package.json ./web/package.json

# Ensure persistent projects directory exists
RUN mkdir -p /app/project

# Expose web visualizer port
EXPOSE 5173

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5173/api/active-project || exit 1

# Default entrypoint and command to run Web Studio
ENTRYPOINT ["nousetsu"]
CMD ["web", "--host", "0.0.0.0", "--port", "5173", "--no-open-browser"]
