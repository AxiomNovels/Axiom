# Stage 1 first-party analytics

## Installation and order

1. Apply the existing `profiles.sql` and `admin_hub.sql` prerequisites, then
   `analytics.sql` in the dedicated Supabase project's SQL editor. Do not rerun
   base migrations against an established database. `analytics.sql` is repeatable.
2. Enable Supabase Cron and schedule `select public.analytics_cleanup()` hourly.
   With pg_cron installed, run once:

   ```sql
   select cron.schedule('axiom-analytics-retention', '17 * * * *',
     'select public.analytics_cleanup()');
   ```

   Verify the job succeeds in Cron history. Raw IPs expire after seven days;
   events/sessions after 90 days. An hourly schedule adds up to one hour of
   cleanup delay. Existing accounts/signups retain their ordinary account lifetime.
3. In backend hosting environment variables, set `ANALYTICS_ENABLED=true` and
   a cryptographically random `ANALYTICS_EDGE_SECRET` (at least 32 random bytes).
   Existing `SUPABASE_SECRET_KEY` is required. Restart the backend.
4. Set the identical `ANALYTICS_EDGE_SECRET` as a **Worker secret** using your
   normal Cloudflare deployment settings; do not put it in `wrangler.jsonc`.
   Set the Worker variable `ANALYTICS_ENABLED=true` and redeploy. Preserve
   `assets.run_worker_first=true`. No Cloudflare Analytics API/token is used.
5. Enable `ANALYTICS_LOG_IPS=true` on the backend only if restricted raw IP
   collection is wanted and retention/access arrangements are ready. It defaults
   to false. The IP log opens separately and its access is recorded in backend logs.
6. Review `/analytics-privacy.html` and applicable privacy/consent requirements
   before enabling live collection. Reader events default to enabled; saved opt-outs and DNT/GPC disable them. This behavior is not a determination that implied consent is appropriate for every visitor or jurisdiction.
7. Visit the site, browse, interact for 30 seconds, and
   check the Analytics tab with a SPECIAL account. Check countries, request types,
   queue health, and Cron. Turn analytics off in the footer preferences and confirm reader events stop.

## Local use

Set `ANALYTICS_ENABLED=true` in `backend/.env`, then restart the backend and run
the frontend normally with `npm.cmd run dev`. The Node frontend automatically
reads the public enabled flag from `/api/analytics/config` on its configured
backend; it never reads or exposes backend secrets. An explicit frontend process
`ANALYTICS_ENABLED=true` or `false` overrides discovery for tests. If the backend
is stopped, analytics stays off until it is available and the page is refreshed.
Local browser events go directly to the backend; country is `XX`
(unknown), and local static requests are not counted. Keep local collection off
when using production credentials to avoid contaminating reports. No credentials
are ever exposed by `/runtime-config.js`.

## Definitions and coverage

- All reports use UTC calendar dates, with an inclusive end date and at most
  90 days. Reports are database aggregates, not limited PostgREST row downloads.
- A visit is a random browser session, renewed after 30 minutes of inactivity.
  Visits started are sessions whose start is in the selection. Engaged sessions
  are sessions with events in the selection; averages use this denominator.
- Page views and active time exclude opt-outs and browser privacy signals, so these metrics do not cover all website users. Signed-in IDs are resolved by the backend, not accepted in payloads.
- A heartbeat credits at most 30 seconds, no more than server-observed elapsed
  session time. A visible page must have interaction within 60 seconds. Multiple
  tabs share the session and server-side row lock, limiting duplicate time.
  This remains an estimate: it cannot prove reading or attention.
- Frontend counts include asset/page requests that reach the Worker, including
  bots; browser cache hits and requests stopped before the Worker are absent.
  Runtime-config/favicon/robots and telemetry endpoints are excluded.
- The enabled Worker proxies ordinary browser API calls to the backend and adds
  signed-trust metadata. The backend counts API requests separately. A proxied
  API call is not counted again as a frontend request. Direct backend callers
  have unknown country. Country is network location, not nationality/residence.
- Backend health checks, analytics collection, and reporting endpoints are
  excluded. Status is collected; request bodies/query strings are not. Route
  templates replace IDs. Country/IP headers are trusted only with the shared secret.
- IP logs contain network addresses only for trusted edge requests when enabled;
  never browser payload addresses or unauthenticated forwarding headers.
- Page paths strip query strings; individual novel interest is Stage 2. Entrances
  are visit entry pages; last pages are observed visit endpoints, not confirmed exits.
- Signups use `auth.users.created_at`, independent of browser events. They are
  unavailable under a country filter because signup country was not recorded.
- Reports include previous equal-period page views, request totals, and active
  time. There is no fabricated history before collection or after retention.

## Operational limits

The backend buffers up to 5,000 events per process, writes batches of up to 100,
and drops records on overflow/write failure. Restarts can lose pending events.
This protects normal website requests; it is not billing/audit-grade accounting.
Queue health is per process, and Worker collection failures are in Worker logs.
Every frontend request adds a background collection call, which has hosting cost.
Use Cloudflare rate-limiting rules for telemetry at scale; the built-in bounded
limiter is per backend process. CORS/origin checks do not make public analytics
unforgeable. Raw requests include bots; no claim of bot-free visitor counts is made.

Only SPECIAL, non-banned accounts can access reporting, exports, and IP logs.
Tables and RPCs revoke ordinary database access and include the restrictive
banned-account policy. Service-role credentials stay on the backend. Account
deletion clears account identifiers via foreign keys. IP logs are not in CSVs.
Daily CSVs contain numeric/date fields, avoiding spreadsheet formula injection.

The offline country map uses Natural Earth v5.1.2 (public domain), simplified
1:110m outlines converted to an equirectangular SVG path dataset. Some small
territories are absent from the outline map; their data remains in the table.
Rebuild it with `scripts/build_analytics_map.py`. Source and license are embedded
in `frontend/public/assets/analytics-world.json`.

Do not expose the backend edge secret in the browser, commit it, or use a
Cloudflare API token in its place. Rotate it in both deployments if compromised.
To disable collection, set the flag false in both deployments; retain cleanup.

## Checks

Run `backend/.venv/Scripts/python.exe -m pytest -c tests/pytest.ini tests/unit/test_analytics.py`.
Run `node tests/integration/analytics_database.mjs` after installing tests dependencies.
Run `node --test tests/integration/analytics_worker.mjs` for Worker trust/proxy checks.
Run the isolated analytics browser tests for dashboard and preference behavior.
