# Axiom audit — 22 October 2026

Local code fixes and tests are complete for the items below. This is **not a
certification of the whole application**. No production data, secrets, or live
database policies were changed. The repository was clean before this work.

## Coverage and limits

Reviewed the FastAPI routes, models, auth/database helpers, recommendation and
profiling services, browser scripts, Node server, Cloudflare Worker, SQL files,
test setup, manifests, and documentation. Reviewed scraper URL handling,
parsing, discovery and publishing paths, and the separate legacy SQLite code.
Parsed 108 Python files and syntax-checked 26 JavaScript files. Checked HTML
IDs and local script/style paths. Inspected API boundaries, ownership checks,
privacy filtering, session handling, vote transactions and migration ordering.

This was not an exhaustive visual/accessibility review of every page. Some
large discovery utilities, old staging fixtures, profiler playgrounds and
historical documents received only targeted inspection. Generated assets,
vendor packages, caches, user database contents and secret values were excluded.
The live schema, deployed policies, storage rules, provider limits, and actual
Gemini/scraping/email integrations were not verified.

## Fixed bugs and manual checks

Use local servers and a **separate disposable test database** for these checks.
Use fake data for security checks. Never point security probes at production.
Database fixes below require the migrations described later in this report.

| # | Severity | Root cause and fix | Manual reproduction / expected result after fix |
|---|---|---|---|
| 1 | P1 | `routes/auth.py`: signup/login mutated the shared Supabase client's session. Both now use isolated clients. | Log in as two test users in separate browsers, alternating requests. Each browser must keep its own account; public requests must stay anonymous. The automated test also asserts that shared auth methods are never called. |
| 2 | P1 | Signup deleted an Auth account whenever profile insertion failed. A repeated signup or ambiguous database failure did not prove that account was newly created. Removed this unsafe deletion and separated duplicate errors from outages. | In a test environment, fail profile insertion after signup. Expect 503 and confirm the Auth account still exists. Retry an existing email; its data must survive. |
| 3 | P2 | Username lookup treated `_` and `%` as SQL pattern wildcards. Escape them before `ilike`. | Create `reader_one` and `readerXone`. Logging in with `reader_one` must resolve only the first account. |
| 4 | P1 | Wattpad accepted arbitrary URLs; WebNovel trusted a domain substring. Added exact source host, scheme, credentials and port checks before network access. | Submit a localhost URL as Wattpad, or a localhost URL with `?webnovel.com` as WebNovel. Expect 422, without an outbound fetch. Use the isolated regression test to verify no request occurs. |
| 5 | P1 | Scrapers and review collectors followed redirects without validating each destination. Added bounded same-source redirects across the HTTP transports. | Run `test_redirect_checks_destination_before_request` in the audit regression file. A mocked source redirect to localhost must be rejected before a second request. Valid relative redirects must still work. |
| 6 | P2 | Upload diagnostics exposed exception text and submitted URLs in logs and headers. Retained only exception type and HTTP status. | Cause a mocked fetch error containing a fake secret. Check `X-Scrape-Debug` and application logs: the fake secret and full URL must be absent. |
| 7 | P1 | Search tags were interpolated into HTML. Build escaped tag markup from text nodes. | In a local fixture, use a tag `<img src=x onerror="alert(1)">`. Search must show the literal text, with no image or script execution. |
| 8 | P1 | Reader avatar HTML escaped text but not attribute quotes. Escape both quote types. | In a local fixture, set the avatar value to `x" onerror="alert(1)`. The rendered image must have no `onerror` attribute. |
| 9 | P1 | Novel reading links accepted executable URL schemes. Only HTTP/HTTPS links are rendered. | Give a local novel fixture a `javascript:alert(1)` reading link. No button for it should appear; a normal HTTPS link should still work. |
| 10 | P1 | The checked-in profiles policy exposed all columns, bypassing friends-only API filtering. Added restrictive owner reads and a public view containing only ID/username. | As test user B, query profiles through Supabase REST for user A. A's row must be hidden. Anonymous username lookup must still work and must not expose social fields. |
| 11 | P1 | List membership RLS checked the membership user, but not the parent list owner. Added a restrictive parent-ownership policy. | As B, insert or move a membership into A's list using direct REST. Expect rejection. Adding to B's own list must work. |
| 12 | P2 | Reply updates could change parents and form cycles or move discussions. Added immutable thread/author checks and self-parent rejection. | In a test DB, try making a reply its own parent or moving it under its child. Both must fail; editing its text must work. |
| 13 | P2 | Catalogue/search/options stopped at the server row cap. Added ordered page reads. | Seed 1,101 local novels with unique tags. The last novel must appear in catalogue/search and its tag in finder options. |
| 14 | P2 | Reader activity sorting considered only the first 100 names and ordered private accounts by hidden heartbeat. Read all candidates and keep private accounts in name order. | Make reader 105 the most recently active public account. It should appear first. Change private readers' activity timestamps; their relative name order must not change. |
| 15 | P2 | Admin activity sort compared real datetime objects to empty strings and stopped at the row cap. Normalize sort values and page the profiles. | Open the admin activity sort with one never-signed-in user and one signed-in user. Expect no 500; newest sign-ins come first. |
| 16 | P2 | A transient session refresh failure cleared login. Backend now distinguishes invalid tokens from provider outages; frontend retains login on temporary errors. | Return 503 from the local refresh API. The stored session must remain. Return 401 for an invalid token; it must clear. |
| 17 | P2 | Failed refreshes near expiry rescheduled immediately; late refresh replies could restore logout. Added a 30-second retry floor and stale-session check. | Simulate a refresh outage near expiry and inspect Network: no rapid retry loop. Delay a successful refresh, log out, then release it: the user must stay logged out. |
| 18 | P2 | Backend wake polling could leave a permanent blocking overlay. Added request timeouts and a 90-second polling window. | Point a local runtime config at an unavailable test API. The overlay should disappear after about 90–102 seconds so page error states remain usable. |
| 19 | P1/P2 | Node path containment accepted sibling directories; malformed percent encoding could reject the request handler. Added relative-path containment and guarded decoding. | Run `test_static_server.py`. Its disposable sibling sentinel must never be served; `/%` returns 400 and the next normal request returns 200. |
| 20 | P3 | `Number(null)` displayed missing chapter counts as zero. Preserve missing values in shared formatting, search, novel and upload views. | Use a novel with a null chapter count: no zero count should appear. A true count of zero must still display zero. |
| 21 | P2 | Removing a review comment hid the owner's delete action and any replies. Keep owned and replied-to reviews visible. | Write a review, add a reply, then clear the review text. The discussion must remain visible and the owner must still be able to delete the review. Repeat for a list review. |
| 22 | P3 | Malformed hash escapes threw while focusing a review and made the whole discussion look unavailable. Match the raw ASCII target ID. | Open a novel/list discussion with `#%` in the URL. Reviews should still load. Normal review anchor links should still focus their target. |
| 23 | P3 | Rendering each inbox card requested the unread badge again. Refresh only after a read-state change. | Load an inbox with many messages while watching Network. Badge requests must not grow one-for-one with message count. Toggling read state must still refresh the badge. |
| 24 | P2 | Unread counts used the length of a capped result page. Use the database's exact count. | Seed 1,500 unread messages in a test DB. The count endpoint must return 1,500. |
| 25 | P2 | A failed profile load left an editable blank form that could overwrite saved fields. Disable saving until loading succeeds. PATCH also now preserves omitted fields. | Fail profile GET and confirm Save is disabled. Send a partial PATCH with gender/city; omitted social fields and privacy settings must remain unchanged. |
| 26 | P3 | Avatar export ran outside cleanup handling and could leave Save disabled after an image error. Move export inside the guarded operation. | Make the local image export fail. The button must become enabled again and show the error state. |
| 27 | P2 | Rebuild creation checked then inserted across separate requests, allowing duplicate or partial jobs. Added a transaction with an advisory lock and atomic item insertion. Workers now claim queued jobs/items conditionally; progress reads all pages. | Start two rebuilds together in a test deployment. Only one may start. Retry a claimed job: no duplicate generation. For a job over 1,000 items, totals must stay correct. |
| 28 | P3 | Admin polling scheduled a new interval even when its first response was terminal, and requests could overlap. Schedule the next poll only after an active response finishes. | Open a completed/cancelled rebuild. Polling must stop. Slow an active response: only one poll should be in flight. |
| 29 | P2 | Cloudflare served assets before the Worker, bypassing dynamic sitemap/noindex handling. Run the Worker first, handle clean HTML URLs and bound sitemap API waits. | In a staging deployment, request `/sitemap.xml`: it should include available novels. `/login.html` and `/login` should carry noindex when served. An unavailable API must return the fallback sitemap within about four seconds. Local Worker deployment was not performed. |
| 30 | P2 | Royal Road discovery swallowed HTTP 503 as a broken individual book. Stop immediately on source unavailability while retaining isolated-500 tolerance. | Run the existing source-refusal regression: the first mocked 503 must stop discovery without requesting the remaining pool. |
| 31 | P1/P2 | Offline tests loaded real credentials; the live runner accepted the ordinary project, used the wrong API port, and leaked a backend process if frontend startup failed. Isolate offline settings, reject matching projects, set API_BASE and clean up failed startup. | Run the full runner with matching project URLs: it must refuse before starting live services. With a dedicated project, the frontend must target port 8100. Force frontend launch failure: the backend must stop. |
| 32 | P2/P3 | Stale tests imported a removed model, ranked genre-only fixtures against tag-based recommendations, and expected obsolete voting/login UI. Updated fixtures/selectors while preserving behavior assertions; live users now get profiles. | Run the suites below. The recommendation test must still select ID 502 beyond the first page; ineligible voting must still have no inputs. The live journey still requires its own database. |
| 33 | P3 | README advertised retired profiling commands; the environment template omitted the service key. Corrected protagonist instructions and added an empty backend-only key setting. | Follow the README preview command; it should resolve the existing module. A fresh template should show the required secret-key setting without a real secret. |

