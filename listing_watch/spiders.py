from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Mapping, Sequence

from listing_watch.config_field import ConfigField

# The Item contract. An Item is one listing a Spider returns, as a dict of strings:
# - `title` and `url` are required in every Item.
# - `price` is optional.
# - Extra keys are allowed. Declare them in the Spider's `item_fields`, so users can use them in
#   message formats.
# The Core deduplicates and stores Items by their content, keeping `title`, `url` and `price`.
SpiderItem = dict[str, str]

# Keys every Item a Spider returns must have, and so every Spider must declare in `item_fields`.
REQUIRED_ITEM_FIELDS = ("title", "url")

# Fields every Item has, whatever its Spider declares: the required fields, plus `query`, which the
# Core sets to the Query's name before notifying (see crawler_manager.delivery in the web UI).
GUARANTEED_ITEM_FIELDS = ("query", *REQUIRED_ITEM_FIELDS)

class Spider(ABC):
    def __init__(self, query_name: str, url: str, *, config: Mapping[str, str] | None = None) -> None:
        """
        Constructs a spider. Spider has a "run" method, which will crawl the set query when invoked.

        :param query_name: Name of the query to be crawled.
        :param url: URL to be crawled.
        :param config: The Query's values for this Spider's `config_fields`, keyed by each field's key.
            Fields left blank by the user are absent.
        """
        self.query_name = query_name
        self.url = url
        self.config: dict[str, str] = dict(config or {})

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Name for the spider. This name is used when referring to spiders in the configuration files or when calling
        the spiders from the CLI.
        """

    # Keys this Spider's Items can have (see the Item contract above `SpiderItem`). Declared
    # per-subclass so callers (e.g. the web UI's message-format field) can look up what's available
    # without running the spider. Must include REQUIRED_ITEM_FIELDS; `query` is added by the Core,
    # so listing it is optional.
    item_fields: tuple[str, ...] = ()

    # The settings this Spider needs from the user, rendered by the Core as form inputs.
    config_fields: Sequence[ConfigField] = ()

    @abstractmethod
    def run(
        self, max_pages: int | None = None, should_stop: Callable[[], bool] | None = None
    ) -> list[SpiderItem]:
        """
        Runs crawling on the set query.

        :returns: The Items currently listed, each following the Item contract above `SpiderItem`.

        :param max_pages: For spiders that paginate, the maximum number of pages to crawl.
            `None` means unlimited (crawl until the last page). Ignored by spiders that
            don't paginate.
        :param should_stop: For spiders that paginate, an optional callable polled between page
            requests; once it returns True, crawling stops early and whatever was already
            collected is returned (no exception). Ignored by spiders that don't paginate -- a
            single request completes too fast to make a mid-run stop meaningful.
        """
