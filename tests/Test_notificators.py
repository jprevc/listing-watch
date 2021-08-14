"""
Contains tests for Notificator classes.
"""
import unittest
from itertools import product

from parameterized import parameterized

from ..notificators import PushoverNotificator, EmailNotificator
from .mocks import HttpsSessionMock, SmtpMock


class Test_PushoverNotificator(unittest.TestCase):
    """
    Tests for PushoverNotificator class.
    """
    num_test_messages = [1, 5, 10, 100]
    test_message_characters = [600, 300, 200]
    num_test_users = [1, 2, 3, 4]

    # create different test combinations for parameterization
    test_combs = list(product(num_test_messages, test_message_characters, num_test_users))

    comb_names = ["{}_messages_{}_chars_{}_users".format(num_messages, num_chars, num_users)
                  for (num_messages, num_chars, num_users) in test_combs]

    parameterized_val = [(comb_name, *test_comb) for comb_name, test_comb in zip(comb_names, test_combs)]

    def setUp(self):
        self.pushover = PushoverNotificator(['user_key_1'], 'app_token')

        # override _open_session with mocked version
        self._session_mock = HttpsSessionMock()
        self.pushover._open_session = lambda: self._session_mock

    def test_send_text(self):
        """
        Test that 'send_text' method correctly creates message text for a pushover notification.
        """
        self.pushover.send_text('test_subject', 'test_message')
        self.assertEqual(self._session_mock.simulated_messages[0], 'test_message')

    @parameterized.expand(parameterized_val)
    def test_minimal_number_of_sent_messages_when_divided(self, _, num_test_items, text_length, num_users):
        """
        Test that 'send_items' method correctly divides items if length of message exceeds 1024 characters.
        """
        self._send_test_items(num_test_items, text_length, num_users, send_separately=False)

        # minimal needed number of messages would occur if length of messages is perfectly divisible by 1024
        min_number_of_messages = (((text_length * num_test_items) // 1025) + 1) * num_users
        self.assertLessEqual(min_number_of_messages, len(self._session_mock.simulated_messages))

    @parameterized.expand(parameterized_val)
    def test_length_of_message_must_be_less_than_1024(self, _, num_test_items, text_length, num_users):
        """
        Test that 'send_items' method never sends a message where length exceeds char limit of 1024.
        """
        self._send_test_items(num_test_items, text_length, num_users, send_separately=False)

        # check that length of each message does not exceed 1024
        for message in self._session_mock.simulated_messages:
            self.assertLessEqual(len(message), 1024)

    @parameterized.expand(parameterized_val)
    def test_length_of_divided_messages_is_equal_to_original(self, _, num_test_items, text_length, num_users):
        """
        Test that total length of divided items in 'send_items' method is equal to original message.
        """
        self._send_test_items(num_test_items, text_length, num_users, send_separately=False)

        # check that sum of all messages lengths is equal to original text length
        messages_length_sum = sum(len(message) for message in self._session_mock.simulated_messages)
        original_txt_length = (text_length * num_test_items * num_users)
        self.assertEqual(original_txt_length, messages_length_sum)

    @parameterized.expand(parameterized_val)
    def test_send_items_separate_correctly_separates_items(self, _, num_test_items, text_length, num_users):
        """
        Test that 'send_items' method correctly sends each item separately if that is specified.
        """

        self._send_test_items(num_test_items, text_length, num_users, send_separately=True)

        self.assertEqual(num_test_items * num_users, len(self._session_mock.simulated_messages))

    def _send_test_items(self, num_test_items, text_length, num_users, send_separately):
        items = [{'data': "a"*text_length}]*num_test_items
        self.pushover.recipients = ['user_key']*num_users

        self.pushover.send_items('Test subject', items, '{data}', send_separately=send_separately)


class Test_EmailNotificator(unittest.TestCase):
    def setUp(self):
        self.email = EmailNotificator(['user_key_1'], 'test_email_user', 'test_email_pass')

        # override _get_smtp_session with mocked version
        self._smtp_mock = SmtpMock()
        self.email._get_smtp_session = lambda: self._smtp_mock

    def test_send_text(self):
        """
        Test that 'send_text' method correctly creates message text for email.
        """
        self.email.send_text('test_subject', 'test_message')
        self.assertEqual(self._smtp_mock.simulated_messages[0], b'Subject: test_subject\n\ntest_message')


if __name__ == '__main__':
    unittest.main()
