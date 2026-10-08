# Latency optimization report — 2026-10-08

Implemented **4 optimizations across 9 files**: 5 application files, 2 regression
test files, 1 repeatable benchmark, and this report. Investigated and rejected or
deferred **10 additional candidates**, listed below. Baseline revision:
`51c1de20fe060c145d00a7309b6b5c3717ab0a93`.

The strongest expected network improvement is the reader directory's reduction
from 100 to 48 serial badge lookups at its default result limit. Local synthetic
measurements show approximately 49% less search processing time and 21–23% less
recommendation processing time. These percentages describe the measured stages,
not whole production requests. Live Supabase latency, query plans, production
traffic distributions, and hosted browser timings were unavailable.

## Architecture and inspection coverage

The repository inventory covered backend, frontend, SQL, CLI utilities, seed
scripts, configuration, and tests. A structural scan read 163 tracked source and
configuration files: 72 backend, 18 database, 51 frontend, 20 tests, the root seed
script, and Wrangler configuration. Targeted deeper review followed request
handling, auth, search, recommendations, directory/activity, lists/reviews,
profiling/scraping, browser loading, and voting transactions. This was a static
repository review plus isolated execution, not a live production profile.

| Area | Runtime and important paths | Latency findings |
| --- | --- | --- |
| API | FastAPI/Uvicorn; synchronous routes/dependencies; Pydantic validation | Blocking Supabase and scraper work runs in synchronous handlers. Converting signatures to `async def` alone would not improve I/O and could block the event loop. |
| Storage/auth | Supabase/PostgREST clients; isolated auth/user clients; privileged clients with explicit access checks | Repeated serial remote calls dominate several paths. Preserve RLS, banned checks, and current visibility. `database/users` is a separate legacy SQLAlchemy/SQLite implementation, not the API's data path. |
| Search | Fetch catalogue with traits/ratings, Python keyword ranking/filtering/sorting | Duplicate relevance work on every nonempty relevance search; all-catalogue transfer remains. |
| Recommendations | Fetch source, page through candidates in batches of 500, score traits/tags, return six cards | Cards/shared-tag display data were created for every candidate and discarded for almost all. |
| Directory/social | Profiles, presence, per-user auth metadata; activity and review hydration | Directory enriched candidates before truncation. Other hydration already uses several batched lookups; some work remains serial. |
| Voting | PostgreSQL RPCs, triggers, global advisory transaction lock | Serialization may limit concurrent voting; changing the lock requires cross-novel transaction/deadlock testing. |
| Scraping/profiling | Requests/httpx/curl_cffi, BeautifulSoup/selectolax, staged publishing, Gemini identification then scoring | External fetches, challenges, rate limits, and model calls dominate. Discovery has deliberate pacing; preview tokens already avoid regenerating profiles on confirmation. |
| Browser | Static HTML/CSS/JS; shared `script.js`, per-page scripts, `authFetch` refresh | Independent novel subpanels already start without awaiting one another. Profile form/header duplicated a read, and avatar saving triggered an unnecessary reread. |
| Hosting/startup | Dependency-free Node static server locally; Cloudflare assets/Worker in production | Local static reads do not establish a production bottleneck. No bundling/build stage. Profiler service defers some imports, although admin imports also load profiling dependencies. |
| Tests | Controlled Python unit/integration, intercepted Playwright, separate PGlite voting suite | No dedicated latency benchmark/tracing suite found. Added deterministic offline comparison using the original Git source. |

## Implemented optimizations

### 1. Keep the relevance order already computed

- **Location:** `backend/routes/search.py::search_novels`.
- **Problem/frequency:** Every nonempty search with `sort=relevance` ranked the
  catalogue, filtered it, then ranked all surviving novels again. This repeated
  regex tokenization, string/list allocation, scoring, and sorting.
- **Change:** Return the filtered list directly for this case. Filtering is
  order-preserving. Empty queries, title ordering, unknown-sort fallback,
  validation, selected fields, ratings, and filters retain their existing paths.
- **Why it helps:** Removes a second CPU pass over matches without caching or
  changing search semantics. Benefit scales with the number of surviving matches.
- **Evidence:** Four new sort/filter/work-count cases, existing search/API tests,
  and 60 before/after differential combinations passed. cProfile on 1,000 matching
  rows showed `rank_novels` calls 2 → 1, relevance calls 2,000 → 1,000, and regex
  `findall` calls 12,000 → 6,000.
- **Measured impact:** 1,000-row processing median 179.138 → 91.277 ms (49.0%);
  10,000-row scaling case 1,872.552 → 943.194 ms (49.6%).
