"""
Main module. Runs defined crawler and send notifications to user, if any news are found.
"""
from __future__ import annotations

import json
import pathlib
from typing import Any

from news_crawlers import notificators
from news_crawlers import spiders
from news_crawlers import configuration

DEFAULT_CACHE_PATH = pathlib.Path("data") / ".nc_cache"


def get_cached_items(cached_items_path: pathlib.Path) -> list:
    """
    Returns cached (previously scraped) items from file.

    :param cached_items_path: Path to file which contains items, that were scraped
                              in the previous run.

    :return: List of cached items. If specified file does not exist, an empty list
                                   will be returned.
    """
    if cached_items_path.exists():
        with open(cached_items_path, "r+", encoding="utf8") as cache_file:
            cached_data = json.load(cache_file)
    else:
        cached_data = []

    return cached_data


def scrape(
    spiders_to_run: list[str],
    spiders_configuration: dict[str, Any],
    cache_folder: pathlib.Path = DEFAULT_CACHE_PATH,
) -> dict[str, list[dict]]:

    # create cache folder in which *_cache.json files will be stored
    if not cache_folder.exists():
        cache_folder.mkdir(parents=True, exist_ok=True)

    return run_crawlers(spiders_configuration, spiders_to_run)


def run_crawlers(spiders_configuration: dict[str, Any], spiders_to_run: list[str]) -> dict[str, list[dict]]:
    crawled_data: dict[str, list[dict]] = {}
    for spider_name in spiders_to_run:
        spider_configuration = configuration.NewsCrawlerConfig(**spiders_configuration[spider_name])

        spider = spiders.get_spider_by_name(spider_name)(spider_configuration.urls)

        crawled_data[spider_name] = spider.run()
    return crawled_data


def check_diff_and_notify(
    cache_folder: pathlib.Path,
    crawled_data: dict[str, list[dict]],
    spiders_configuration: dict[str, Any],
    spiders_to_run: list[str],
) -> dict[str, list[dict]]:
    diff: dict[str, list[dict]] = {}
    for spider_name in spiders_to_run:
        cache_file = pathlib.Path(cache_folder) / f"{spider_name}_cached.json"

        new_data = get_diff(cache_file, crawled_data[spider_name])
        diff[spider_name] = new_data

        notification_configuration = configuration.NewsCrawlerConfig(**spiders_configuration[spider_name]).notifications

        # if new items have been found, send a notification and add that data to cached items
        if new_data:
            send_notifications(notification_configuration, spider_name, new_data)

            # append new items to cached ones and write all back to file
            with open(cache_file, "a+", encoding="utf8") as file:
                json.dump(new_data, file)

    return diff


def get_diff(cache_file: pathlib.Path, crawled_data: list[dict]) -> list:
    # get previously crawled cached items
    cached_spider_data = get_cached_items(cache_file)

    # check which crawled items are new
    return [item for item in crawled_data if item not in cached_spider_data]


def send_notifications(notificators_config: dict, spider_name: str, new_data: list):
    # send message with each configured notificator
    for (notificator_type_str, notificator_data) in notificators_config.items():
        notificator = notificators.get_notificator_by_name(notificator_type_str)(notificator_data)

        notificator.send_items(
            spider_name + " news",
            new_data,
            notificator_data["message_body_format"],
            send_separately=notificator_data.get("send_separately", False),
        )
