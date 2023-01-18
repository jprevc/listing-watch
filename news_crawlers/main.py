import argparse

from news_crawlers import scrape
from news_crawlers import scheduler


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

    scrape_subparsers = scrape_parser.add_subparsers(dest="scrape_command")
    schedule_parser = scrape_subparsers.add_parser("schedule")
    schedule_parser.add_argument("--every", required=False, default=1, type=int)
    schedule_parser.add_argument("--units", required=False, default="minutes")

    args = parser.parse_args()

    if args.command == "scrape":

        scrape_args = [args.spider, args.config, args.cache]

        if args.scrape_command == "schedule":
            scheduler.schedule_func(lambda: scrape.scrape(*scrape_args), args.every, args.units)
        else:
            scrape.scrape(*scrape_args)


if __name__ == "__main__":
    main()
