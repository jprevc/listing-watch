"""
Contains various mock classes which can be used in tests.
"""


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
