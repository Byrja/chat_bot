# Stage 1: Build frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/webapp/frontend
COPY webapp/frontend/package.json webapp/frontend/yarn.lock ./
RUN yarn install --frozen-lockfile
COPY webapp/frontend/ ./
RUN yarn build

# Stage 2: Python runtime
FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy Python dependencies first (cache layer)
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --extra webapp --extra ai --no-dev

# Copy application code˚
COPY mamoolyaBot/ ./mamoolyaBot/
COPY webapp/backend/ ./webapp/backend/
COPY bot.py ./

# Install supervisor for running multiple processes
RUN apt-get update && apt-get install -y supervisor && rm -rf /var/lib/apt/lists/*
COPY supervisord.conf .

# Copy built frontend
COPY --from=frontend-build /app/webapp/frontend/build ./webapp/frontend/build

# Set environment defaults
ENV PYTHONUNBUFFERED=1
ENV DB_PATH=/data/chat.db
ENV STATIC_WEB_PATH=/app/webapp/frontend/build

# Create data directory for SQLite
RUN mkdir -p /data

EXPOSE 5001

# Run both bot and webapp via supervisord
CMD ["supervisord", "-c", "supervisord.conf"]
