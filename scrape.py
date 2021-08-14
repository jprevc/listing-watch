"""
Main module. Runs defined crawler and send notifications to user, if any news are found.
"""

import os
import json
import sys

import yaml
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from notificators import EmailNotificator, PushoverNotificator


def run_spider(spider_name: str) -> list:
    """
    Runs spider and returns collected (scraped) data.

    :param spider_name: Name of spider to be run.

    :return: Collected (scraped) data.
    """
    crawled_output_path = spider_name + '.json'

    # if output file exists, remove it, otherwise scrapy will just append new data to it
    if os.path.exists(crawled_output_path):
        os.remove(crawled_output_path)

    # set settings for spider
    settings = get_project_settings()
    settings['FEED_FORMAT'] = 'json'
    settings['FEED_URI'] = crawled_output_path

    # create new crawler process and run it
    process = CrawlerProcess(settings)
    process.crawl(spider_name)
    process.start()  # the script will block here until the crawling is finished

    # open resulting json file and read its contents
    with open(crawled_output_path, 'r') as file:
        scraped_data = json.load(file)

    # remove json file, which was created when crawling - it is not needed anymore
    os.remove(crawled_output_path)

    return scraped_data


def get_cached_items(cached_items_path: str) -> list:
    """
    Returns cached (previously scraped) items from file.

    :param cached_items_path: Path to file which contains items, that were scraped
                              in the previous run.

    :return: List of cached items. If specified file does not exist, an empty list
                                   will be returned.
    """
    if os.path.exists(cached_items_path):
        with open(cached_items_path, 'r') as file:
            cached_data = json.load(file)
    else:
        cached_data = []

    return cached_data


def get_notificator(notificator_type: str, recipients: list):
    """
    Creates a notificator according to specified type.

    :param notificator_type: Notificator type. Can either be 'email' or 'pushover'.

    :param recipients: List of recipients to which messages should be sent.

    :return: Notificator object.
    :rtype: NotificatorBase
    """
    notificator_map = {'email': lambda: EmailNotificator(recipients, os.environ.get('EMAIL_USER'),
                                                         os.environ.get('EMAIL_PASS')),
                       'pushover': lambda: PushoverNotificator(recipients, os.environ.get('PUSHOVER_APP_TOKEN'))}

    return notificator_map[notificator_type]()


if __name__ == '__main__':
    spider = sys.argv[1]

    home_path = os.environ.get('NEWS_CRAWLERS_HOME', os.path.dirname(__file__))

    # create __cache__ folder in which *_cache.json files will be stored
    cache_folder = os.path.join(home_path, '__cache__')
    if not os.path.exists(cache_folder):
        os.makedirs(cache_folder)

    # read configuration for this spider
    configuration_path = os.path.join(home_path, spider + '_configuration.yaml')
    with open(configuration_path, 'r') as f:
        spider_configuration = yaml.safe_load(f)

    # run spider to acquire crawled data
    crawled_data = run_spider(spider)

    # get previously crawled cached items
    cached_json = os.path.join(cache_folder, spider + '_cached.json')
    cached_spider_data = get_cached_items(cached_json)

    # check which crawled items are new
    new_data = [item for item in crawled_data if item not in cached_spider_data]

    # if new items have been found, send a notification and add that data to cached items
    if new_data:
        # send message with each configured notificator
        for notificator_type_str, notificator_data in spider_configuration['notifications'].items():
            notificator = get_notificator(notificator_type_str, notificator_data['recipients'])

            notificator.send_items(spider + ' news', new_data, spider_configuration['message_body_format'],
                                   send_separate=notificator_data.get('send_separately', False))

            # append new items to cached ones and write all back to file
            cached_spider_data += list(new_data)
            with open(cached_json, 'w+') as f:
                json.dump(cached_spider_data, f)
