#!/bin/bash

# Exit on any error
set -e

# Cleanup function
cleanup() {
    echo "Cleaning up temporary files..."
    rm -f Dockerfile
}

# Set cleanup to run on script exit (success or failure)
trap cleanup EXIT

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "Error: ANTHROPIC_API_KEY environment variable is not set"
    exit 1
fi

# Create Docker image
cat << EOF > Dockerfile
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ruby-full \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Jekyll
RUN gem install jekyll bundler

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy source code
COPY . .

# Set environment variable
ENV ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}

# Create necessary directories
RUN mkdir -p docs/source docs/build

# Use non-root user for better security
RUN useradd -m docuser && \
    chown -R docuser:docuser /app
USER docuser

# Run the documentation pipeline
CMD python -m utils.generate && \
    python -m utils.validate && \
    cd docs && jekyll build
EOF

echo "Building Docker image..."
docker build -t doc-pipeline .

echo "Running documentation pipeline..."
docker run --rm \
    -v "$(pwd):/app" \
    -u "$(id -u):$(id -g)" \
    doc-pipeline

echo "Pipeline completed successfully!"
