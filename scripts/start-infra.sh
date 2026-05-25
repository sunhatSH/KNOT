#!/bin/bash
# Start infrastructure services
echo "Starting KNOT infrastructure..."
docker compose up -d
echo "Waiting for services..."
# Wait for PostgreSQL
until docker compose exec postgres pg_isready -U knot 2>/dev/null; do
  sleep 2
done
echo "PostgreSQL is ready"
echo "All services started. Run 'docker compose logs -f' to follow logs."
