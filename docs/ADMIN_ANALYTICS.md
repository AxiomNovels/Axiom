# Admin website analytics

The Analytics tab uses **Cloudflare Web Analytics / Real User Monitoring**,
`rumPageloadEventsAdaptiveGroups`, scoped to the configured hostnames with
`bot: 0` (Exclude Bots). HTTP zone requests and unique IP counts are not used.

## What the numbers mean

- Visits: direct/external referral arrivals, Cloudflare's `sum.visits`. A person
  may make multiple visits; this is not a count of unique humans or accounts.
- Page views: browser page-load events, Cloudflare's `count`.
- Countries: the same bot-filtered visits and page views grouped by
  `countryName`, inferred by Cloudflare from the browser connection. VPNs can
  change the reported country. Unknown locations remain in the table.
- All date boundaries are UTC. Today's data is partial; today and yesterday
  are provisional. Counts can be delayed and the adaptive dataset may be sampled.
  Ad blockers, disabled JavaScript, and people leaving before the beacon loads
  can prevent measurement. Bot filtering is an estimate, not proof of humanity.
- Range totals sum the daily counts. Empty analytics stays empty; there is no
  fallback to network requests. Country totals use the identical filters/range.

## Enable collection

1. In Cloudflare, open **Web Analytics / Real User Monitoring**, add/select
   `axiomnovels.com`, and enable the JavaScript beacon. Prefer Cloudflare's
   automatic injection when available. Verify the deployed page includes
   `static.cloudflareinsights.com/beacon.min.js` and sends a beacon after loading.
2. If automatic injection is unavailable, copy the **public beacon token** from
   the site's JavaScript snippet. Set `CLOUDFLARE_WEB_ANALYTICS_TOKEN` in the
   **frontend Worker's runtime variables** (or the Node server's environment),
   and redeploy. Shared browser code then loads one beacon on the production
   hostnames. Do not enable manual and automatic injection simultaneously.
   The beacon token is a public site identifier, NOT the privileged API token.
3. Backend configuration (`backend/.env` locally, backend hosting environment
   in production):

   ```dotenv
   CLOUDFLARE_API_TOKEN=<API token with Account / Account Analytics / Read>
   CLOUDFLARE_ACCOUNT_ID=<the account containing this Web Analytics site>
   CLOUDFLARE_ANALYTICS_HOSTS=axiomnovels.com,www.axiomnovels.com
   CLOUDFLARE_ANALYTICS_TIMEZONE=UTC
   ```

   Limit token permissions to the relevant account. Alternatively the existing
   `CLOUDFLARE_ZONE_ID` can resolve the account ID once per backend process; this
   also requires Zone / Zone / Read on that zone. No write permissions are needed.
   Account IDs, API tokens and zone IDs are never returned to the browser.
4. Restart/deploy the backend. Visit the public site, allow processing time,
   then open Admin Hub > Analytics. Collection starts when the beacon is enabled;
   prior HTTP requests cannot be converted into past browser visits.

The backend caches successful results for 60 seconds. Supported UI ranges are
7, 30 and 90 days; actual retention and query entitlements depend on the account.
An unsupported range or permission failure produces an error, not zero traffic.

## Troubleshoot analytics access

The API returns 503 when a backend Cloudflare credential/configuration prevents
analytics from loading. This does not mean the admin's Axiom session is invalid.
Cloudflare can return HTTP 200 with a GraphQL authorization error; successful
token verification alone does not prove permission to read Web Analytics rows.

- For an invalid/expired/revoked token, update `CLOUDFLARE_API_TOKEN` in the
  environment of the backend being used, then restart/redeploy that backend.
  Process environment variables take precedence over `backend/.env`.
- For an analytics-data denial, check the exact token used by that backend,
  Account / Account Analytics / Read, Account Resources, and whether its owner
  can access the site's Web Analytics in the dashboard. An enabled dataset or
  successful account lookup is not a successful analytics-data authorization test.
- For a zone-lookup denial, set `CLOUDFLARE_ACCOUNT_ID` directly, or add
  Zone / Zone / Read for the configured zone. Adding Account Analytics permission
  does not grant zone lookup access.

Never paste API token values into a support message or put them in frontend
configuration. Do not replace browser visits with HTTP request counts when
analytics access fails.

## Map

`frontend/public/assets/analytics-world.json` contains public-domain Natural
Earth 5.1.2 country outlines, continents, and label points. All use the same
equirectangular projection. Circle **area** scales with visits. Large circles
render underneath small circles. Hover, keyboard focus, and tap reveal values;
all locations also appear in the table. Simplified boundaries are for analytics,
not a statement about sovereignty.

Regenerate the JSON using `frontend/generate_analytics_map.py` (prints to stdout).
Source: https://github.com/nvkelso/natural-earth-vector/tree/v5.1.2/geojson
License: https://www.naturalearthdata.com/about/terms-of-use/ (public domain).

Cloudflare references:

- https://developers.cloudflare.com/web-analytics/data-metrics/dimensions/
- https://developers.cloudflare.com/web-analytics/data-metrics/high-level-metrics/
- https://developers.cloudflare.com/analytics/graphql-api/features/discovery/settings/
