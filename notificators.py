from abc import ABC, abstractmethod
import os
import smtplib


class NotificatorBase(ABC):
    def __init__(self, recipients):
        self.recipients = recipients

    @abstractmethod
    def send(self, subject, message):
        pass


class EmailNotificator(Notificator):

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
