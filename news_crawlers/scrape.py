"""
Main module. Runs defined crawler and send notifications to user, if any news are found.
"""
from __future__ import annotations

import json
import pathlib
from typing import cast

from news_crawlers import notificators
from news_crawlers import spiders
from news_crawlers import configuration

DEFAULT_CACHE_PATH = pathlib.Path("data") / ".nc_cache"

CrawlData = dict[str, list[spiders.SpiderItem]]


def get_cached_items(cached_items_path: pathlib.Path) -> list[spiders.SpiderItem]:
    """
    Returns cached (previously scraped) items from file.

    :param cached_items_path: Path to file which contains items, that were scraped
                              in the previous run.

    :return: List of cached items. If specified file does not exist, an empty list
                                   will be returned.
    """
    if cached_items_path.exists():
        with open(cached_items_path, "r+", encoding="utf8") as cache_file:
            cached_data = cast(list[spiders.SpiderItem], json.load(cache_file))
    else:
        cached_data = []

    return cached_data


def scrape(
    spiders_to_run: list[str],
    spiders_configuration: dict[str, configuration.SpiderConfig],
    cache_folder: pathlib.Path = DEFAULT_CACHE_PATH,
) -> CrawlData:

    # create cache folder in which *_cache.json files will be stored
    if not cache_folder.exists():
        cache_folder.mkdir(parents=True, exist_ok=True)

    return run_crawlers(spiders_configuration, spiders_to_run)


def run_crawlers(spiders_configuration: dict[str, configuration.SpiderConfig], spiders_to_run: list[str]) -> CrawlData:
    """
    Run the specified spiders with their configurations and return combined crawl results.

    :param spiders_configuration: Map of spider name to its config (URLs, etc.).
    :param spiders_to_run: List of spider names to run.
    :return: Map of spider name to list of scraped items.
    """
    crawled_data: CrawlData = {}
    for spider_name in spiders_to_run:
        spider_configuration = spiders_configuration[spider_name]

        spider = spiders.get_spider_by_name(spider_name)(spider_configuration.urls)

        crawled_data[spider_name] = spider.run()
    return crawled_data


def check_diff(
    cache_folder: pathlib.Path,
    crawled_data: CrawlData,
) -> CrawlData:
    diff: CrawlData = {}
    for spider_name, crawled_spider_items in crawled_data.items():
        cache_file = pathlib.Path(cache_folder) / f"{spider_name}_cached.json"

        # get previously crawled cached items
        cached_spider_data = get_cached_items(cache_file)

        new_data = [item for item in crawled_spider_items if item not in cached_spider_data]

        # if new items have been found, add that data to cached items
        if new_data:
            diff[spider_name] = new_data
            # write old + new items to cache file
            with open(cache_file, "w+", encoding="utf8") as file:
                json.dump(cached_spider_data + new_data, file)

    return diff


def notify(diff: CrawlData, spiders_configuration: dict[str, configuration.SpiderConfig]) -> None:
    """
    Send notifications for each spider that has new items, using that spider's configured notificators.

    :param diff: Map of spider name to list of new items.
    :param spiders_configuration: Map of spider name to its config (including notifications).
    """
    for spider_name, new_data in diff.items():
        send_notifications(spiders_configuration[spider_name].notifications, spider_name, new_data)


def send_notifications(
    notificators_config: dict[str, dict[str, str | bool]],
    spider_name: str,
    new_data: list[spiders.SpiderItem],
) -> None:
    """
    Send new items to all configured notificators (e.g. email, Pushover) for a single spider.

    :param notificators_config: Map of notificator type name to its config (e.g. message_body_format).
    :param spider_name: Name of the spider (used in the notification subject/title).
    :param new_data: List of new items to send.
    """
    # send message with each configured notificator
    for (notificator_type_str, notificator_data) in notificators_config.items():
        notificator = notificators.get_notificator_by_name(notificator_type_str)(notificator_data)

        message_body_format = cast(str, notificator_data["message_body_format"])
        send_separately = cast(bool, notificator_data.get("send_separately", False))

        notificator.send_items(
            spider_name + " news",
            new_data,
            message_body_format,
            send_separately=send_separately,
        )
