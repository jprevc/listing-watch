import argparse
import pathlib
from typing import Optional
import logging
import logging.handlers
import yaml

from news_crawlers import scrape
from news_crawlers import scheduler
from news_crawlers import configuration


logger = logging.getLogger("main")
log_handler = logging.handlers.TimedRotatingFileHandler("news_crawlers.log", when="d", interval=7)
logger.addHandler(log_handler)


def read_configuration(config_path: Optional[pathlib.Path] = None) -> dict:
    # read configuration
    found_config_path = configuration.find_config(config_path)

    with open(found_config_path, encoding="utf8") as file:
        config_dict = yaml.safe_load(file)

    logger.debug(f"Found configuration in {found_config_path.resolve()}")

    return config_dict


def run_crawlers(config_path: Optional[pathlib.Path], spiders_to_run: list[str], cache_folder: pathlib.Path) -> None:
    logger.debug(f"Running crawlers with input parameters: {locals()}")
    scrape_configuration_dict = read_configuration(config_path)

    spider_configuration_dict = scrape_configuration_dict["spiders"]

    if spiders_to_run is None:
        spiders_to_run = list(spider_configuration_dict.keys())

    try:
        crawled_data = scrape.scrape(spiders_to_run, spider_configuration_dict, cache_folder)
        logger.debug("Scraping done.")

        diff = scrape.check_diff_and_notify(cache_folder, crawled_data, spider_configuration_dict, spiders_to_run)

        if any(crawled_values for crawled_values in diff.values()):
            logger.debug(f"Found new items: {diff}")
        else:
            logger.debug("No new items were found.")

    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Exception occurred when running crawlers.", exc_info=exc)
    else:
        logger.debug("Crawlers were run successfully.")


def main() -> int:
    logger.info("Application started.")

    parser = argparse.ArgumentParser(
        prog="News Crawlers",
        description="Runs web crawlers which will check for updates and alert users if there are any news.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    scrape_parser = subparsers.add_parser("scrape")
    scrape_parser.add_argument("-s", "--spider", required=False, action="append")
    scrape_parser.add_argument("-c", "--config", type=pathlib.Path, required=False)
    scrape_parser.add_argument("--cache", required=False, type=pathlib.Path, default=scrape.DEFAULT_CACHE_PATH)

    scrape_subparsers = scrape_parser.add_subparsers(dest="scrape_command")
    schedule_parser = scrape_subparsers.add_parser("schedule")
    schedule_parser.add_argument("--every", required=False, default=1, type=int)
    schedule_parser.add_argument("--units", required=False, default="minutes")

    args = parser.parse_args()

    logger.info(f"Running application with args: {vars(args)}")

    if args.command != "scrape":
        return 0

    scrape_configuration_dict = read_configuration(args.config)

    if args.scrape_command == "schedule":
        sch_data = scheduler.ScheduleData(every=args.every, units=args.units)
        logger.debug(f"Scheduled crawling on every {args.every} {args.units}")
    elif "schedule" in scrape_configuration_dict:
        sch_data = scheduler.ScheduleData(**scrape_configuration_dict["schedule"])
        logger.debug(f"Scheduled crawling on every {sch_data.every} {sch_data.units}")
    else:
        logger.debug("Running crawlers without schedule.")
        run_crawlers(args.config, args.spider, args.cache)
        return 0

    scheduler.schedule_func(lambda: run_crawlers(args.config, args.spider, args.cache), sch_data)

    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(message)s",
    )
    raise SystemExit(main())
