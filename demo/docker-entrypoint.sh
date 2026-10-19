#!/bin/sh
set -e

cd /app/webui

python manage.py migrate --noinput
python /demo/seed_demo.py

exec /app/webui/docker-entrypoint.sh
