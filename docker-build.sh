#!/bin/bash

IMAGE_NAME=cc-mobile-backend

echo "Building Docker image..."

docker build -t $IMAGE_NAME .

echo "Build complete."