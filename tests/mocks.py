"""
Contains various mock classes which can be used in tests.
"""
import dataclasses
import pathlib


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


def mock_get_raw_html() -> str:
    mock_html_path = pathlib.Path(__file__).parent / "res" / "example_test_html.html"

    with open(mock_html_path, encoding="utf8") as file:
        html_content = file.read()

    return html_content


@dataclasses.dataclass
class MockRequestObject:
    text = mock_get_raw_html()


def mock_requests_get(url, headers, timeout) -> MockRequestObject:
    return MockRequestObject()
