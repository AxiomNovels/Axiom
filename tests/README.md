# Axiom test suite

The suite is organized by scope:

- `unit/`: fast tests of isolated business logic.
- `integration/`: API tests with controlled database substitutes.
- `e2e/`: real-browser tests against the frontend, backend, and a dedicated Supabase test project.
- `fixtures/`: reusable, non-sensitive test data.

## First-time setup

From the repository root:

```powershell
backend\.venv\Scripts\python.exe -m pip install -r tests\requirements.txt
backend\.venv\Scripts\python.exe -m playwright install chromium
Copy-Item tests\.env.test.example tests\.env.test
```

Fill in `tests/.env.test` using credentials from a dedicated Supabase test project. The real file is ignored by Git; the empty example is committed.

## Run tests

Run fast unit and integration tests:

```powershell
backend\.venv\Scripts\python.exe tests\run_all.py --fast
```

Run everything, including the browser journey and temporary-user cleanup:

```powershell
backend\.venv\Scripts\python.exe tests\run_all.py
```

The full run starts isolated Axiom servers on ports 3100 and 8100, then stops them. Test-user deletion is attempted in cleanup even if the browser test fails.

The dynamic protagonist definition regression suite uses an isolated PGlite database:

```powershell
npm.cmd run test:definitions --prefix tests
npm.cmd run test:trait-migrations --prefix tests
npm.cmd run test:sql --prefix tests
```

It covers migration from the uploaded mixed legacy/current column layout,
transactional column changes and cleanup, unchanged defaults/votes, locked
profiles, stale revisions, rollback on a dependent view, and RPC permissions.
`tests/unit/test_protagonist_definition.py` covers the API, prompt/schema snapshots,
preview token invalidation, dynamic search and recommendations, and rebuild eligibility.
`tests/e2e/test_protagonist_voting.py` also exercises the Admin Hub definition editor,
manual score editing, and dynamic Finder/guide rendering with intercepted APIs.
The trait-migration suite covers legacy scores/votes/locks moving to the seven
defaults, subsequent Admin Hub edits, and rejection of the legacy reset after
dynamic setup without changing data or restoring unversioned RPCs.
It also installs over historical helper parameter names (`p_scores`, `scores`,
`p_rows`, `p_row`, `profile`, and unnamed parameters), preserving dependencies.
The all-SQL suite executes every `database/*.sql` file in dependency order with
isolated Supabase auth/role substitutes and the actual pgcrypto extension. It
checks repeatable migrations, RPC argument names, review/reply constraints,
reading-list triggers, Admin Hub privileges, RLS, and banned-account restrictions.

## First-party analytics

```powershell
backend\.venv\Scripts\python.exe -m pytest -c tests\pytest.ini tests\unit\test_analytics.py
node tests/integration/analytics_database.mjs
node --test tests/integration/analytics_worker.mjs
backend\.venv\Scripts\python.exe -m pytest -c tests\pytest.ini tests\e2e\test_analytics.py
```

These checks use controlled API/database substitutes and require no Cloudflare
account or live Supabase project. They cover trust headers, event validation,
report authorization, body/rate limits, SQL aggregation, concurrent-time caps,
deduplication, retention, Worker proxying, consent, maps, exports, and mobile layout.
Browser tests save desktop/mobile dashboard previews under `test-results/`.
See `database/ANALYTICS.md` for production setup and metric definitions.
