# Track each Delivery per Item and Notification Profile

Items are saved before they are sent, and later runs only send Items they haven't seen before. So if sending failed, those Items were never sent, not even on a later run (#3). We now record one Delivery per Item and per Notification Profile that was attached to the Item's Query when the Item was found. A Delivery stays *pending* until that Profile's Notificator accepts it. Each run of the Query sends what is still pending together with its new Items, so a Profile that already received an Item never gets it again.

## Considered Options

- **Retry only the failed (Profile, Items) pairs.** This is the same bookkeeping, but recording only failures. It can't answer "what has this Profile received?", so it was rejected.
- **Show the gap and resend by hand.** Nobody watches scheduled runs, which are exactly the runs this product exists for, so this was rejected.

## Consequences

- A run whose crawl succeeded is `success` even when some of its Deliveries are still pending. The run history shows the pending count instead. A failed send no longer loses Items, so it no longer fails the run. It also no longer makes the next run re-crawl every page, because the "first successful run crawls all pages" rule counts only `success` runs.
- Pending Deliveries *expire* 7 days after their Item was found, so fixing a Profile weeks later doesn't flood it with stale listings. An Unavailable Profile is skipped rather than tried and failed. Its Deliveries stay pending, but the 7-day clock still runs.
- Deliveries are only created for Profiles attached when the Item is found. A newly attached Profile gets no backlog, and detaching a Profile drops its pending Deliveries. Changing which Profile an attachment points at counts as detaching the old Profile and attaching the new one, and deleting a Query detaches all of its Profiles. Items found before this change have no Deliveries.
