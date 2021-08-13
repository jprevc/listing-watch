"""
Contains various Notificator implementations.
"""


from abc import ABC, abstractmethod
import os
import smtplib

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

    def send_items(self, subject, items, item_format, send_separate=False):
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

    def _get_smtp_session(self):
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
    def _open_session():
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

            # get list of indexes, where each index corresponds to group in which item should be sent. Indexes are
            # selected according to message size limitation, such that no message will exceed 1024 characters
            item_groups = np.cumsum([len(item_format.format(**item)) for item in items]) // 1025

            # get list of text messages for each group
            groups_txt_blocks = [""] * (max(item_groups) + 1)
            for item, group in zip(items, item_groups):
                groups_txt_blocks[group] += item_format.format(**item)

            # send messages in separate notifications
            for txt_block in groups_txt_blocks:
                self.send_text(subject, txt_block)
