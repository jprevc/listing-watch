#!/bin/sh
set -e

cd /app/webui

# Chromium (driven by Playwright in exampleSpider) runs headed, not headless, so it needs a display
# to render into -- Xvfb provides a virtual one since this container has no real screen.
#
# A prior Xvfb on the same display leaves a lock file (and X11 socket) behind in the container's
# writable layer; if the container is killed/restarted (e.g. mid-crawl, rather than recreated from
# a fresh filesystem), the stale lock makes this Xvfb refuse to start with "Server is already
# active for display 99" -- silently leaving no display at all, so every subsequent browser launch
# fails. Clear it first so a restart always gets a working display.
rm -f /tmp/.X99-lock /tmp/.X11-unix/X99
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99

python manage.py migrate --noinput
python manage.py collectstatic --noinput

python manage.py runscheduler &

exec gunicorn webui.wsgi:application --bind 0.0.0.0:8000
