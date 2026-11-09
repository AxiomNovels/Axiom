# Comment inbox notifications

Apply `database/comment_notifications.sql` in Supabase after `reviews.sql`,
`review_replies.sql`, and the existing production schemas for `profiles`,
`reading_lists` (including `visibility`), `reading_list_reviews`,
`reading_list_review_replies`, `friendships`, and `notifications` (including
`type` and `data`). Several of these older schemas are not defined by a
standalone migration in this repository. The migration is transactional and safe
to reapply. It does not backfill old activity or change existing table policies.
Deploy the updated `frontend/public/inbox.js` to enable discussion links.

- A new novel or reading-list reply notifies the author of its immediate parent
  comment, or the review author when it has no parent reply.
- New comments on reading lists, including replies, notify the list owner.
  If the owner is also the reply recipient, they receive just the reply notice.
- Authors never notify themselves. Banned senders and recipients are skipped.
- Rating-only reviews are silent. Adding text to a rating-only review sends a
  notice; editing existing text, re-saving it, changing ratings, likes, and
  deletions do not. Removing text and later adding it counts as a new comment.
- Reply recipients must still be able to see the reading list at delivery time
  (owner, public list, or accepted friend of the owner for a friends-only list).
  The destination page independently checks current access when opened.
- Notices contain the sender name and novel/list title, without copying comment
  text. They use the existing inbox unread count, read/unread, and delete actions.
  No emails are sent. Existing notices remain if a discussion is later deleted
  or its visibility changes, and its destination uses existing unavailable UI.

Database triggers distinguish inserts from updates even for concurrent upserts.
Notices commit with the comment and roll back if its transaction rolls back.
Delivery is best-effort, matching `core.notifications`: a failed notice emits a
database warning and does not block saving the comment. There is no delivery
retry queue. The trigger function has a fixed search path and no client execute
grants; recipient IDs come from stored relationships, never a notification API.

Run `npm.cmd run test:sql --prefix tests` for isolated PostgreSQL regression
coverage, including comment notifications, existing migrations, RLS, and bans.
