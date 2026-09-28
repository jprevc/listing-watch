# Split into core, spider-plugin and notificator-plugin repos

The project is split into three repositories: a public **core** (web UI plus the Plugin interface, with no Spiders or Notificators of its own), a public **notificator plugin** repo, and a **private spider plugin** repo. Spiders are kept private because of legal concerns about scraping specific sites. Keeping them in their own private repo lets the core and notificators be published openly without exposing them. The core's public history was rewritten to remove all spider code, and its docs deliberately don't name any scraped site.

## Consequences

- Plugins are discovered through Python entry points (`listing_watch.spiders`, `listing_watch.notificators`). The core never imports a concrete Spider or Notificator.
- The public Docker image contains no Spiders and no browser. The deployable image is a private derivative (`FROM` the core image) built from the spider repo, and it owns the Chromium/Xvfb setup.
- Queries and Notification Profiles that name a Spider or Notificator no installed Plugin provides are kept but marked unavailable. They are never deleted.
