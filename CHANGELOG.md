# Change Log

## [Unreleased]
### Added
- A Query whose crawl fails on 3 runs in a row is Failing: its Notification Profiles get one alert
  with the latest error, and one "working again" message once a run's crawl succeeds.
- A self-contained demo (`docker compose up --build`): a fake classifieds site, a demo Spider Plugin
  that crawls it, and a local ntfy server for the notifications.

### Changed
- Each Item's Delivery is now tracked per Notification Profile: if a Notification Profile fails to send (or is Unavailable),
  its Items are sent with the Query's next run instead of being lost, for up to 7 days after they
  were found. A failed send no longer fails the run; the run history shows the pending count and
  the delivery errors instead.

### Fixed
- A "Run now" that overlaps a scheduled run of the same Query no longer sends the same Items to a
  Notification Profile twice.
- The Docker image's data volume is declared at `/app/data`. The relative path it used before is
  rejected by recent Docker versions when recreating a container.

### Removed
- `listing_watch.scrape`. Sending Items is done by the web UI.

## [4.1.0]
### Removed
- The built-in Spiders. Spiders now come only from Plugins, like Notificators, and the Core no longer
  depends on `requests`, `beautifulsoup4` or `playwright`. Queries whose Spider isn't installed are
  kept and shown as Unavailable.
- The browser and Xvfb setup from the Docker image. An image that needs a browser for its Spiders
  is built `FROM` the Core image.

## [4.0.0]
### Removed
- The Email, Pushover and ntfy Notificators. They now live in the
  [`listing-watch-notificators`](https://github.com/jprevc/listing-watch-notificators) Plugin, which
  registers them under the same names, so existing Notification Profiles keep working once it's
  installed. The Docker image installs it.

### Changed
- Published on PyPI as `listing-watch` (previously `news-crawlers`).

## [2.0.0] - 2021-08-14
### Added
- Support for Pushover notifications (https://pushover.net/)
- New option to send each new found item as a separate notification

### Changed
- Crawler configuration structure in .yaml files
    - Notification settings are now under separate field
    - message_body_format is now set for each notificator separately
