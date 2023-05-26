import pytest
import requests
from tests import mocks


@pytest.fixture(name="mock_request_example")
def mock_request_example_fixture(monkeypatch):
    monkeypatch.setattr(requests, "get", mocks.mock_requests_get("example_test_html.html"))
