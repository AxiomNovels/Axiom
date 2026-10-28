# Protagonist quiz

Standalone campaign entry: `/quiz/index.html`. `/quiz/` is the canonical URL;
the local server also accepts `/quiz`. No signup, frontend dependencies, build
step, database writes, or new external services are required.

## Repository audit

| Area | Existing implementation and quiz integration |
| --- | --- |
| Stack and structure | `frontend/public/` contains plain HTML, CSS, and browser JavaScript. `frontend/server.js` is a dependency-free Node HTTP server. `backend/main.py` registers FastAPI routers; request validation, business logic, and shared clients live in `backend/models/`, `backend/services/`, and `backend/core/`. The active API uses Supabase, with SQL in `database/`. Profiling and scraping live in `backend/profiler/` and `backend/scraper/`. |
| Routing | Each HTML file is an independent page; there is no client-side router. Novel links use `/novel.html?id=ID`. Node serves files and runtime config. The quiz adds explicit Node directory aliases. Root `wrangler.jsonc` points Cloudflare assets at `frontend/public`, uses `auto-trailing-slash` HTML handling, and routes requests through `frontend/worker.js`. The Worker asset handler resolves the quiz directory index. |
| Deployment | The existing deployment is a Cloudflare Worker plus static assets. `wrangler.jsonc` currently points `API_BASE` at an `onrender.com` backend. This change stays in that deployment; it does not create a separately hosted Site. No production deployment was performed. Deploy the backend analytics path update with the ordinary backend release and the frontend through the existing Worker deployment. |
| Layout | Headers are repeated HTML, with shared CSS and authentication behavior in `script.js`; there is no server template engine. `script.js` injects the shared footer and loads `analytics.js`. The quiz uses a compact branded campaign header with visible navigation, the existing shared footer, and a new quiz footer link across the app. |
| Typography | Shared `styles.css` uses an Inter/system sans-serif stack and Georgia/Times for literary headings. No font download is needed. The quiz retains these stacks. |
| Palette | Shared tokens include `--background: #09030d`, `--background-soft: #16091c`, `--ink: #f7f0f5`, `--muted: #bba9bd`, `--accent: #9b4dcc`, `--passion: #d14a55`, `--dusk: #6e92c4`, `--verdant: #5f9b82`, `--gold: #c9a66b`, `--line`, and `--focus: #c99ae5`. The quiz uses the same plum, lavender, and gold vocabulary with a quieter dark background. |
| Logos and assets | Existing PNG logos are `/assets/axiom-mark.png`, `/assets/axiom-wordmark.png`, and `/assets/axiom-logo.png`. Novel covers come from catalog `cover_image_url` values. Original, local SVG illustrations live in `quiz/art/`: one gateway/book hero and eight archetype emblems. Failed covers receive a local placeholder. |
| Analytics and consent | Runtime config controls existing first-party tracking. `analytics.js` defaults to enabled when configured, respects `axiomAnalyticsConsent=declined`, Do Not Track, and Global Privacy Control, and exposes preferences in the shared footer. Signed-in visits can be account-linked. Worker request counts are collected separately. Quiz page aliases normalize to `/quiz/` in browser tracking and backend sanitization. No new analytics events are added; answers, trait scores, and archetypes are never transmitted or stored. |
| Metadata | Existing public pages use descriptive titles, descriptions, production canonicals, Open Graph tags, and a sitemap. Internal pages use noindex response headers. The quiz has its own metadata and canonical, uses the existing raster logo for social previews, and appears in both dynamic sitemap implementations and the static fallback. |
| Accessibility and mobile | Existing pages use labeled navigation, visible focus styling, responsive header wrapping, and shared footer stacking. The quiz uses a skip link, native fieldset/legend/radios, large labeled targets, native keyboard radio navigation, explicit Next, a labeled progress element, focus transfer, live loading/error status, native disclosure controls, and reduced-motion rules. Its small navigation stays visible instead of introducing a menu. Layouts were checked at 320px, 390px, and desktop widths. |

## Files and flow

- `index.html`: title, questions, and results screens; metadata and shared scripts.
- `content.js`: 18 scenario questions, four answers each; two per trait plus two
  each for independence and unconventional thinking.
- `config.js`: seven trait definitions, archetype descriptions, weights,
  eligibility thresholds, near-tie threshold, and fixed tie priority.
- `engine.js`: pure normalization, archetype selection, and catalog distance
  matching; loadable in both the browser and Node tests.
- `ui.js`: in-memory answer state, navigation, result rendering, and public
  catalog loading. Returning to a question preserves its answer; retaking clears
  answers; reloading the page starts fresh.
- `quiz.css` and `art/`: responsive interface and original vector artwork.

Scripts load in this order: `/runtime-config.js`, `/script.js`, quiz configuration,
content, engine, and interface. Public matching requests use the shared `API_BASE`.
There are no authenticated quiz operations.

## Scoring rules

The quiz measures exactly Intelligence, Charisma, Courage, Moral Integrity,
Kinship & Friendship, Romantic Attachment, and Arrogance & Conceit. Romantic
Attachment includes the participant's own romantic or sexual attraction and
investment, as specified in the campaign brief. There is no separate desire trait.

For each dimension, sum the selected points, then normalize using the minimum
and maximum attainable sums across that dimension's questions:

`score = 100 × (selected sum − possible minimum) / (possible maximum − possible minimum)`.

