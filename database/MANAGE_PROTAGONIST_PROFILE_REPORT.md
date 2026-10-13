Manage Protagonist Profile — implementation report (October 10, 2026)

The Admin Hub now has a **Manage Protagonist Profile** tab. SPECIAL accounts can
view and edit every trait's name and full scoring prompt, add or delete traits,
and edit shared scoring instructions. The editor stages changes, identifies the
affected traits, and requires confirmation before permanently clearing their data.
Conflicting saves preserve the draft and ask the administrator to reload.

The implementation is complete in this checkout. **The migration has not been
applied to live Supabase, and the application has not been deployed.** No live
novel data was changed, and no Gemini calls were made during verification.

To enable the feature on the existing database:

1. Apply [manage_protagonist_profile.sql](manage_protagonist_profile.sql) in the
   Supabase SQL editor. It requires the existing Admin Hub and voting migrations:
   `admin_hub.sql`, `protagonist_votes.sql`, and `protagonist_vote_controls.sql`.
   If those are already installed, only the new migration is needed.
2. Deploy the matching backend and frontend together. The new profile and voting
   writes require a definition revision, so an old backend cannot safely write
   through the new RPC contracts. Refresh already-open browser pages.
3. Open Admin Hub → Manage Protagonist Profile. Future routine changes require
   neither source edits nor manual SQL. The existing profile rebuild tools remain
   under Novel profiles.

For a fresh database, apply the existing profile/table migrations, voting and
voting-control migrations, and Admin Hub migration before this new migration.
Keep `protagonist_rebuild_jobs.sql` installed for the existing rebuild interface.
Do not reapply the older trait/voting migrations after the new migration: they
contain retired, fixed trait definitions. Reapplying the **new** migration is
tested and preserves the saved definition and current profile data.

The database design keeps the existing wide `protagonist_profiles` table and its
relationships. A singleton `protagonist_definition` record stores an ordered trait
list, shared instructions, and a monotonically increasing revision. A restricted
`SECURITY DEFINER` function performs the following operations in one transaction:

| Change | Result |
| --- | --- |
| Add a trait | Add a nullable, range-checked `smallint` score column; existing traits survive. |
| Change a name or prompt | Set that column to NULL for every novel; remove that key from voting defaults and delete all votes for it. |
| Delete a trait | Remove its defaults and votes, then drop its column without `CASCADE`. |
| Change shared instructions | Clear scores, defaults, and votes for every current trait. |
| Save without changes | Preserve data and revision. |

