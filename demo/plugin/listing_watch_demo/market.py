"""
A fake classifieds site for the demo, served with the standard library only.

It starts with a few listings and posts a new one every `--interval` seconds, newest first, a few to
a page, so the demo Spider has pagination to follow and new Items to find on each run.

Run it with `python -m listing_watch_demo.market`.
"""
from __future__ import annotations

import argparse
import html
import os
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import parse_qs, urlsplit

PAGE_SIZE = 5

# (title, price in euros, location). Once every one is posted, the site starts again from the top,
# with new listing ids.
CATALOG = [
    ("Road bike, 56 cm aluminium frame", 420, "Ljubljana"),
    ("Fujifilm X-T3 body, low shutter count", 690, "Maribor"),
    ("Oak dining table with 4 chairs", 250, "Kranj"),
    ("Mechanical keyboard, brown switches", 65, "Celje"),
    ("Kids' balance bike", 40, "Koper"),
    ("Espresso machine, dual boiler", 780, "Ljubljana"),
    ("Hiking boots, size 43, worn twice", 85, "Novo Mesto"),
    ("27\" 1440p monitor", 180, "Velenje"),
    ("Vintage turntable, serviced", 210, "Ptuj"),
    ("Camping tent for 3, with footprint", 95, "Bled"),
    ("Electric scooter, 25 km range", 310, "Ljubljana"),
    ("Cast-iron skillet set", 55, "Kamnik"),
    ("Snowboard 158 cm with bindings", 230, "Kranjska Gora"),
    ("Standing desk frame, dual motor", 260, "Maribor"),
    ("Acoustic guitar, solid spruce top", 340, "Celje"),
    ("Baby stroller, travel system", 190, "Domžale"),
    ("Cordless drill with two batteries", 75, "Kranj"),
    ("Mid-century armchair, reupholstered", 320, "Ljubljana"),
    ("Kayak, sit-on-top, with paddle", 380, "Piran"),
    ("Board game bundle, 6 games", 70, "Nova Gorica"),
    ("Mountain bike, 29er hardtail", 650, "Škofja Loka"),
    ("Drone with 4K camera", 410, "Murska Sobota"),
    ("Bookshelf, solid pine", 60, "Postojna"),
    ("Running watch with GPS", 140, "Ljubljana"),
]


@dataclass(frozen=True)
class Listing:
    id: int
    title: str
    price: int
    location: str


class Market:
    """
    Which listings are posted at any moment. The first `initial` are posted from the start; after
    that, one more is posted every `interval` seconds.
    """

    def __init__(
        self, *, interval: float, initial: int = 6, start: float | None = None, clock: Callable[[], float] = time.time
    ) -> None:
        self.interval = interval
        self.initial = initial
        self.clock = clock
        self.start = clock() if start is None else start

    def posted_count(self) -> int:
        elapsed = max(0.0, self.clock() - self.start)
        return self.initial + int(elapsed // self.interval)

    def listing(self, listing_id: int) -> Listing | None:
        if not 1 <= listing_id <= self.posted_count():
            return None
        title, price, location = CATALOG[(listing_id - 1) % len(CATALOG)]
        return Listing(listing_id, title, price, location)

    def page(self, number: int) -> tuple[list[Listing], bool]:
        """The listings on page `number` (from 1, newest first), and whether there's a page after it."""
        count = self.posted_count()
        newest = count - (number - 1) * PAGE_SIZE
        ids = range(newest, max(0, newest - PAGE_SIZE), -1)
        listings = [listing for listing in map(self.listing, ids) if listing is not None]
        return listings, newest - PAGE_SIZE > 0


_STYLE = """
body { font: 16px/1.5 system-ui, sans-serif; max-width: 42rem; margin: 2rem auto; padding: 0 1rem;
       color: #222; background: #faf8f3; }
h1 { font-size: 1.5rem; margin-bottom: .25rem; }
.listing { display: flex; justify-content: space-between; gap: 1rem; padding: .75rem 0;
           border-bottom: 1px solid #ddd; }
.price { font-weight: 600; white-space: nowrap; }
.location { color: #666; font-size: .9rem; }
nav { margin-top: 1rem; display: flex; justify-content: space-between; }
"""


def _render(title: str, body: str) -> str:
    return (
        f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>"
        f"<style>{_STYLE}</style></head><body>{body}</body></html>"
    )


def render_page(market: Market, number: int, base_url: str) -> str:
    listings, has_next = market.page(number)
    rows = "".join(
        f"<article class='listing' data-id='{listing.id}'><div>"
        f"<a class='title' href='{base_url}/listing/{listing.id}'>{html.escape(listing.title)}</a>"
        f"<div class='location'>{html.escape(listing.location)}</div></div>"
        f"<span class='price'>€{listing.price}</span></article>"
        for listing in listings
    )
    prev_link = f"<a rel='prev' href='/?page={number - 1}'>← Newer</a>" if number > 1 else "<span></span>"
    next_link = f"<a rel='next' href='/?page={number + 1}'>Older →</a>" if has_next else ""
    return _render(
        "Demo Market",
        f"<h1>Demo Market</h1><p>A fake classifieds site. A new listing appears every "
        f"{market.interval:g} seconds.</p>{rows or '<p>No listings.</p>'}<nav>{prev_link}{next_link}</nav>",
    )


def render_listing(listing: Listing) -> str:
    return _render(
        listing.title,
        f"<p><a href='/'>← All listings</a></p><h1>{html.escape(listing.title)}</h1>"
        f"<p class='price'>€{listing.price}</p><p class='location'>{html.escape(listing.location)}</p>",
    )


def make_handler(market: Market, base_url: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # pylint: disable=invalid-name
            parts = urlsplit(self.path)
            body: str | None = None
            if parts.path == "/":
                try:
                    number = max(1, int(parse_qs(parts.query).get("page", ["1"])[0]))
                except ValueError:
                    number = 1
                body = render_page(market, number, base_url)
            elif parts.path.startswith("/listing/") and parts.path.removeprefix("/listing/").isdigit():
                listing = market.listing(int(parts.path.removeprefix("/listing/")))
                body = render_listing(listing) if listing else None
            encoded = (body or _render("Not found", "<h1>Not found</h1>")).encode("utf-8")
            self.send_response(200 if body else 404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0].strip())
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument(
        "--interval", type=float, default=float(os.environ.get("DEMO_MARKET_INTERVAL", "120")),
        help="Seconds between new listings.",
    )
    parser.add_argument(
        "--base-url", default=os.environ.get("DEMO_MARKET_BASE_URL", "http://localhost:8001"),
        help="Where a browser reaches this site; listing links point here.",
    )
    args = parser.parse_args()
    market = Market(interval=args.interval)
    server = ThreadingHTTPServer(("0.0.0.0", args.port), make_handler(market, args.base_url.rstrip("/")))
    print(f"Demo Market on port {args.port}, a new listing every {args.interval:g}s.", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