Current question scores are 0, 33, 67, and 100. Questions measure their assigned
dimension independently; low romance never reduces friendship. All 18 questions
are mandatory. Calculations retain precision; the interface rounds trait scores
to whole percentages and similarity to one decimal place.

Archetype scores are weighted sums of normalized inputs:

| Archetype | Weights | Eligibility |
| --- | --- | --- |
| Mastermind | .70 intelligence + .20 max(charisma, arrogance) + .10 courage | All participants |
| Natural Leader | .65 charisma + .20 kinship + .10 courage + .05 integrity | All participants |
| Idealist | .70 integrity + .20 courage + .10 kinship | All participants |
| Guardian | .70 kinship + .15 courage + .10 integrity + .05 romance | All participants |
| Romantic | .80 romance + .10 courage + .10 kinship | All participants |
| Conqueror | .65 arrogance + .20 courage + .10 intelligence + .05 charisma | Arrogance ≥60 and courage ≥50 |
| Lone Wolf | .60 independence + .15 (100 − kinship) + .10 intelligence + .15 courage | Independence ≥65 |
| Wildcard | .65 unconventionality + .15 intelligence + .10 courage + .10 trait range | Unconventionality ≥65 |

Trait range is the highest minus lowest of the seven scores. The two decision
patterns are measured directly and used only for archetype assignment; they are
not presented as extra character traits. Low friendship alone cannot qualify
someone as a Lone Wolf. Balanced or varied scores alone cannot qualify a Wildcard.
High arrogance without courage cannot qualify a Conqueror.

The highest eligible score wins. The next eligible result appears as a secondary
influence if it is within three points, inclusive. Exact ties use configuration
array order (the table order); a 1e-9 tolerance ignores floating point noise.
Results represent the closest creative archetype, not a clinical assessment.
Weights and the near-tie cutoff remain campaign parameters to calibrate with real
audience feedback; representative synthetic patterns are tested, not a scientific
validation sample. “About 3 minutes” is the requested placeholder estimate.

## Matching real protagonists

On results, the interface requests `/api/search` and
`/api/search/protagonist-definition`. The existing search route fetches the full
public catalog using `all_rows`, including embedded `protagonist_profiles`;
it is not restricted to the first ten rows. Public Supabase RLS remains in force.

Only matching keys from the seven configured quiz traits and active catalog
definition are compared. Every candidate uses the same dimensions. Missing
dimensions are named in the UI; missing or invalid candidate scores are excluded,
never replaced with zero or a midpoint. If no dimensions overlap, no matches are
shown. With the intended active seven-trait definition, all seven are compared.

For n compared traits on the 0–100 scale:

`D = sqrt(sum((participant[i] − protagonist[i])²) / n)`

`Similarity = 100 − D`

This is Euclidean distance divided by sqrt(n), so distance and similarity both
stay within 0–100. Sort by ascending unrounded distance, then ascending novel ID
for deterministic ties. Return at most ten distinct novels; show fewer if fewer
valid profiles exist. If an embed contains multiple profiles, the closest is used.
Strongest overlap is the trait with the smallest absolute gap, breaking ties by
the participant's higher score and then configured trait order. Low-score overlap
is valid too. Each card contains rank, similarity, cover/fallback, novel title,
protagonist name, strongest overlap trait name, and its Axiom novel link.

Loading has a 20-second timeout and retry. Failures never hide the quiz result.
Restarting or reviewing cancels pending matching, preventing stale responses from
overwriting a later result. Catalog text is rendered with `textContent`; cover
URLs accept only HTTP(S).

### Existing source mismatch

The campaign follows the user's confirmed seven-trait brief. The checked-in
`backend/profiler/default_definition.json` still contains `erotic_desire` and lacks
`courage`; `profiler/prompt.py` imports that seed for compatibility. Some older
fixtures (including `tests/e2e/test_protagonist_voting.py`) also retain the old set.
The static `protagonist-profile-info.html` fallback omits Courage. Current backend
operations read the active database definition through `load_definition()`. The
guide is currently an admin-only static preview, gated by `admin-preview.js`.
Those stale
defaults/fixtures were not rewritten or used as quiz requirements. No existing
assertion was weakened and no database trait or schema change was made. Live
database contents were not inspected as part of this implementation.

## Verification

From the repository root:

```powershell
node --test tests/unit/quiz_engine.test.cjs
backend\.venv\Scripts\python.exe -m pytest -c tests/pytest.ini tests/e2e/test_quiz.py
backend\.venv\Scripts\python.exe -m pytest -c tests/pytest.ini tests/unit/test_static_server.py tests/unit/test_seo.py tests/unit/test_analytics.py
node --test tests/integration/analytics_worker.mjs
```

Browser tests use intercepted API fixtures, exercise complete journeys and all
seven displayed traits, desktop/mobile layouts, keyboard controls, answer
revision, restart, valid/broken covers, untrusted title text, retries, empty
matches, and analytics opt-out. Local screenshots are generated under ignored
`test-results/`. Scoring tests cover all eight archetypes, endpoints, exact and
near ties, mandatory answers, invalid profiles, missing dimensions, deduplication,
and ranking before taking the top ten. No live Supabase or Gemini calls are made.

For local use, run `npm.cmd run dev` from `frontend/`, then open
`http://localhost:3000/quiz/index.html`. The quiz itself works without the backend;
real matches need the normal backend and configured public Supabase access. The
quiz's `data-backend-optional` marker bypasses the shared full-page backend wake
overlay so a sleeping catalog never prevents starting or completing the quiz.
