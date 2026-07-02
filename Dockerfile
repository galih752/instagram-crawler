# ---- Build stage ----
FROM python:3.10-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps into a venv
COPY pyproject.toml ./
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel && \
    /opt/venv/bin/pip install --no-cache-dir \
        instagrapi \
        pydantic \
        pydantic-settings \
        loguru \
        httpx \
        aiohttp \
        redis \
        kafka-python \
        greenstalk \
        beautifulsoup4 \
        pyquery \
        faker \
        python-dateutil \
        dateparser \
        pytz \
        jmespath \
        lxml \
        orjson

# ---- Runtime stage ----
FROM python:3.10-slim AS runtime

WORKDIR /app

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY source/ ./source/

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Default command
ENTRYPOINT ["python", "source/main.py"]
CMD ["crawler", "--help"]
