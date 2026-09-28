# Listing Watch

Watches classifieds/marketplace listings for new items and alerts users about them. The core is a web UI plus a plugin interface; every Spider and Notificator is supplied by a Plugin.

## Language

### Extension points

**Core**:
The web UI, scheduler and Plugin interface: everything except the Spiders and Notificators themselves.
_Avoid_: Host, app, main repo

**Plugin**:
An installable package that provides one or more Spiders and/or Notificators to the core.
_Avoid_: Addon, extension, handler

**Spider**:
A component that crawls one listing site and returns the items currently listed there.
_Avoid_: Crawler, crawler handler, scraper

**Notificator**:
A component that delivers messages to one notification channel (e.g. email, a push service).
_Avoid_: Notifier, notification handler

**Item**:
One listing a Spider returns. It always has a title and a URL, may have a price, and can carry any number of extra fields.
_Avoid_: Listing, result, ad

**Unavailable**:
The state of a Query or Notification Profile whose Spider or Notificator no installed Plugin provides.
_Avoid_: Broken, orphaned

**Config Field**:
A single setting a Spider or Notificator declares it needs from the user (e.g. an API token), which the core renders as a form input.
_Avoid_: Option, parameter
