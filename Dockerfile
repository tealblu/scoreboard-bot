FROM python:3.12.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /bot

# Install dependencies in a separate layer so code changes don't bust the cache.
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .

# Non-root user + writable data directory for the SQLite database & logs.
RUN useradd --create-home --shell /usr/sbin/nologin botuser \
    && mkdir -p /bot/data \
    && chown -R botuser:botuser /bot

USER botuser

ENTRYPOINT [ "python", "bot.py" ]
