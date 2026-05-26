# KNOT Production Deployment

## Overview

Production deployment for KNOT (Knowledge-enhanced Task Orchestration for LLM Tuning) using Docker Compose. This setup runs the FastAPI backend, React frontend, and all infrastructure services (PostgreSQL, Milvus, etcd, MinIO, Redis) in containers.

## Prerequisites

- Docker >= 24.0
- Docker Compose >= 2.20

## Quick Start

1. Copy the environment file and configure required variables:

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and set at minimum:
   - `DEEPSEEK_API_KEY` -- your DeepSeek API key
   - `JWT_SECRET_KEY` -- a random secret for JWT signing

2. Start all services:

   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

3. Access the application:

   - Frontend: http://localhost
   - API: http://localhost:8000
   - API docs: http://localhost:8000/docs

## Stopping

```bash
docker compose -f docker-compose.prod.yml down
```

To also remove volumes (data will be lost):

```bash
docker compose -f docker-compose.prod.yml down -v
```

## Logs

```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f frontend
```

## Building Images Separately

```bash
# Backend
docker build -f Dockerfile.backend -t knot-backend .

# Frontend
docker build -f Dockerfile.frontend -t knot-frontend .
```

## Environment Variables Reference

| Variable | Description | Default |
|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API key | (required) |
| `DEEPSEEK_BASE_URL` | DeepSeek API base URL | `https://api.deepseek.com` |
| `DATABASE_URL` | Database connection string | `postgresql+asyncpg://knot:knot_dev@postgres:5432/knot` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `MILVUS_HOST` | Milvus hostname | `milvus` |
| `MILVUS_PORT` | Milvus port | `19530` |
| `JWT_SECRET_KEY` | Secret for JWT signing | (change from default) |
| `JWT_ALGORITHM` | JWT signing algorithm | `HS256` |
| `JWT_EXPIRE_MINUTES` | JWT token expiry | `1440` |
| `DEBUG` | Enable debug mode | `false` |

## Data Persistence

All persistent data is stored in Docker named volumes:

- `pgdata` -- PostgreSQL database
- `milvusdata` -- Milvus vector store
- `etcddata` -- etcd metadata
- `miniodata` -- MinIO object storage
- `redisdata` -- Redis cache

Volumes are not removed on `docker compose down`. Use `docker compose down -v` to delete them.
