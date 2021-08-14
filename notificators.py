"""
Contains various Notificator implementations.
"""

from abc import ABC, abstractmethod
import smtplib
from typing import List

import requests


class NotificatorBase(ABC):
    """
    Notificator base class. This class is meant to be subclassed for each implementation of different notification
    options.
    """

    def __init__(self, recipients):
        self.recipients = recipients

    @abstractmethod
    def send_text(self, subject: str, message: str):
        """
        Sends notification.

        :param subject: Subject (title) of notification.
        :param message: Message content.
        """

    @abstractmethod
    def _send_single_item(self, subject: str, item: dict, item_format: str):
        """
        Sends single item as a message.

        :param subject: Subject (title) of notification.
        :param item: Item as a dictionary, containing data as key value pairs, which will be sent to recipients.
        :param item_format: Format, with which item's message will be created.
        """

    def send_items(self, subject: str, items: List[dict], item_format: str, send_separately: bool=False):
        """
        Sends items in a form of a dictionary to recipients.

        :param subject: Subject for message.
        :param items: List of dictionaries, containing data as key value pairs, which will be sent to recipients.
        :param item_format: Format, with which each item's message will be created.
        :param send_separately: If True, each item will be sent as separate message.
        """
        text = ""
        for item in items:
            if send_separately:
                self._send_single_item(subject, item, item_format)
            else:
                text += item_format.format(**item)

        if not send_separately:
            self.send_text(subject, text)


class EmailNotificator(NotificatorBase):
    """
    Email notification implementation.

    This implementation uses gmail's SMTP server to send notifications as emails to users.

    This implementation requires user credentials (email address and password). To avoid storing your
    password in system variables, it is advised to generate a special password to be used only
    for this application. This can be done here:

    https://myaccount.google.com/apppasswords
    """
    def __init__(self, recipients, email_user, email_password):
        super().__init__(recipients)
        self._email_user = email_user
        self._email_password = email_password

    @staticmethod
    def _get_smtp_session() -> smtplib.SMTP:
        """
        Returns Gmail SMTP session handle.

        :return: Gmail SMTP session handle.
        """
        return smtplib.SMTP('smtp.gmail.com', 587)

    def _send_single_item(self, subject, item, item_format):
        self.send_text(subject, item_format.format(**item))

    def send_text(self, subject: str, message: str):
        """
        Sends email message.

        :param subject: Subject of email.
        :param message: Email message content.
        """
        with self._get_smtp_session() as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()

            smtp.login(user=self._email_user, password=self._email_password)

            msg = f'Subject: {subject}\n\n{message}'

            smtp.sendmail(self._email_user, self.recipients, msg.encode('utf8'))


class PushoverNotificator(NotificatorBase):
    """
    Pushover notification implementation.

    This implementation uses Pushover (https://pushover.net/) to send push notifications to the
    recipients' mobile phones.

    Pushover API token can be generated here:
    https://pushover.net/apps/build

    :param recipients: Pushover user keys of recipients to which push notification should be sent.
    :param app_token: Pushover application token.
    """
    def __init__(self, recipients: list, app_token: str):
        super().__init__(recipients)
        self._app_token = app_token

    @staticmethod
    def _open_session() -> requests.Session:
        """
        Opens HTTPS session.

        :return: HTTPS session handle.
        """
        return requests.Session()

    def send_text(self, subject: str, message: str):
        """
        Sends a pushover notification.

        :param subject: Subject of push notification.
        :param message: Push notification message.
        """
        self._post_message(subject, message, url=None)

    def _send_single_item(self, subject, item, item_format):

        # if item contains 'url' field, we can send it as URL in push notification and will be presented
        # in designated place
        url = item.get('url', None)
        message = item_format.format(**item)
        self._post_message(subject, message, url=url)

    def _post_message(self, subject, message, url):
        session = self._open_session()
        for user_key in self.recipients:
            payload = {"token": self._app_token,
                       "user": user_key,
                       "title": subject,
                       "message": message}
            if url:
                payload['url'] = url

            session.post('https://api.pushover.net/1/messages.json', data=payload, headers={'User-Agent': 'Python'})

    def send_items(self, subject, items, item_format, send_separately=False):
        if send_separately:
            # here it is assumed, that any single item's text will not exceed 1024 character limitation
            super().send_items(subject, items, item_format, send_separately=True)
        else:
            # pushover messages are limited to 1024 characters. Items need to be divided to separate text blocks and
            # sent separately if text would exceed that limit

            temp_message = ""
            for item in items:
                item_txt = item_format.format(**item)
                if len(temp_message + item_txt) > 1024:
                    # if message together with new item exceeds character limit, send it without new item
                    self.send_text(subject, temp_message)

                    # current item's text will be sent in the next message
                    temp_message = item_txt
                else:
                    # append current item's text to message
                    temp_message += item_txt

            # send 'leftover' text
            self.send_text(subject, temp_message)
