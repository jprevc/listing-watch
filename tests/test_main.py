import json
import pathlib
import re

import pytest

from news_crawlers.__main__ import main


@pytest.fixture(name="dummy_config")
def dummy_config_fixture(tmp_path: pathlib.Path):
    config_path = tmp_path / "news_crawlers.yaml"

    dummy_config: dict[str, dict] = {"spiders": {}}

    with open(config_path, "w+", encoding="utf-8") as file:
        json.dump(dummy_config, file)


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


def test_log_option_creates_log_file(dummy_config, tmp_path: pathlib.Path):  # pylint: disable=unused-argument
    log_path = tmp_path / "news_crawlers.log"
    main(("scrape", "--config", str(tmp_path / "news_crawlers.yaml")))

    assert not log_path.exists()

    main(("--log", str(log_path), "scrape", "--config", str(tmp_path / "news_crawlers.yaml")))

    assert log_path.exists()
