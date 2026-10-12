FROM python:3.12-slim

WORKDIR /app

COPY . .

VOLUME app/data

RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev --group web

ENV PATH="/app/.venv/bin:$PATH"

# The Core has no Notificators of its own; the public Notificator Plugin provides Email, Pushover and
# ntfy. It's installed from PyPI next to the Core, so the Core release it depends on (`>=4,<5`) is
# already satisfied by the copy synced above.
RUN uv pip install --no-cache "listing-watch-notificators>=1,<2"

# The Core has no Spiders either, and so no browser. To crawl, build an image `FROM` this one that
# installs a Spider Plugin, plus whatever its Spiders need.

EXPOSE 8000

# Runs the web UI (Django + APScheduler).
ENTRYPOINT ["webui/docker-entrypoint.sh"]
