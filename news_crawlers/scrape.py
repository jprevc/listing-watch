"""
Main module. Runs defined crawler and send notifications to user, if any news are found.
"""

import os
import json
from typing import Optional

import yaml

from news_crawlers import notificators
from news_crawlers import spiders
from news_crawlers import configuration


def get_cached_items(cached_items_path: str) -> list:
    """
    Returns cached (previously scraped) items from file.

    :param cached_items_path: Path to file which contains items, that were scraped
                              in the previous run.

    :return: List of cached items. If specified file does not exist, an empty list
                                   will be returned.
    """
    if os.path.exists(cached_items_path):
        with open(cached_items_path, encoding="utf8") as file:
            cached_data = json.load(file)
    else:
        cached_data = []

    return cached_data


def scrape(spiders_to_run: Optional[list[str]], config_path: Optional[str], cache_path: Optional[str]) -> None:

    # create __cache__ folder in which *_cache.json files will be stored
    if not os.path.exists(cache_path):
        os.makedirs(cache_path)

    # read configuration
    with open(config_path, encoding="utf8") as file:
        spider_configuration_dict = yaml.safe_load(file)

    if spiders_to_run is None:
        spiders_to_run = spider_configuration_dict.keys()

    for spider_name in spiders_to_run:

        spider_configuration = configuration.NewsCrawlerConfig(**spider_configuration_dict[spider_name])

        spider = spiders.get_spider_by_name(spider_name)(spider_configuration)

        # run spider to acquire crawled data
        crawled_data = spider.run()

        # get previously crawled cached items
        cached_json = os.path.join(cache_path, spider_name + "_cached.json")
        cached_spider_data = get_cached_items(cached_json)

        # check which crawled items are new
        new_data = [item for item in crawled_data if item not in cached_spider_data]

        # if new items have been found, send a notification and add that data to cached items
        if new_data:
            # send message with each configured notificator
            for (notificator_type_str, notificator_data) in spider_configuration.notifications.items():
                notificator = notificators.get_notificator_by_name(notificator_type_str)(notificator_data)

                notificator.send_items(
                    spider_name + " news",
                    new_data,
                    notificator_data["message_body_format"],
                    send_separately=notificator_data.get("send_separately", False),
                )

                # append new items to cached ones and write all back to file
                cached_spider_data += list(new_data)
                with open(cached_json, "w+", encoding="utf8") as file:
                    json.dump(cached_spider_data, file)
