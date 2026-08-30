import pytest
from django.db import IntegrityError

from crawler_manager.models import FoundItem, Query

pytestmark = pytest.mark.django_db


@pytest.fixture(name="query")
def query_fixture() -> Query:
    return Query.objects.create(name="test_query", spider_name="example", url="https://example.com")


def test_query_str(query: Query) -> None:
    assert str(query) == "example/test_query"


def test_found_item_dedup_constraint(query: Query) -> None:
    FoundItem.objects.create(
        query=query,
        query_name=query.name,
        spider_name=query.spider_name,
        payload={"title": "a"},
        content_hash="hash1",
    )
    with pytest.raises(IntegrityError):
        FoundItem.objects.create(
            query=query,
            query_name=query.name,
            spider_name=query.spider_name,
            payload={"title": "a"},
            content_hash="hash1",
        )