## Deployment order

1. Review and back up the target database using your normal deployment process.
2. Apply `database/audit_hardening.sql` after profiles, reading lists, review
   replies and admin hub migrations. It preserves existing ban policies.
3. Apply `database/rebuild_atomic_creation.sql` after
   `database/protagonist_rebuild_jobs.sql`, **before deploying the new backend**.
4. Deploy backend/frontend together. No packages were installed or upgraded.

Both new migrations were applied twice in disposable PGlite, including tests
under anon, authenticated and service roles. They were not applied to Supabase.
Existing malformed memberships/reply cycles are not silently repaired.

## Verification

Baseline: fast runner failed collection on the removed `AuthRequest`. Excluding
that file gave 250 passes and two failures (503 handling and stale recommendation
fixture). The original voting SQL suite passed.

Checks run after fixes:

- `backend/.venv/Scripts/python.exe tests/run_all.py --fast` — final run: **285 passed**.
- `backend/.venv/Scripts/python.exe tests/run_all.py` — offline suites passed;
  live phase correctly blocked because the test and ordinary project URLs match.
- `backend/.venv/Scripts/python.exe -m pytest -c tests/pytest.ini tests/e2e --browser-channel msedge -p no:cacheprovider -q`
  — first run: 19 passed, one stale voting-text failure, one live test skipped.
