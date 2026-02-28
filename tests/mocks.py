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
    def __init__(self, mock_html):
        self.mock_html = mock_html
        self.request_counter = 0

    @property
    def text(self) -> str:
        self.request_counter += 1
        return mock_get_raw_html(self.mock_html)

    @property
    def status_code(self) -> int:
        return 200 if self.request_counter < 1 else 404

    def raise_for_status(self) -> None:
        """Mimic requests.Response: raise on 4xx/5xx (mock uses 404 after first call)."""
        if self.status_code >= 400:
            response = requests.Response()
            response.status_code = self.status_code
            response.raise_for_status()


def mock_requests_get(mock_html: str) -> Callable[[str, str, str], MockRequestObject]:
    mock_request_obj = MockRequestObject(mock_html)

    def mock_request_func(url: str, headers: str, timeout: str) -> MockRequestObject:
        return mock_request_obj

    return mock_request_func


def send_text_mock(obj, subject, message):
    pass
