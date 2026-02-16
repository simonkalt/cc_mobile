#!/bin/bash

# Stop the container if it's running
docker stop cc-mobile-api 2>/dev/null || true

# Remove the container if it exists
docker rm cc-mobile-api 2>/dev/null || true

# Optional: prune unused images/layers safely (commented out)
# docker system prune -f

# Build the image
docker build -t cc-mobile-api .

# Run the container with a bind mount
docker run --name cc-mobile-api \
  -p 8000:8000 \
  -v ${PWD}:/app \
  cc-mobile-api \
  python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
