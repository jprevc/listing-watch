"""
Contains various mock classes which can be used in tests.
"""

import pathlib
from collections.abc import Callable

import requests

# pylint: disable=unused-argument


class HttpsSessionMock:
    """
    HTTPS Session mock class.
    """

    def __init__(self):
        self.simulated_messages = []

    def post(self, url, data, headers):
        self.simulated_messages.append(data["message"])


class NtfySessionMock:
    """
    HTTPS Session mock class for the ntfy notificator, whose 'post' call shape (raw bytes body,
    headers carrying title/priority/tags/click/auth info) differs from Pushover's form-encoded dict.
    """

    def __init__(self):
        self.simulated_messages = []
        self.simulated_headers = []
        self.simulated_urls = []
        self.simulated_auth = []

    def post(self, url, data=None, headers=None, auth=None):
        self.simulated_urls.append(url)
        self.simulated_messages.append(data.decode("utf-8") if isinstance(data, (bytes, bytearray)) else data)
        self.simulated_headers.append(headers or {})
        self.simulated_auth.append(auth)


class SmtpMock:
    """
    SMTP mock class
    """

    def __init__(self):
        self.simulated_messages = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def ehlo(self):
        pass

    def starttls(self):
        pass

    def login(self, user, password):
        pass

    def sendmail(self, user, recipients, message):
        self.simulated_messages.append(message)


def mock_get_raw_html(mock_html: str) -> str:
    mock_html_path = pathlib.Path(__file__).parent / "res" / mock_html

    with open(mock_html_path, encoding="utf8") as file:
        html_content = file.read()

    return html_content


class MockRequestObject:
    def __init__(self, mock_html, error_status: int = 404):
        self.mock_html = mock_html
        self.request_counter = 0
        self.error_status = error_status

    @property
    def text(self) -> str:
        self.request_counter += 1
        return mock_get_raw_html(self.mock_html)

    @property
    def status_code(self) -> int:
        return 200 if self.request_counter < 1 else self.error_status

    def raise_for_status(self) -> None:
        """Mimic requests.Response: raise on 4xx/5xx (mock errors out after the first call)."""
        if self.status_code >= 400:
            response = requests.Response()
            response.status_code = self.status_code
            response.raise_for_status()


def mock_requests_get(mock_html: str, error_status: int = 404) -> Callable[[str, str, str], MockRequestObject]:
    mock_request_obj = MockRequestObject(mock_html, error_status=error_status)

    def mock_request_func(url: str, headers: str, timeout: str) -> MockRequestObject:
        return mock_request_obj

    return mock_request_func


class FakePlaywrightResponse:
    """Minimal stand-in for playwright.sync_api.Response: just exposes .status."""

    def __init__(self, status: int):
        self.status = status


class FakePlaywrightPage:
    """Minimal stand-in for playwright.sync_api.Page.

    Takes a fixed sequence of (html, status) pairs, one per expected .goto() call, and replays
    them in order -- so exampleSpider's pagination/parsing logic can be tested without a real
    browser.
    """

    def __init__(self, responses: list[tuple[str, int]]):
        self._responses = list(responses)
        self._current_html = ""

    def goto(self, url: str, wait_until: str | None = None, timeout: int | None = None) -> FakePlaywrightResponse:
        self._current_html, status = self._responses.pop(0)
        return FakePlaywrightResponse(status)

    def content(self) -> str:
        return self._current_html


def send_text_mock(obj, subject, message):
    pass