- **Confidence:** High.
- **Tradeoffs:** No cache memory or invalidation burden. No meaningful gain for
  empty queries or queries with no surviving results; database transfer remains.

### 2. Fetch reader badges after selecting directory results

- **Location:** `backend/routes/users.py::list_public_users`.
- **Problem/frequency:** The default last-online directory fetches up to 100
  candidate profiles and serially calls Auth for each badge, then returns 48.
  Up to 52 network calls contributed nothing to the response on every such load.
- **Change:** Keep presence, sorting, and truncation unchanged; call the existing
  `_is_special_account` helper only for returned users.
- **Why it helps:** Eliminates discarded network work and associated JSON
  parsing. Does not increase concurrency or weaken metadata checks.
- **Evidence:** Tests verify both directory sort modes, returned IDs and badges,
  hidden presence, lookup counts, banned metadata, and Auth failure fallback.
  Benchmark confirms identical output and 100 → 48 Auth calls.
- **Measured impact:** With an explicitly simulated 2 ms sleep per Auth call,
  directory median 250.533 → 120.796 ms (51.8%). Windows sleep/scheduling overhead
  is included. This is a controlled simulation, **not a measured Supabase gain**.
- **Confidence:** High for removing work; actual production milliseconds unknown.
- **Tradeoffs:** Still up to 48 serial badge reads. When all candidates are
  returned (or alphabetical query already limits rows), there is no call saving.
  Badge metadata is read slightly later in the request, still fresh and uncached.

### 3. Build recommendation cards only for selected results

- **Location:** `backend/services/recommendation_service.py::recommend_novels`.
- **Problem/frequency:** Every similar-novels request constructed card dictionaries
  and normalized/sorted shared display tags for the entire candidate catalogue,
  usually returning only six. CPU/allocation work grew with discarded candidates.
- **Change:** Rank references to original rows using the identical score, title,
  and ID keys; build cards and display tags after slicing to the requested limit.
- **Why it helps:** Card creation becomes proportional to returned results.
  Scoring still examines every candidate and uses the same trait/tag weights.
- **Evidence:** New tests cover current traits, both profile embed shapes, ties,
  normalized shared tags, duplicate/source exclusion, missing title, output
  fields, unmodified inputs, and zero/negative/large limits. Fifty differential
  comparisons against the baseline and benchmark output comparisons passed.
- **Measured impact:** At 1,000 rows, 9.185 → 7.119 ms (22.5%), peak traced
  allocation 652,046 → 391,686 bytes. At 10,000 rows, 125.876 → 99.130 ms (21.2%),
  peak 6,716,582 → 4,109,542 bytes (38.8% less).
- **Confidence:** High.
- **Tradeoffs:** Full-catalogue fetch and full sort remain; no new algorithm,
  shared cache, API change, or retained cross-request state. Benefit shrinks when
  callers request most candidates.

### 4. Reuse profile responses for the browser header avatar

- **Location:** `frontend/public/script.js::updateAccountNav` and
  `frontend/public/profile.js::{loadProfile,applyAvatarEdit}`.
- **Problem/frequency:** Opening the profile page fetched `/api/profile` separately
  for the form and header. Saving an avatar fetched the profile again even though
  the mutation response already contained the persisted avatar URL.
- **Change:** The profile form's successful load also updates the header; initial
  navigation skips its redundant read on that form page. Successful avatar saves
  use the server-returned URL directly. Other pages retain their header fetch.
- **Why it helps:** One fewer authenticated read per profile-page load and one
  fewer after each avatar save, including backend auth and profile query work.
  The post-save avatar can update without another API round trip.
- **Evidence:** Three intercepted browser tests pass in installed Edge: form and
  header load with one GET; avatar save updates the header with no extra GET;
  other pages still fetch the avatar; profile failure retains the letter fallback.
  Both modified scripts pass `node --check`.
- **Measured impact:** Current browser request counts are verified. Baseline code
  issues two initial GETs versus one now, and one post-save GET versus zero now.
  No before/after browser wall-clock latency was measured.
- **Confidence:** High for request elimination; perceived latency benefit inferred.
- **Tradeoffs:** Header loading on the profile page now relies on the page's
  existing successful profile read. No persistent client cache, stale-data window,
  new auth flow, or changes to upload/error handling.

## Measurement method and reproduction

`tests/performance/benchmark_latency.py` loads baseline Python source with
`git show` and compares it with the working tree, using dummy service settings
and controlled database substitutes. No network or database writes occur.

