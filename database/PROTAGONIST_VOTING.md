# Protagonist trait voting

Apply protagonist_votes.sql, then protagonist_vote_controls.sql, after the existing
profiles and protagonist-measures migrations. Keep this order for new databases;
then apply `admin_hub.sql` and `manage_protagonist_profile.sql`. Existing databases
with voting controls and Admin Hub already installed only need
`manage_protagonist_profile.sql`. Do not reapply the older trait migrations after it.

## Admin rebuild history

Apply `protagonist_rebuild_jobs.sql` after the profiles and protagonist-measures
migrations, before using Admin hub > Novel profiles > Protagonist profile rebuilds.
The migration is safe to reapply: it adds the `not_needed` item status used to
record complete profiles that an outdated-only run deliberately skips.

Any protagonist profile with all currently configured scores filled in is eligible. Zero counts as
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
In Admin hub > Novel profiles > Vote distribution, Lock scores freezes all
current protagonist scores. Votes can still be created, updated, and removed,
and remain visible to admins, but cannot change locked scores. Moderators can
edit scores while locked; Gemini cannot overwrite a locked profile. Unlock scores
immediately recalculates from the defaults and all current votes.
Locking does not change voting eligibility or erase votes. Definition edits are
the exception: changing a trait name or prompt clears that trait across all
novels, including locked ones. Changing shared instructions clears every trait.
The definition revision guards profile saves and votes against stale prompts.
See [the implementation report](MANAGE_PROTAGONIST_PROFILE_REPORT.md).

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
npm run test:definitions
```

Use the project's Python environment; browser tests require Playwright Chromium.
The original Node test runs the legacy voting migrations in an isolated PostgreSQL-compatible PGlite
instance, covering manual profiles, zeros, nulls, locking, unlocking, recalculation,
deletions, and permissions.
