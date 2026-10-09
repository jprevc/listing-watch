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

# Runs the web UI (Django + APScheduler).
ENTRYPOINT ["webui/docker-entrypoint.sh"]
