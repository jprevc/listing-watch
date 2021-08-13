import unittest

from ..notificators import PushoverNotificator, EmailNotificator
from .mocks import SessionMock, SmtpMock
from parameterized import parameterized


class Test_PushoverNotificator(unittest.TestCase):
    def setUp(self):
        self.pushover = PushoverNotificator(['user_key_1'], 'app_token')

        # override _open_session with mocked version
        self._session_mock = SessionMock()
        self.pushover._open_session = lambda: self._session_mock

    def test_send_text(self):
        self.pushover.send_text('test_subject', 'test_message')
        self.assertEqual(self._session_mock.simulated_messages[0], 'test_message')

    @parameterized.expand([('1_times_600_1_user', 1, 600, 1),
                           ('5_times_600_2_users', 5, 600, 2),
                           ('10_times_300_3_users', 10, 300, 3),
                           ('100_times_200_4_users', 100, 200, 4)])
    def test_send_items_correctly_divides_items(self, _, num_test_items, text_length, num_users):
        items = [{'data': "a"*text_length}]*num_test_items
        self.pushover.recipients = ['user_key']*num_users

        self.pushover.send_items('Test subject', items, '{data}')

        expected_number_of_messages = (((text_length * num_test_items) // 1025) + 1) * num_users
        self.assertEqual(expected_number_of_messages, len(self._session_mock.simulated_messages))

    @parameterized.expand([('1_message_1_user', 1, 600, 1),
                           ('5_messages_2_users', 5, 600, 2),
                           ('10_messages_3_users', 10, 300, 3),
                           ('100_messages_4_users', 100, 200, 4)])
    def test_send_items_separate_correctly_separates_items(self, _, num_test_items, text_length, num_users):
        items = [{'data': "a" * text_length}] * num_test_items
        self.pushover.recipients = ['user_key'] * num_users

        self.pushover.send_items('Test subject', items, '{data}', send_separate=True)

        self.assertEqual(num_test_items * num_users, len(self._session_mock.simulated_messages))


class Test_EmailNotificator(unittest.TestCase):
    def setUp(self):
        self.email = EmailNotificator(['user_key_1'], 'test_email_user', 'test_email_pass')

        # override _get_smtp_session with mocked version
        self._smtp_mock = SmtpMock()
        self.email._get_smtp_session = lambda: self._smtp_mock

    def test_send_text(self):
        self.email.send_text('test_subject', 'test_message')
        self.assertEqual(self._smtp_mock.simulated_messages[0], b'Subject: test_subject\n\ntest_message')


if __name__ == '__main__':
    unittest.main()