- `backend/.venv/Scripts/python.exe -m pytest -c tests/pytest.ini tests/e2e/test_audit_browser.py tests/e2e/test_protagonist_voting.py --browser-channel msedge -p no:cacheprovider -q`
  — **16 passed** after correcting the stale assertion and adding the avatar-error test.
  The other five isolated browser tests passed in the earlier full browser run.
- `npm.cmd run test:votes --prefix tests` — passed.
- `npm.cmd run test:definitions --prefix tests` — passed.
- `npm.cmd run test:trait-migrations --prefix tests` — passed.
- `npm.cmd run test:sql --prefix tests` — all 20 SQL files passed.
- `npm.cmd audit --prefix tests --json` — zero reported vulnerabilities for its
  one dependency. This does not audit the Python environment.
- `backend/.venv/Scripts/python.exe -m pip check` — passed.
- Python AST parsing, `node --check`, HTML duplicate-ID/asset checks — passed.
- `git diff --check` — passed. No actual `.env` file changed.

There is no configured production build, lint, or type-check command. The
frontend is static and has no bundling step. Worker deployment, live providers,
and a complete live reader journey were not run. Pytest reported cache permission
warnings and a pre-existing Starlette/httpx deprecation warning.

New regression coverage lives in `tests/unit/test_audit_regressions.py`,
`tests/unit/test_static_server.py`, `tests/e2e/test_audit_browser.py`, and the
extended `tests/integration/sql_migrations_database.mjs`. These cover fetch
allowlists/redirects, auth isolation and failures, row limits, privacy ordering,
worker claims, partial profile updates, exact counts, real static-server
requests, browser injection/session/error states and actual SQL access rules.

## Remaining findings and risks

These are not claimed fixed:

- **P2, source-confirmed:** the repository lacks base migrations for several
  current social/profile/progress/list-review tables and columns. The all-SQL
  test supplies explicit prerequisites; it does not prove fresh provisioning.
  Recover the deployed schema before writing a safe complete baseline.
- **P2, source-confirmed:** some review, membership, presence and inbox list
  queries still rely on default row caps. Catalogue/options and unread counts
  are fixed; these other paths need large-data fixtures and pagination work.
- **P2, source-confirmed:** upload history uses a read/append/write array, and
  novel publishing checks duplicates before insertion. Concurrent requests can
  lose history or race unless the deployed DB has protections not in this repo.
  Inspect deployed constraints and add transactional RPCs; no production race
  test was attempted.
- **P2, source-confirmed:** a process crash can leave a rebuild marked running.
  Conditional claims prevent duplicate workers but do not implement crash
  recovery. Admin cancellation remains the recovery path. Test shutdown/restart
  and define a lease/resume policy before adding automatic retries.
- **Potential security risks:** expensive authenticated scrape/Gemini endpoints
  have no verified distributed abuse limit. Provider controls were not checked.
  Avatar payloads receive base64/size checks, not full image decoding. Review
  those controls before exposing the service widely.
- Cross-tab refresh-token rotation, very large review trees, SMTP recovery,
  provider challenge handling and arbitrary custom-trait migrations need more
  integration coverage. No claims of safety are made for untested interactions.
- Python dependency advisories were not exhaustively checked. Minimum-version
  manifests are not lockfiles. `pip check` verifies compatibility, not security.
- SQL and Worker fixes are not active in production until deployed. Production
  RLS, storage policies, API limits and network behavior remain unverified.

Source references used for design checks: [Supabase signup behavior](https://supabase.com/docs/reference/javascript/v1/auth-signup)
and [Cloudflare asset routing](https://developers.cloudflare.com/workers/static-assets/routing/worker-script/).
No private source code was sent to those services.
