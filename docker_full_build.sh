#!/bin/bash

# Stop the container if it's running
docker stop cc-mobile-api 2>/dev/null || true

# Remove the container if it exists
docker rm cc-mobile-api 2>/dev/null || true

# Optional: prune unused images/layers safely (commented out)
# docker system prune -f

# Build the image
docker build -t cc-mobile-api .

# Run the container (single line so -p 8000:8000 is never dropped by shell line-continuation)
docker run -d --name cc-mobile-api -p 8675:8675 -v "${PWD}:/app" --env-file .env cc-mobile-api python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8675

echo "Port mapping:"
docker port cc-mobile-api
