"""
Contains various Notificator implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import smtplib
from typing import Sequence, cast

import requests

from listing_watch.config_field import ConfigField

NotificatorItem = dict[str, str]


class _EmptyForMissing(dict[str, str]):
    """An item's fields for `str.format_map`, where a field the item lacks renders as empty."""

    def __missing__(self, key: str) -> str:
        return ""


class Notificator(ABC):
    """
    Notificator base class. This class is meant to be subclassed for each implementation of different notification
    options.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    # The settings this Notificator needs from the user. The Core renders them as the Notification
    # Profile form and stores the entered values in `configuration`, under each field's key.
    config_fields: Sequence[ConfigField] = ()

    def __init__(self, configuration: dict[str, str | bool]):
        self.configuration = configuration

    @abstractmethod
    def send_text(self, subject: str, message: str) -> None:
        """
        Sends notification.

        :param subject: Subject (title) of notification.
        :param message: Message content.
        """

    @staticmethod
    def _format_item(item: NotificatorItem, item_format: str, include_header: bool) -> str:
        """
        Renders a single item's body via `item_format`, optionally preceded by a "Query: ..."
        header. The header isn't part of `item_format` itself (which no longer contains
        `{query}`) since it's meant to appear once per query, not once per item -- see
        `send_items`.

        :param item: Item to render.
        :param item_format: Format, with which the item's body will be created. A field the item
            doesn't have renders as empty: an Item only has to carry a title and a URL.
        :param include_header: Whether to prepend a "Query: <name>" header line.
        :return: Rendered item, ready to be joined with other items via a blank line.
        """
        body = item_format.format_map(_EmptyForMissing(item)).rstrip()
        if include_header:
            return f"Query: {item['query']}\n\n{body}"
        return body

    def send_items(
        self,
        subject: str,
        items: list[NotificatorItem],
        item_format: str,
    ) -> None:
        """
        Sends items in a form of a dictionary to recipients.

        Items are expected to arrive grouped by `query` (consecutive items sharing the same
        query stay adjacent) -- true for every current spider, which builds its item list one
        query at a time. A "Query: <name>" header is emitted once at the start of each such
        run rather than once per item, since all items in a run share the same query value.

        :param subject: Subject for message.
        :param items: List of dictionaries, containing data as key value pairs, which will be sent to recipients.
        :param item_format: Format, with which each item's message will be created.
        """
        blocks: list[str] = []
        previous_query: str | None = None
        for item in items:
            query = item["query"]
            blocks.append(self._format_item(item, item_format, include_header=query != previous_query))
            previous_query = query

        self.send_text(subject, "\n\n".join(blocks))


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
    config_fields = (
        ConfigField(key="email_user", label="Email address", required=True),
        ConfigField(key="email_password", label="Email password", required=True, secret=True),
        ConfigField(key="recipients", label="Recipients (comma-separated email addresses)", required=True),
    )

    def __init__(self, configuration: dict[str, str | bool]) -> None:
        super().__init__(configuration)
        self._email_user = cast(str, self.configuration["email_user"])
        self._email_password = cast(str, self.configuration["email_password"])
        recipients = cast(str, self.configuration["recipients"])

        self.recipients = recipients.split(",")

    @staticmethod
    def _get_smtp_session() -> smtplib.SMTP:
        """
        Returns Gmail SMTP session handle.

        :return: Gmail SMTP session handle.
        """
        return smtplib.SMTP("smtp.gmail.com", 587)

    def send_text(self, subject: str, message: str) -> None:
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
                self.recipients,
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
    config_fields = (
        ConfigField(key="app_token", label="Pushover app token", required=True, secret=True),
        ConfigField(key="recipients", label="Recipients (comma-separated Pushover user keys)", required=True),
    )

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

    def _post_message(self, subject: str, message: str, url: str | None) -> None:
        session = self._open_session()
        recipients = cast(str, self.configuration["recipients"]).split(",")

        for user_key in recipients:
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

    def send_items(
        self,
        subject: str,
        items: list[NotificatorItem],
        item_format: str,
    ) -> None:
        # pushover messages are limited to 1024 characters. Items need to be divided into
        # separate text blocks and sent separately if text would exceed that limit. Each
        # resulting message is its own standalone push notification, so it always carries its
        # own "Query: ..." header for the query active where it starts, even if that query was
        # already headed in the previous (now-flushed) message.
        temp_message = ""
        temp_query: str | None = None
        for item in items:
            query = item["query"]
            piece = self._format_item(item, item_format, include_header=not temp_message or query != temp_query)
            candidate = f"{temp_message}\n\n{piece}" if temp_message else piece

            if temp_message and len(candidate) > 1024:
                # if message together with new item exceeds character limit, send it without new item
                self.send_text(subject, temp_message)

                # current item's text will be sent in the next message, with its own header
                temp_message = self._format_item(item, item_format, include_header=True)
            else:
                temp_message = candidate

            temp_query = query

        # send 'leftover' text
        self.send_text(subject, temp_message)


class NtfyNotificator(Notificator):
    """
    ntfy (https://ntfy.sh/) push notification implementation.

    Works with the public ntfy.sh service or a self-hosted ntfy server. Configure the topic to
    publish to; optionally a custom server, priority, tags, and authentication (either a bearer
    token or username/password).
    """

    name = "ntfy"
    config_fields = (
        ConfigField(key="topic", label="Topic", required=True),
        ConfigField(key="server", label="Server URL", default="https://ntfy.sh"),
        ConfigField(
            key="priority",
            label="Priority",
            help_text=(
                "How urgently ntfy delivers/displays the notification: min, low, default, high, or "
                "urgent (or 1-5). Leave blank for default. urgent/5 bypasses silent mode on some devices."
            ),
        ),
        ConfigField(
            key="tags",
            label="Tags (comma-separated)",
            help_text=(
                "Comma-separated labels. A tag matching a known emoji short name (e.g. warning, "
                "rotating_light, white_check_mark) is shown as an emoji prefix; other tags are shown as "
                "plain text tags."
            ),
        ),
        ConfigField(
            key="token",
            label="Auth token",
            secret=True,
            help_text=(
                "Only needed if your topic requires authentication. Use either this access token or the "
                "username and password below, not both. Leave the token, username and password blank for "
                "an unauthenticated topic on public ntfy.sh."
            ),
        ),
        ConfigField(key="username", label="Username"),
        ConfigField(key="password", label="Password", secret=True),
    )

    @staticmethod
    def _open_session() -> requests.Session:
        """
        Opens HTTPS session.

        :return: HTTPS session handle.
        """
        return requests.Session()

    def send_text(self, subject: str, message: str) -> None:
        """
        Sends an ntfy notification.

        :param subject: Subject of push notification.
        :param message: Push notification message.
        """
        self._post_message(subject, message, url=None)

    def _post_message(self, subject: str, message: str, url: str | None) -> None:
        session = self._open_session()
        server = cast(str, self.configuration.get("server", "https://ntfy.sh"))
        topic = cast(str, self.configuration["topic"])

        # HTTP header values passed as `str` are encoded 'latin-1' by the underlying
        # http.client/urllib3, which raises UnicodeEncodeError for any character outside that
        # range (e.g. 'Ž' in a Slovenian query/item title). Encoding to UTF-8 bytes up front
        # sidesteps that: bytes header values are sent as-is, and ntfy expects UTF-8 anyway.
        headers: dict[str, str | bytes] = {"Title": subject.encode("utf-8")}

        priority = self.configuration.get("priority")
        if priority:
            headers["Priority"] = str(priority)

        tags = self.configuration.get("tags")
        if tags:
            headers["Tags"] = cast(str, tags).encode("utf-8")

        if url:
            headers["Click"] = url.encode("utf-8")

        auth = None
        token = self.configuration.get("token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif self.configuration.get("username") and self.configuration.get("password"):
            auth = (cast(str, self.configuration["username"]), cast(str, self.configuration["password"]))

        response = session.post(
            f"{server.rstrip('/')}/{topic}",
            data=message.encode("utf-8"),
            headers=headers,
            auth=auth,
        )
        # requests doesn't raise for HTTP error responses on its own -- without this, a rejected
        # publish (bad/expired token, unknown topic, server error, ...) looks identical to a
        # successful one: the crawl run gets marked SUCCESS with no error, silently swallowing a
        # real delivery failure. Raising surfaces it through send_notifications' existing
        # per-notificator error aggregation instead.
        response.raise_for_status()

