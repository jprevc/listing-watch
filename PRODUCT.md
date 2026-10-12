# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

A small household/group of people who share one self-hosted deployment, each with their own account. Each user configures and watches their own listing queries and notification profiles independently of the others on the same instance.

## Product Purpose

Listing Watch crawls configured listings/classifieds sites (e.g. car listings, general classifieds) for new items on a schedule, diffs results against previously found items, and notifies the user via Email, Pushover, or ntfy when something new shows up. Success is a user never having to manually re-check a listings site — new matches reach them as notifications.

## Positioning

An extensible, self-hosted crawler framework: sites to watch, schedules, and notification channels are all configured through a web UI and stored in a database — no config files or legacy JSON cache to hand-edit. New source sites are added as Spiders, installed from Plugins, rather than requiring a different tool per site. The Core itself ships no Spiders and no Notificators.

## Operating Context

- Self-hosted, home-server scale: Dockerized, expected to run continuously on a small/low-power box (not a hosted SaaS offering).
- Django web UI (`webui/`) for configuration, backed by SQLite; a separate scheduler process (`runscheduler`) triggers spider runs on cron/interval schedules.
- Multiple people share one deployment, each signed in with their own account.
- Spiders come from Plugins. A Spider that needs a browser brings it in a derived Docker image built `FROM` the Core image; the Core image has none.

## Capabilities and Constraints

- Per-user accounts: queries and notification profiles are private to the account that created them (a real, load-bearing feature, not incidental Django scaffolding) — each household member's setup stays separate on the shared instance.
- Notification profiles are reusable and attachable to any of that user's queries; one profile per type can be marked default and is pre-selected (still removable) when adding a new query.
- Three Notificators from the public Notificator Plugin: Email (Gmail SMTP), Pushover, ntfy — each configured once as a profile, mixed/matched per query.
- Scheduling is per-query: simple interval or cron expression.
- Adding a new source site means writing a new `Spider` subclass in a Plugin, returning Item dicts whose keys match the placeholders used in a profile's `message_body_format`.
- Distributed as an installable package (PyPI: `listing-watch`) and as Docker images (Docker Hub), open source (MIT license) — published for other self-hosters to run, even though the design target is the maintainer's own household deployment.

## Brand Commitments

- Name: Listing Watch.
- An existing, deliberate visual identity is already implemented in `webui/templates/base.html` (Tailwind + Alpine.js + htmx, Space Grotesk / IBM Plex Mono, a light "paper ledger" / dark "ink-and-brass watch console" theme pair, with a defined accent/live-status color story) — this is incumbent visual truth to treat as evidence, not to redesign from scratch without cause.

## Evidence on Hand

- README.md documents the architecture, notification setup, spider extension pattern, and web UI usage in detail.
- No testimonials, case studies, press, or usage benchmarks exist; future work must not fabricate any.

## Product Principles

1. Configuration lives in the web UI and the database — never require hand-edited config files or JSON caches.
2. Per-user isolation on a shared instance is a real constraint: queries, profiles, and history must stay scoped to the account that owns them.
3. Adding a new listings source should mean writing one spider, not building a new tool.
4. The product is built and tuned for continuous, unattended operation on modest self-hosted hardware, not for a hosted multi-tenant SaaS.
5. Notifications are the product's payoff moment — channel setup (Email/Pushover/ntfy) should stay simple and reusable across queries.
