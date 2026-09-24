# Protagonist trait voting

Apply protagonist_votes.sql, then protagonist_vote_controls.sql, after the existing
profiles and protagonist-measures migrations. Keep this order for new databases;
existing installations only need the follow-up controls migration.

Any protagonist profile with all six scores filled in is eligible. Zero counts as
filled in. Gemini, moderator edits, and other trusted profile imports all qualify.
The controls migration enables existing complete profiles without regenerating
profiles or changing displayed scores. SUPABASE_SECRET_KEY stays on the backend.

## Scores and locks

Signed-in, non-banned readers can submit, update, or withdraw a whole-number
0-100 vote per trait per novel. Each account gets one vote per trait.
Unlocked scores are rounded from:
(default + sum of reader scores) / (1 + reader vote count).
Changes and deletions recalculate stored profiles in the same transaction, so
Finder and recommendations use the updated scores. Derived scores never feed
back into defaults.

Moderator edits become the new defaults and are displayed immediately. Subsequent
votes recalculate unlocked profiles against those defaults.
In Admin hub > Novel profiles > Vote distribution, Lock scores freezes all six
current protagonist scores. Votes can still be created, updated, and removed,
and remain visible to admins, but cannot change locked scores. Moderators can
edit scores while locked; Gemini cannot overwrite a locked profile. Unlock scores
immediately recalculates from the defaults and all current votes.
Locking does not change voting eligibility or erase votes.

## Admin moderation

Vote distribution shows exact score frequencies, defaults, current scores, lock
status, and paginated individual votes. Accounts > View votes shows a user's votes
across novels. Delete vote removes one trait vote; Delete all votes removes the
user's votes across every novel. Locked scores stay fixed in both cases. SPECIAL
access is required for moderation and locking. Reader responses exclude other
voters' identities. Ban an account separately to prevent new votes.

## Verification

These checks do not modify a live database:

```bash
python -m pytest tests/unit/test_protagonist_votes.py tests/unit/test_admin.py -q
python -m pytest tests/e2e/test_protagonist_voting.py -q
cd tests
npm ci
npm run test:votes
```

Use the project's Python environment; browser tests require Playwright Chromium.
The Node test runs both migrations in an isolated PostgreSQL-compatible PGlite
instance, covering manual profiles, zeros, nulls, locking, unlocking, recalculation,
deletions, and permissions.
