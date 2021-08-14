"""
Contains various Notificator implementations.
"""


from abc import ABC, abstractmethod
import smtplib
from typing import List

import requests
import numpy as np


class NotificatorBase(ABC):
    """
    Notificator base class. This class is meant to be subclassed for each implementation of different notification
    options.
    """

    def __init__(self, recipients):
        self.recipients = recipients

    @abstractmethod
    def send_text(self, subject, message):
        """
        Sends notification.

        :param subject: Subject (title) of notification.
        :type subject: str

        :param message: Message content.
        :type message: str
        """

    def send_items(self, subject: str, items: List[dict], item_format: str, send_separate: bool=False):
        """
        Sends items in a form of a dictionary to recipients.

        :param subject: Subject for message.
        :param items: List of dictionaries, containing data as key value pairs, which will be sent to recipients.
        :param item_format: Format, with which each item's message will be created.
        :param send_separate: If True, each item will be sent as separate message.
        """
        text = ""
        for item in items:
            item_text = item_format.format(**item)
            if send_separate:
                self.send_text(subject, item_text)
            else:
                text += item_text

        if not send_separate:
            self.send_text(subject, text)


class EmailNotificator(NotificatorBase):
    """
    Email notification implementation.

    This implementation uses gmail's SMTP server to send notifications as emails to users.

    This implementation requires user credentials (email address and password) to be
    stored in environment variables as EMAIL_PASS and EMAIL_USER. To avoid storing your
    password in system variables, it is advised to generate a special password to be used only
    for this application. This can be done here:

    https://myaccount.google.com/apppasswords and generate a new app password for your account.

    This password can then safely be stored under EMAIL_PASS variable.
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

    def send_text(self, subject, message):
        """
        Sends email message.

        :param subject: Subject of email.
        :type subject: str

        :param message: Email message content.
        :type message: str
        """
        email_password = self._email_password
        email_user = self._email_user

        with self._get_smtp_session() as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()

            smtp.login(user=email_user, password=email_password)

            msg = f'Subject: {subject}\n\n{message}'

            smtp.sendmail(email_user, self.recipients, msg.encode('utf8'))


class PushoverNotificator(NotificatorBase):
    """
    Pushover notification implementation.

    This implementation uses Pushover (https://pushover.net/) to send push notifications to the
    recipients' mobile phones.

    This implementation requires 'PUSHOVER_APP_TOKEN' variable to be stored in environment variables.
    Value of this variable should be a pushover application token, which can be generated here:

    https://pushover.net/apps/build

    :param recipients: Pushover user keys of recipients to which push notification should be sent.
    :type recipients: list
    """
    def __init__(self, recipients, app_token):
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
        session = self._open_session()
        for user_key in self.recipients:
            payload = {"token": self._app_token,
                       "user": user_key,
                       "title": subject,
                       "message": message}
            session.post('https://api.pushover.net/1/messages.json', data=payload, headers={'User-Agent': 'Python'})

    def send_items(self, subject, items, item_format, send_separate=False):
        if send_separate:
            # here it is assumed, that any single item's text will not exceed 1024 character limitation
            super().send_items(subject, items, item_format, send_separate=True)
        else:
            # pushover messages are limited to 1024 characters. Items need to be divided to separate text blocks and
            # sent separately if text would exceed that limit

            temp_message = ""
            for item in items:
                item_txt = item_format.format(**item)
                if len(temp_message + item_txt) > 1024:
                    # if message together with new item exceeds character limit, send it without new item
                    self.send_text(subject, temp_message)

                    # current item will be sent in the next 'block'
                    temp_message = item_txt
                else:
                    temp_message += item_txt

            # send 'leftover' text
            self.send_text(subject, temp_message)
