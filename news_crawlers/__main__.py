import argparse
import os.path
import pathlib

import yaml

from news_crawlers import scrape
from news_crawlers import scheduler

DEFAULT_CONFIG_PATH = pathlib.Path("config") / "news_crawlers.yaml"


def find_config(config_path: str) -> str:
    config_path = config_path if os.path.exists(config_path) else "news_crawlers.yaml"

    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Could not find configuration file on {config_path} or in current working directory " f"{os.getcwd()}."
        )

    return config_path


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="News Crawlers",
        description="Runs web crawlers which will check for updates and alert users if " "there are any news.",
    )

    subparsers = parser.add_subparsers(dest="command")
    scrape_parser = subparsers.add_parser("scrape")
    scrape_parser.add_argument("-s", "--spider", required=False, action="append")
    scrape_parser.add_argument("-c", "--config", required=False, default=DEFAULT_CONFIG_PATH)
    scrape_parser.add_argument("--cache", required=False, default=scrape.DEFAULT_CACHE_PATH)

    scrape_subparsers = scrape_parser.add_subparsers(dest="scrape_command")
    schedule_parser = scrape_subparsers.add_parser("schedule")
    schedule_parser.add_argument("--every", required=False, default=1, type=int)
    schedule_parser.add_argument("--units", required=False, default="minutes")

    args = parser.parse_args()

    # read configuration
    with open(find_config(args.config), encoding="utf8") as file:
        scrape_configuration_dict = yaml.safe_load(file)

    spider_configuration_dict = scrape_configuration_dict["spiders"]

    if args.command != "scrape":
        return

    scrape_args_lst = [args.spider, spider_configuration_dict, args.cache]

    if args.scrape_command == "schedule":
        sch_data = scheduler.ScheduleData(every=args.every, units=args.units)
    elif "schedule" in scrape_configuration_dict:
        sch_data = scheduler.ScheduleData(**scrape_configuration_dict["schedule"])
    else:
        scrape.scrape(*scrape_args_lst)
        return

    scheduler.schedule_func(lambda: scrape.scrape(*scrape_args_lst), sch_data)


if __name__ == "__main__":
    main()
