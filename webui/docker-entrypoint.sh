#!/bin/sh
set -e

cd /app/webui

# Chromium (driven by Playwright in exampleSpider) runs headed, not headless, so it needs a display
# to render into -- Xvfb provides a virtual one since this container has no real screen.
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99

python manage.py migrate --noinput
python manage.py collectstatic --noinput

python manage.py runscheduler &

exec gunicorn webui.wsgi:application --bind 0.0.0.0:8000
