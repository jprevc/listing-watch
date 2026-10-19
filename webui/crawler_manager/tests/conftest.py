import contextlib

import pytest

from crawler_manager import services


@pytest.fixture(autouse=True)
def _no_cancel_request_poller(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Gives every `run_query` a stop signal that never fires, instead of the DB-polling thread: that
    thread reads through its own DB connection, which a non-transactional test doesn't allow. Tests
    of the poller itself opt out with `@pytest.mark.cancel_request_poller`.
    """
    if request.node.get_closest_marker("cancel_request_poller") is None:
        monkeypatch.setattr(services, "poll_cancel_requested", lambda run: contextlib.nullcontext(lambda: False))
