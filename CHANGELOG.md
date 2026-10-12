# Change Log

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
