import json
import pathlib
import re

import pytest

from listing_watch.__main__ import main
from listing_watch import notificators
from tests import mocks

# pylint: disable=unused-argument


@pytest.fixture(name="dummy_config")
def dummy_config_fixture(tmp_path: pathlib.Path):
    _create_dummy_config(tmp_path / "listing_watch.yaml", {"spiders": {}})


@pytest.fixture(name="example_dummy_config")
def example_dummy_config_fixture(tmp_path: pathlib.Path):
    _create_dummy_config(
        tmp_path / "listing_watch.yaml",
        {
            "spiders": {
                "example": {
                    "urls": {"dummy_url": ""},
                    "notifications": {
                        "email": {
                            "email_user": "dummy_email",
                            "email_password": "dummy_pass",
                            "recipients": "dummy_recipient_1,dummy_recipient_2",
                            "message_body_format": "URL: {url}\nTitle: {title}\nPrice: {price}\n",
                        }
                    },
                }
            }
        },
    )


def _create_dummy_config(path, content_dict):
    with open(path, "w+", encoding="utf-8") as file:
        json.dump(content_dict, file)


def test_main_basic(capsys):
    with pytest.raises(SystemExit):
        main(("--help",))

    _, err = capsys.readouterr()

    assert err == ""


def test_version(capsys):
    with pytest.raises(SystemExit):
        main(("--version",))

    out, _ = capsys.readouterr()

    assert re.match(r"(\d\.){2}\d", out)


def test_log_option_creates_log_file(dummy_config, tmp_path: pathlib.Path):
    log_path = tmp_path / "listing_watch.log"
    main(("scrape", "--config", str(tmp_path / "listing_watch.yaml")))

    assert not log_path.exists()

    main(("--log", str(log_path), "scrape", "--config", str(tmp_path / "listing_watch.yaml")))

    assert log_path.exists()


@pytest.mark.usefixtures("mock_request_example")
def test_running_scrape_command_returns_expected_items(monkeypatch, tmp_path: pathlib.Path, example_dummy_config):
    monkeypatch.setattr(notificators.EmailNotificator, "send_text", mocks.send_text_mock)

    main(
        (
            "scrape",
            "--config",
            str(tmp_path / "listing_watch.yaml"),
            "--cache",
            str(tmp_path / ".nc_cache"),
            "-s",
            "example",
        )
    )

    cache_file_path = tmp_path / ".nc_cache" / "example_cached.json"
    assert cache_file_path.exists()

    with open(cache_file_path, encoding="utf8") as cache_file:
        listings = json.load(cache_file)

    assert len(listings) == 2
