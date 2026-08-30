FROM python:3.12-slim

WORKDIR /app

COPY . .

VOLUME app/data app/config

RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev --group web

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Default command runs the web UI (Django + APScheduler); the news_crawlers CLI is still
# available in the same image by overriding the command, e.g.:
#   docker run <image> python -m news_crawlers scrape
ENTRYPOINT ["webui/docker-entrypoint.sh"]
