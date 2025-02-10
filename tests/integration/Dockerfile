FROM python:3.11-slim

WORKDIR /app

# Install git (needed for tests)
RUN apt-get update && apt-get install -y git

# Create cache directory with correct permissions
RUN mkdir -p .cache && chmod 777 .cache

# Copy only necessary files for testing
COPY requirements.txt .
COPY setup.py .
COPY build/ build/
COPY utils/ utils/
COPY tests/ tests/

# Install dependencies
RUN pip install -e .
RUN pip install pytest pytest-asyncio pytest-cov

# Set environment variables
ENV PYTHONPATH=/app
ENV ANTHROPIC_API_KEY=test-key

# Command to run tests
CMD ["pytest", "tests/integration/test_build.py", "-v", "--cov=build"] 