import json

import pytest

from news_crawlers import scrape


@pytest.fixture(name="initial_cache_file")
def initial_cache_file_fixture(tmp_path):
    cache_file_path = tmp_path / ".nc_cache" / "example_cache.json"
    cache_file_path.parent.mkdir(exist_ok=True, parents=True)
    with open(cache_file_path, "w+", encoding="utf8") as cache_file:
        json.dump({"example": [{"item_1": "some_content_1"}]}, cache_file)

    yield cache_file_path


def test_check_diff(initial_cache_file):
    crawled_data = {"example": [{"item_2": "some_content_2"}]}
    diff = scrape.check_diff(initial_cache_file.parent, crawled_data)

    assert diff == {"example": [{"item_2": "some_content_2"}]}

    newly_crawled_data = {"example": [{"item_2": "some_content_2"}, {"item_3": "some_content_3"}]}
    diff = scrape.check_diff(initial_cache_file.parent, newly_crawled_data)

    assert diff == {"example": [{"item_3": "some_content_3"}]}
