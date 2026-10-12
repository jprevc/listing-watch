#!/bin/sh
set -e

cd /app/webui

python manage.py migrate --noinput
python manage.py collectstatic --noinput

python manage.py runscheduler &

exec gunicorn webui.wsgi:application --bind 0.0.0.0:8000
