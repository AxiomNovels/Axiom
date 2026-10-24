# Admin novel deletion

Apply `database/delete_novel.sql` in Supabase after the existing profiles,
reading lists, reviews/replies, Home feature, protagonist voting/definition,
rebuild and Admin Hub migrations (including `rebuild_atomic_creation.sql` and
`remove_retired_profiles.sql`).
The existing Inbox `notifications` table must be installed. The migration is
repeatable and removes no novels when installed. Deploy it before the API/UI.

SPECIAL accounts can search the Admin Hub's **Remove Novels** tab or use
**Delete novel** on a novel page. Both controls confirm permanent deletion.
`DELETE /api/admin/novels/{id}` checks the current server-owned SPECIAL flag
and banned status. Its database function is callable only by the backend
service role and rechecks the actor's metadata. Ordinary users cannot delete
novels directly through Supabase either.

One transaction removes the novel, reading-list membership, upload-history IDs,
reviews, replies and likes, protagonist profiles/defaults/votes, per-novel
rebuild history, and the Home feature if it points to the novel. Matching
scraper staging records are removed by published novel ID or exact reading
source URL, if staging is installed. Rebuild counters are adjusted; shared
lists, accounts and unrelated novels remain. Any unexpected constraint failure
rolls everything back. The upload-history trigger also filters nonexistent IDs
from stale profile writes and locks valid novel references during those writes.

Each affected reading-list owner or uploader gets one ordinary, unread system
Inbox message, even if they qualify through both lists. It identifies the title
and explains the policy removal without linking to the deleted page. That
required notice is the only intentionally retained novel information. If Inbox
delivery fails, deletion rolls back. Repeating a completed deletion returns 404
without another notice. This does not email readers or block future reuploads.

Verification uses controlled API substitutes and isolated PGlite/Playwright;
no live Supabase data needs to be deleted:

```powershell
backend/.venv/Scripts/python.exe -m pytest -c tests/pytest.ini tests/unit/test_admin.py tests/e2e/test_novel_deletion.py
npm.cmd run test:sql --prefix tests
```
