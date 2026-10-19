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

### Watching and alerting

**Query**:
A saved search: one Spider pointed at one listing URL, run on a schedule, with Notification Profiles attached.
_Avoid_: Search, watch, job

**Notification Profile**:
A user's named, configured instance of a Notificator (e.g. "my ntfy topic"); one can be attached to many Queries.
_Avoid_: "Profile" alone in user-facing text, notificator config

**Delivery**:
One Item sent to one Notification Profile attached to the Item's Query; it is *pending* until that Profile's Notificator accepts it, then *delivered*, or *expired* if it stays pending too long after the Item was found. A pending Delivery is dropped if its Profile is detached from the Query.
_Avoid_: Notification, send

**Failing**:
The state of a Query whose crawl failed on each of its last few finished runs (cancelled runs don't count); it is Failing *since* the start of the first failed run in that streak, and stops being Failing when a run's crawl succeeds.
_Avoid_: Broken, down, erroring