```powershell
backend\.venv\Scripts\python.exe tests/performance/benchmark_latency.py --baseline 51c1de20fe060c145d00a7309b6b5c3717ab0a93
```

Environment: Windows, Python 3.14.3, nine interleaved timing samples per variant;
medians reported. Exact output equality is checked before timing. `tracemalloc`
is measured separately, with inputs already allocated, so peaks describe
additional Python allocations, not whole-process memory. Fixture seed is 42;
novels have ten current traits, four tags, two ratings, and a 450-word synopsis.
Search's measured query matches every title. This deliberately exposes duplicate
ranking; it is not a representative production query distribution. The 10,000-row
search case is a CPU scaling experiment, not a claim that the current unpaginated
Supabase search fetch returns that many rows.

| Measured stage | Before median | After median | Reduction |
| --- | ---: | ---: | ---: |
| Search, 1,000 matching rows | 179.138 ms | 91.277 ms | 49.0% |
| Search, 10,000 matching rows | 1,872.552 ms | 943.194 ms | 49.6% |
| Recommendations, 1,000 candidates | 9.185 ms | 7.119 ms | 22.5% |
| Recommendations, 10,000 candidates | 125.876 ms | 99.130 ms | 21.2% |
| Directory, simulated Auth delay | 250.533 ms | 120.796 ms | 51.8% |

An additional one-off cProfile run confirmed the search call counts above, and
110 differential comparisons exercised search and recommendation outputs. Those
checks used the same benchmark fixture and original revision.

## Ten candidates investigated but not implemented

| Location/candidate | Potential benefit | Reason deferred or rejected | Evidence needed |
| --- | --- | --- | --- |
| `routes/search.py`, database search/RPC/indexes | Avoid transferring/tokenizing the full catalogue; improve large-catalogue latency | Python's normalization, prefix weights, stable ordering, and filters would need a carefully equivalent database implementation. Pagination also changes the current response contract. | Representative catalogue, `EXPLAIN (ANALYZE, BUFFERS)`, query distribution, semantic parity tests, separately agreed pagination API if needed. |
| Search/options/recommendation catalogue caches | Avoid repeated remote reads and scoring | Uploads, reviews, and transactional votes affect these results; TTL caching silently introduces stale behavior. | Acceptable staleness contract or reliable cross-worker invalidation, observed hit rate, memory and p95 data. |
| `core/database.py`, sharing user/service clients | Amortize initialization, TLS setup, and connections | Auth sessions/authorization headers are mutable; sharing user clients risks identity leakage. Service pooling also needs lifecycle and deployed-library verification. | Client-construction/handshake traces plus concurrency/isolation tests and explicit lifecycle design. |
| Remaining directory/admin Auth lookups | Overlap up to 48/25 serial calls | Per-request thread pools multiply load under concurrency; provider limits and client guarantees are unmeasured. The implemented pruning is simpler and reduces load. | Auth RTT and rate-limit data, bounded process-wide concurrency/load tests, supported client concurrency semantics. |
| `users.py` presence helpers | Replace two presence reads with one | Existing helpers fail independently; consolidating also requires careful timestamp handling and changes failure behavior. Smaller benefit than discarded badge calls. | Failure-semantics decision and timestamp/boundary tests, request traces showing material remaining cost. |
| List previews and review/profile hydration | Smaller batched reads or merged profile lookups | Limiting previews before resolving missing novels can change fallback covers. Combining author queries can hit response caps and alter error behavior; existing code deliberately avoids unreliable embedded profiles. | Large-list/discussion fixtures, missing-row cases, explicit pagination/cap handling, query plans and latency traces. |
| Voting SQL global advisory lock | Allow unrelated novel votes concurrently | Global lock coordinates bulk deletes, baselines, locking, and recalculation. Per-novel locks need consistent ordering across cross-novel transactions; removing it risks deadlocks or incorrect totals. | Real PostgreSQL concurrent transaction/deadlock workload and lock-wait profiles. |
| Scraper/profiler parallel requests or fewer retries/delays | Shorter import/profile wall time | Pacing protects source availability; identification precedes trait generation; re-scraping confirmation validates fresh input. Removing these changes reliability/behavior. | Provider-safe concurrency limits, source traces, representative fixtures, and failure/rate-limit experiments. |
| `core/email.py` background welcome email | Remove SMTP latency from signup | Moving delivery to an in-process task changes durability during shutdown/failure. A durable outbox exceeds this focused pass. | Signup/SMTP timing evidence and an agreed delivery/retry guarantee. |
| `frontend/server.js`, caching/compression | Reduce local disk reads/asset transfer | Production serves assets through Cloudflare; local caching risks hiding edits and does not establish a hosted bottleneck. No hot disk/serialization evidence supports a change. | Hosted asset waterfall/cache metrics and local I/O profiling if developer startup is the actual problem. |