Identifiers are validated and quoted; prompts are data, never SQL. The function
uses the same advisory lock as voting/profile writes, plus a table lock for
schema changes. A failure, including an unknown dependent view that prevents a
column drop, rolls back the entire change. This follows PostgreSQL's documented
[dynamic SQL identifier quoting](https://www.postgresql.org/docs/17/plpgsql-statements.html).
After a change it sends the documented
[PostgREST schema cache reload notification](https://postgrest.org/en/latest/references/schema_cache.html).
Large catalogue changes therefore hold database locks while clearing affected data.

Only the backend service role can call the mutation functions. HTTP endpoints
reuse `require_special`, server-owned privilege metadata, and banned-account
checks. The definition table enables RLS and has the restrictive banned-account
policy. A separate public, read-only function supplies definitions to public
profile displays, voting guides, and Finder. Existing vote identity privacy and
service-key boundaries are preserved.

Every generated profile carries the definition revision used for its prompt and
Gemini response schema. Saves check that revision under the same database lock.
This includes uploads, signed preview tokens, CLI profiling, scraper publishing
through the existing shared profiler, manual Admin Hub scores, and rebuild jobs.
A prompt-only edit invalidates old preview tokens even when the trait keys have
not changed. Old generation results and stale voting submissions cannot restore
cleared data. Runtime definitions are read per operation; they are not held in a
process-wide cache.

Judgments made while implementing the request:

- The uploaded file is actually named `database/table_schema.js` (singular),
  and contains both the six retired columns and ten current columns. I reviewed
  it and left the user-provided file unchanged. The migration starts from the ten
  current traits and the scoring content in `backend/profiler/prompt.py`, preserving
  existing defaults/votes for current keys and cleaning retired keys from defaults
  and votes. Unmanaged retired columns are left untouched and cannot be reused as
  new trait keys accidentally.
- A display name is separate from its stable storage key. Renaming a trait still
  clears all its data, as requested; it does not need a physical column rename.
  Adding/deleting traits performs actual column DDL automatically. Shared rules
  and prompt edits require transactional cleanup rather than structural DDL.
- Locks remain enabled after definition changes. Their affected scores are cleared
  because old scores would contradict the new definition. Gemini continues to
  respect those locks; unlock an affected profile before using the existing rebuild
  feature. Unchanged traits retain their displayed scores, defaults, and votes.
- Profiles must contain 1–50 traits, with whole-number scores from 0–100. An empty
  definition is rejected so completeness, voting, and generation have meaningful
  behavior. Trait names/keys must be unique; keys have a restricted SQL-safe format.
- Unchanged voting defaults remain separate from derived scores, including when
  other traits become incomplete. Vote removal still recalculates surviving,
  unlocked traits. Adding a trait closes new voting until every current trait has
  a score; deleting a trait can make a previously incomplete profile complete.
- Finder, search filter labels, recommendations, the novel profile, public scoring
  guide, reader voting, manual score editing, and admin vote distributions all use
  current definitions. Retired query parameters retain the existing behavior of
  being ignored. Scoring guides render the current prompt as text, including markup
  characters, and voting exposes a collapsible guide for each trait.
- The initial rubric is retained in `default_definition.json` for bootstrap and
  offline compatibility/testing. It is **not** a runtime fallback if database
  definitions are unavailable. The fixed wrapper still supplies novel evidence and
  the structured score contract; trait scoring instructions come from the database.
- An existing missing closing section tag in `admin.html` was repaired so Accounts,
  Novel profiles, Home page, and the new tab are independent. No second rebuild
  feature was added.

Verification completed locally:

- **135 targeted Python tests passed**, covering admin authentication, score writes,
  voting, dynamic definition validation, prompt/schema snapshots, stale preview
  tokens, custom-trait search/recommendations, rebuild eligibility, existing search
  behavior, and the profiler's original rubric assertions.
- **11 browser scenarios passed** across the complete browser run and focused
  final reruns. They cover staged add/edit/delete, canceling confirmation, affected-data
  notices, draft preservation after revision conflicts, mobile layout, current
  trait labels/prompts, safe text rendering, reader voting, locking/unlocking,
  moderation, and manual score submission with its definition revision.
- Both isolated database suites passed: the existing legacy voting suite and the
  new dynamic-definition suite. The new suite checks actual column creation/removal,
  migration of the uploaded mixed column layout, cleanup across multiple novels,
  locked profiles, unaffected data, partial baselines, stale revisions, failed-DDL
  rollback, migration reapplication, and anonymous/authenticated RPC denial.
- JavaScript syntax checks and `git diff --check` passed. Mobile editor output was
  visually inspected. Database tests use PGlite and browser APIs are intercepted;
  live Supabase/PostgREST cache delivery and production deployment were not tested.

The complete repository suite is not green for existing reasons. The fast runner
stops during collection because `tests/unit/test_auth_model.py` imports the removed
`AuthRequest`. Running the broader suite with that file excluded produced **238
passes and three failures** at that point in development:

| Existing test | Mismatch |
| --- | --- |
| `tests/unit/test_recommendation_service.py::test_tags_and_protagonist_have_equal_weight` | Uses retired `impulsivity`; the current seed uses different keys. |
| `tests/integration/test_recommendations.py::test_similar_endpoint_searches_beyond_first_page` | Expects genre-based similarity, while the implementation intentionally uses tags. |
| `tests/unit/test_royalroad_discovery.py::test_source_refusal_stops_scraping_instead_of_retrying_pool[503]` | Expects an HTTP 503 to abort discovery; the existing code continues to the next candidate. |

The two recommendation mismatches were also reproduced using the original
recommendation implementation read from Git. Their assertions and the unrelated
scraper/auth implementation were not weakened or changed. Tests directly affected
by the new API were updated to supply explicit definition fixtures and revisions;
the obsolete six-trait retirement assertion now verifies the actual seed contract.
The browser fixture deliberately uses a custom six-trait definition to prove that
rendering follows the API rather than a hard-coded ten-trait list.

Reproduction commands are in [tests/README.md](../tests/README.md). The targeted
Python command used was:

```powershell
backend/.venv/Scripts/python.exe -m pytest -c tests/pytest.ini tests/unit/test_admin.py tests/unit/test_protagonist_votes.py tests/unit/test_protagonist_definition.py tests/unit/test_profile_retirement.py tests/unit/test_search_service.py tests/unit/test_latency_paths.py tests/integration/test_api_routes.py backend/profiler/test_profiler.py -q -p no:cacheprovider
npm.cmd run test:votes --prefix tests
npm.cmd run test:definitions --prefix tests
backend/.venv/Scripts/python.exe -m pytest -c tests/pytest.ini tests/e2e/test_protagonist_voting.py -q -p no:cacheprovider
```

Files changed or added are listed below. Generated test screenshots, caches,
`node_modules`, and environment files are not included in the deliverable.

| File | Change |
| --- | --- |
| `README.md` | Modified |
| `backend/models/protagonist_definition.py` | Added |
| `backend/profiler/default_definition.json` | Added |
| `backend/profiler/gemini.py` | Modified |
| `backend/profiler/profile_novel.py` | Modified |
| `backend/profiler/prompt.py` | Modified |
| `backend/profiler/regenerate_profiles.py` | Modified |
| `backend/profiler/test_profiler.py` | Modified |
| `backend/routes/admin.py` | Modified |
| `backend/routes/novels.py` | Modified |
| `backend/routes/protagonist_votes.py` | Modified |
| `backend/routes/search.py` | Modified |
| `backend/services/novel_profiling_service.py` | Modified |
| `backend/services/protagonist_definition_service.py` | Added |
| `backend/services/protagonist_rebuild_service.py` | Modified |
| `backend/services/recommendation_service.py` | Modified |
| `backend/services/search_service.py` | Modified |
| `database/MANAGE_PROTAGONIST_PROFILE_REPORT.md` | Added |
| `database/PROTAGONIST_VOTING.md` | Modified |
| `database/manage_protagonist_profile.sql` | Added |
| `frontend/public/admin-protagonist.js` | Added |
| `frontend/public/admin-votes.js` | Modified |
| `frontend/public/admin.css` | Modified |
| `frontend/public/admin.html` | Modified |
| `frontend/public/admin.js` | Modified |
| `frontend/public/finder.js` | Modified |
| `frontend/public/novel.js` | Modified |
| `frontend/public/protagonist-profile-info.html` | Modified |
| `frontend/public/protagonist-profile-info.js` | Modified |
| `frontend/public/protagonist-votes.js` | Modified |
| `frontend/public/search.js` | Modified |
| `tests/README.md` | Modified |
| `tests/e2e/test_protagonist_voting.py` | Modified |
| `tests/integration/protagonist_definition_database.mjs` | Added |
| `tests/integration/test_api_routes.py` | Modified |
| `tests/integration/test_recommendations.py` | Modified |
| `tests/package.json` | Modified |
| `tests/unit/test_admin.py` | Modified |
| `tests/unit/test_latency_paths.py` | Modified |
| `tests/unit/test_profile_retirement.py` | Modified |
| `tests/unit/test_protagonist_definition.py` | Added |
| `tests/unit/test_protagonist_votes.py` | Modified |
