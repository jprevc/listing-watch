"""
Contains various Notificator implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import smtplib
import sys
import os
import inspect

import requests


class Notificator(ABC):
    """
    Notificator base class. This class is meant to be subclassed for each implementation of different notification
    options.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    def __init__(self, configuration: dict[str, str]):
        self.configuration = handle_secrets_in_configuration(configuration)

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

    def send_items(
        self,
        subject: str,
        items: list[dict],
        item_format: str,
        send_separately: bool = False,
    ):
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


class EmailNotificator(Notificator):
    """
    Email notification implementation.

    This implementation uses gmail's SMTP server to send notifications as emails to users.

    This implementation requires user credentials (email address and password). To avoid storing your
    password in system variables, it is advised to generate a special password to be used only
    for this application. This can be done here:

    https://myaccount.google.com/apppasswords
    """

    name = "email"

    def __init__(self, configuration):
        super().__init__(configuration)
        self._email_user = self.configuration["email_user"]
        self._email_password = self.configuration["email_password"]

    @staticmethod
    def _get_smtp_session() -> smtplib.SMTP:
        """
        Returns Gmail SMTP session handle.

        :return: Gmail SMTP session handle.
        """
        return smtplib.SMTP("smtp.gmail.com", 587)

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

            msg = f"Subject: {subject}\n\n{message}"

            smtp.sendmail(
                self._email_user,
                self.configuration["recipients"].split(","),
                msg.encode("utf8"),
            )


class PushoverNotificator(Notificator):
    """
    Pushover notification implementation.

    This implementation uses Pushover (https://pushover.net/) to send push notifications to the
    recipients' mobile phones.

    Pushover API token can be generated here:
    https://pushover.net/apps/build
    """

    name = "pushover"

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
        url = item.get("url", None)
        message = item_format.format(**item)
        self._post_message(subject, message, url=url)

    def _post_message(self, subject, message, url):
        session = self._open_session()
        for user_key in self.configuration["recipients"].split(","):
            payload = {
                "token": self.configuration["app_token"],
                "user": user_key,
                "title": subject,
                "message": message,
            }
            if url:
                payload["url"] = url

            session.post(
                "https://api.pushover.net/1/messages.json",
                data=payload,
                headers={"User-Agent": "Python"},
            )

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


def get_notificator_by_name(name: str) -> type[Notificator]:
    """
    Finds notificator class with the 'name' attribute equal to the one specified.

    :param name: Value of the 'name' attribute within the notificator class to match.

    :return: Notificator class.

    :raises KeyError: If notificator could not be found.
    """
    for _, obj in inspect.getmembers(sys.modules[__name__]):
        if inspect.isclass(obj) and issubclass(obj, Notificator) and obj.name == name:
            return obj
    raise KeyError(f"Could not find notificator with name attribute set to {name}.")


def handle_secrets_in_configuration(configuration: dict[str, str]) -> dict[str, str]:
    """
    Replaces dictionary values starting with __env_ with values from environment variables.

    :param configuration: Notificator configuration dictionary.

    :return: Notificator configuration dictionary, where all __env_* values are replaced with values from
             environment variables.

    :raises KeyError: If value could not be found in environment variables.
    """

    out_dict = {}
    for key, val in configuration.items():
        if val.startswith("__env_"):
            env_var = val.replace("__env_", "")
            try:
                out_dict[key] = os.environ[env_var]
            except KeyError as exc:
                raise KeyError(f"Could not find {env_var} in environment variables.") from exc
        else:
            out_dict[key] = val
    return out_dict
