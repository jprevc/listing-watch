"""
Contains various Notificator implementations.
"""


from abc import ABC, abstractmethod
import os
import smtplib
import requests


class NotificatorBase(ABC):
    """
    Notificator base class. This class is meant to be subclassed for each implementation of different notification
    options.
    """

    def __init__(self, recipients):
        self.recipients = recipients

    @abstractmethod
    def send(self, subject, message):
        """
        Sends notification.

        :param subject: Subject (title) of notification.
        :type subject: str

        :param message: Message content.
        :type message: str
        """


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

    def send(self, subject, message):
        """
        Sends email message.

        :param subject: Subject of email.
        :type subject: str

        :param message: Email message content.
        :type message: str
        """
        email_password = os.environ.get('EMAIL_PASS')
        email_user = os.environ.get('EMAIL_USER')

        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
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

    def send(self, subject: str, message: str):
        """
        Sends a pushover notification.

        :param subject: Subject of push notification.

        :param message: Push notification message.
        """
        session = requests.Session()
        for user_key in self.recipients:
            payload = {"token": os.environ.get('PUSHOVER_APP_TOKEN'),
                       "user": user_key,
                       "title": subject,
                       "message": message}
            session.post('https://api.pushover.net/1/messages.json', data=payload, headers={'User-Agent': 'Python'})
