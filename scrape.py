from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
import os
import json
import smtplib
import yaml
import sys

from notificators import NotificatorBase, EmailNotificator, PushoverNotificator

def run_spider(spider_name):
    """
    Runs spider and returns collected (scraped) data.

    :param spider_name: Name of spider to be run.
    :type spider_name: str

    :return: Collected (scraped) data.
    :rtype: list
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
    with open(crawled_output_path, 'r') as f:
        scraped_data = json.load(f)

    # remove json file, which was created when crawling - it is not needed anymore
    os.remove(crawled_output_path)

    return scraped_data


def send_email(subject, message, recipient_list):
    """
    Sends email message to specified recipients.

    :param subject: Subject of email.
    :type subject: str

    :param message: Email message (body).
    :type message: str

    :param recipient_list: List of emails (recipients) to which email will be sent.
    :type recipient_list: list
    """
    email_password = os.environ.get('EMAIL_PASS')
    email_user = os.environ.get('EMAIL_USER')

    with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()

        smtp.login(user=email_user, password=email_password)

        msg = f'Subject: {subject}\n\n{message}'

        smtp.sendmail(email_user, recipient_list, msg.encode('utf8'))


def get_cached_items(cached_items_path):
    """
    Returns cached (previously scraped) items from file.

    :param cached_items_path: Path to file which contains items, that were scraped in the previous run.
    :type cached_items_path: str

    :return: List of cached items. If specified file does not exist, an empty list will be returned.
    :rtype: list
    """
    if os.path.exists(cached_items_path):
        with open(cached_items_path, 'r') as f:
            cached_data = json.load(f)
    else:
        cached_data = []

    return cached_data


def get_notificator(notificator_type):
    """
    Creates a notificator according to specified type.

    :param notificator_type: Notificator type. Can either be 'email' or 'pushover'.
    :type notificator_type: str

    :return: Notificator object.
    :rtype: NotificatorBase
    """
    notificator_map = {'email': EmailNotificator,
                       'pushover': PushoverNotificator}

    return notificator_map[notificator_type]


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
        message_body = '\n'.join([spider_configuration['message_body_format'].format(**item) for item in new_data])

        # send message with each configured notificator
        for notificator_type, notificator_data in spider_configuration['notifications'].items():
            notificator = get_notificator(notificator_type)(recipients=notificator_data['recipients'])

            notificator.send(spider + ' nove objave', message_body)

            # append new items to cached ones and write all back to file
            cached_spider_data += list(new_data)
            with open(cached_json, 'w+') as f:
                json.dump(cached_spider_data, f)
