FROM python:3.12-slim

WORKDIR /app

# Install deps first, separate from copying source -- lets Docker cache this layer
# across rebuilds when only application code changes, not dependencies.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Mirrors operations-assistant's Dockerfile pattern (same author, same reasoning) --
# a genuine health check against /health (src/api/routes.py's `check_connection()`),
# not just "is the process up". Reads $PORT (falling back to 8000 locally) since
# Render/Cloud Run assign the listen port dynamically via that env var.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import os, httpx; httpx.get(f'http://localhost:{os.environ.get(\"PORT\", 8000)}/health', timeout=3).raise_for_status()" || exit 1

# Shell form (not exec-form JSON array) so $PORT is expanded at container start --
# an exec-form CMD would pass the literal string "$PORT" to uvicorn instead of its
# value. Falls back to 8000 (this project's local default) when PORT isn't set.
CMD uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
