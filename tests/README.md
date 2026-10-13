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
