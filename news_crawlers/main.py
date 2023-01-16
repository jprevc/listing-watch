import argparse
from news_crawlers import scrape


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="News Crawlers",
        description="Runs web crawlers which will check for updates and alert users if " "there are any news.",
    )

    subparsers = parser.add_subparsers(dest="command")
    scrape_parser = subparsers.add_parser("scrape")
    scrape_parser.add_argument("-s", "--spider", required=False, action="append")
    scrape_parser.add_argument("-c", "--config", default="news_crawlers.yaml")
    parser.add_argument("--cache", default=".nc_cache")

    args = parser.parse_args()

    if args.command == "scrape":
        scrape.scrape(args.spider, args.config, args.cache)


if __name__ == "__main__":
    main()