These are potential benefits inferred from code, not demonstrated speedups. No
low-confidence optimization was implemented. No database migration, lock change,
new dependency, cache, or HTTP API compatibility change was introduced.

## Verification and existing failures

| Check | Result |
| --- | --- |
| Original `tests/run_all.py --fast` before edits | Collection blocked: `test_auth_model.py` imports removed `AuthRequest`. Also reported inaccessible pytest cache warnings. |
| Baseline unit/integration run excluding only that collection-blocking file | **189 passed, 9 failed**. |
| Search/API/admin targeted tests immediately after first edits | **46 passed**. |
| New latency regression tests | **8 passed**. |
| Recommendation targeted tests after edit | **9 passed, same 2 pre-existing failures**. |
| Final unit/integration run with identical exclusion | **197 passed, same 9 failed**; no new failures. |
| New browser tests using default Playwright browser | Setup failed: bundled Chromium executable not installed. |
| Same browser tests with `--browser-channel msedge` | **3 passed**, 42.40 s suite duration (not a latency benchmark). |
| JavaScript syntax checks | Both modified scripts passed. |
| `git diff --check` | Passed; modified files follow LF formatting. |
| Offline benchmark | All five cases passed baseline/current output equality; timings above. |
| Additional differential checks | **110 passed**. |

Final suite command:

```powershell
backend\.venv\Scripts\python.exe -m pytest -c tests/pytest.ini tests/unit tests/integration --ignore=tests/unit/test_auth_model.py -p no:cacheprovider -q --tb=short
backend\.venv\Scripts\python.exe -m pytest -c tests/pytest.ini tests/e2e/test_profile_latency.py --browser-channel msedge -p no:cacheprovider -q
node --check frontend/public/script.js
node --check frontend/public/profile.js
```

The nine baseline failures were preserved and not weakened:

- `test_profile_retirement.py::test_only_protagonist_is_generated_and_editable`
  expects six measures; current code defines ten.
- Five cases in `test_protagonist_votes.py` use the retired `selflessness` trait:
  the three parameterized vote cases, missing-baseline case, and withdrawal case.
- `test_recommendation_service.py::test_tags_and_protagonist_have_equal_weight`
  uses retired `impulsivity`, so it does not exercise a current trait.
- `test_royalroad_discovery.py::test_source_refusal_stops_scraping_instead_of_retrying_pool[503]`
  expects stopping where current code continues on a 503.
- `test_recommendations.py::test_similar_endpoint_searches_beyond_first_page`
  expects genre-based ranking, while current recommendations score tags/traits.

Several other passing legacy tests also use retired traits and therefore offer
weaker coverage than their names imply. The new regression test uses current
`intellectual_drive`; no retired fields were restored.

The live Supabase browser journey, external scraping/Gemini calls, SMTP, hosted
Cloudflare behavior, and production concurrent load were not run. The separate
PGlite suite was not run: no SQL changed and its local dependency was absent.
Existing voting browser fixtures also reference retired traits; this pass tested
the changed profile UI with its own isolated fixtures. FastAPI TestClient reports
an existing httpx deprecation warning.

## Second pass and change record

Reviewed the complete application diff after measurements, then reran the wider
controlled suite. Checked sorting fallback, filtering order, current trait
weights, shared-tag spelling, input mutation, source/duplicate exclusion,
non-default limits, private presence, banned badges, Auth failures, avatar-save
response shape, shared-script loading order, and header fallback. No new
correctness failure appeared. No additional cache or concurrency mechanism was
needed; remaining performance questions are listed above.

| File | Change |
| --- | --- |
| `backend/routes/search.py` | Avoid duplicate relevance ranking. |
| `backend/routes/users.py` | Defer badge reads until directory selection. |
| `backend/services/recommendation_service.py` | Defer display-card construction. |
| `frontend/public/script.js` | Let the profile form supply its header avatar. |
| `frontend/public/profile.js` | Apply loaded/saved avatar data to the header. |
| `tests/unit/test_latency_paths.py` | Eight behavior/work-count regressions. |
| `tests/e2e/test_profile_latency.py` | Three intercepted browser regressions. |
| `tests/performance/benchmark_latency.py` | Reproducible offline baseline comparison. |
| `LATENCY_REPORT.md` | Architecture, decisions, measurements, limitations, and checks. |
