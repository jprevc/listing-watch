FROM python:3.12-slim

WORKDIR /app

COPY . .

VOLUME app/data app/config

RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev --group web

ENV PATH="/app/.venv/bin:$PATH"

# exampleSpider drives a real Chromium (via Playwright) instead of plain HTTP requests -- example.com's
# anti-bot protection requires actual JS execution/fingerprinting that no amount of header spoofing
# on a plain request can satisfy. --with-deps installs Chromium's OS-level shared libraries too
# (fonts, codecs, etc.), needed since this is a slim base image. xvfb provides the virtual display
# Chromium renders into: it's launched headed (not headless), since even Chromium's modern
# headless mode still leaks a few detectable differences from a real, on-screen browser.
RUN playwright install --with-deps chromium \
    && apt-get install -y --no-install-recommends xvfb \
    && rm -rf /var/lib/apt/lists/*

EXPOSE 8000

# Default command runs the web UI (Django + APScheduler); the news_crawlers CLI is still
# available in the same image by overriding the command, e.g.:
#   docker run <image> python -m news_crawlers scrape
ENTRYPOINT ["webui/docker-entrypoint.sh"]
