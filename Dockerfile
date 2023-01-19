FROM python:3.10-slim

WORKDIR /app

COPY . .

VOLUME app/data app/config

RUN ["python3", "-m", "pip", "install", "-e", "."]

CMD ["python3", "-m", "news_crawlers",  "scrape"]
