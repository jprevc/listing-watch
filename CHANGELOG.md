# Change Log

## [2.0.0] - 2021-08-14
### Added
- Support for Pushover notifications (https://pushover.net/)
- New option to send each new found item as a separate notification

### Changed
- Crawler configuration structure in .yaml files
    - Notification settings are now under separate field
    - message_body_format is now set for each notificator separately
