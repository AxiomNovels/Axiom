# Repository guidance

## Project layout

Axiom is a novel discovery and recommendation app with reader profiles, reviews,
reading lists, social features, protagonist profiling, and trait voting.

- `backend/main.py`: FastAPI entry point; registers the `/api` routers.
- `backend/routes/`: HTTP endpoints and request handling.
- `backend/models/`: Pydantic request models and validation.
- `backend/services/`: recommendation, search, profiling, and other business logic.
- `backend/core/`: configuration, Supabase clients, shared authentication, email,
  and notifications.
- `backend/profiler/` and `backend/scraper/`: Gemini profiling and source-specific
  discovery, scraping, staging, and publishing.
- `frontend/public/`: plain HTML, CSS, and browser JavaScript; no framework or
  bundling step. Shared browser behavior lives in `script.js` and `styles.css`.
- `frontend/server.js`: local Node static server and runtime configuration endpoint.
- `frontend/worker.js` and `wrangler.jsonc`: Cloudflare Worker and asset configuration.
- `database/`: Supabase SQL migrations, policies, triggers, and RPC functions.
  `database/users/` contains a separate SQLite/SQLAlchemy implementation; the
  current API uses Supabase through `backend/core/database.py`.
- `tests/`: Python unit/integration tests, Playwright browser tests, and a separate
  Node/PGlite database regression test.

Some documentation and test fixtures describe older profile sets. The application
currently generates and edits protagonist profiles only. Check current code,
particularly `backend/profiler/prompt.py` (`MEASURES`), when working on traits;
do not restore retired philosophy/storytelling tables based on old README text.
Report mismatches in existing tests instead of weakening assertions to hide them.

## Local setup and commands

Run these PowerShell commands from the repository root unless stated otherwise.
Use the existing `backend/.venv` Python environment when available; create it with
`python -m venv backend/.venv` on a fresh clone.

```powershell
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
backend\.venv\Scripts\python.exe -m pip install -r tests\requirements.txt
Copy-Item backend\.env.example backend\.env
```

Only copy the environment example when `backend/.env` does not exist. Configure
`SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY`; privileged operations also need
`SUPABASE_SECRET_KEY`, and profiling needs `GEMINI_API_KEY`. `GEMINI_MODEL` and
`FRONTEND_ORIGIN` are optional settings. The root `requirements.txt` is not the
FastAPI backend's dependency list.

Start the backend from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --port 8000
```

Start the frontend from `frontend/` with `npm.cmd run dev` (Node 18+). It serves
`http://localhost:3000`; verify the backend at `/api/health` and finder metadata
at `/api/search/options` on port 8000. The frontend has no npm runtime dependencies.
`PORT` controls its listening port and `API_BASE` controls its backend URL.

Preview a protagonist profile from `backend/` with
`.\.venv\Scripts\python.exe -m profiler.profile_protagonist NOVEL_ID`.
`--save` writes a profile; `--yes` skips its confirmation. Profiling and scraping
can call external services and publish database changes; use previews when only
inspecting behavior.

## Verification

Run checks appropriate to the changed behavior. No lint or build script is
currently declared in `frontend/package.json`.

```powershell
# Fast Python unit and integration suites (controlled database substitutes).
backend\.venv\Scripts\python.exe tests\run_all.py --fast

# One targeted Python test file; use this configuration for direct pytest runs.
backend\.venv\Scripts\python.exe -m pytest -c tests\pytest.ini tests\unit\test_search_service.py

# Separate isolated database regression suite; not included in run_all.py.
npm.cmd ci --prefix tests
npm.cmd run test:votes --prefix tests

# Install browser support when needed.
backend\.venv\Scripts\python.exe -m playwright install chromium

# Isolated voting UI checks with intercepted API responses.
backend\.venv\Scripts\python.exe -m pytest -c tests\pytest.ini tests\e2e\test_protagonist_voting.py

# Full Python suite, including the real Supabase browser journey.
backend\.venv\Scripts\python.exe tests\run_all.py
```

The full runner requires `tests/.env.test`, copied from its example and configured
for a dedicated Supabase test project. It starts frontend/backend servers on
3100/8100, creates temporary users, and attempts cleanup. Ensure the frontend's
`API_BASE` points to the test backend when running that journey; its ordinary
fallback is port 8000. See `tests/README.md` for setup. Keep unit/integration tests
independent of live Supabase and Gemini by using mocks or controlled substitutes.

## Implementation conventions

- Follow `.editorconfig` and `.gitattributes`: UTF-8, LF, a final newline, and
  spaces. Match nearby code (typically four spaces in Python, two in JavaScript).
- Keep routes focused on HTTP/authentication, Pydantic models on validation, and
  reusable business logic in services. Register new routers in `backend/main.py`.
- Use shared `API_BASE` and `authFetch()` for authenticated browser requests.
  Load `/runtime-config.js` before `/script.js`, then page-specific scripts.
  Both the Node server and Cloudflare Worker serve the runtime configuration;
  keep their behavior consistent when changing it.
- Reuse the shared backend auth dependencies. User-scoped clients must preserve
  Supabase RLS. Auth operations use isolated clients to avoid sharing sessions.
- `SUPABASE_SECRET_KEY` stays on the backend. Service clients bypass RLS, so
  privileged endpoints must enforce authentication and authorization themselves.
  SPECIAL access comes from server-owned `app_metadata.axiom_special`; browser
  storage, usernames, and user-editable metadata never grant access. Preserve
  banned-account checks and privacy/visibility rules.
- For database changes, add or update SQL under `database/` and document migration
  ordering. Preserve grants, RLS, and transactional vote recalculation. Follow
  `database/PROTAGONIST_VOTING.md` for voting/locking behavior, checking trait
  names against current code. New RLS tables need the restrictive banned-account
  policy described in `database/admin_hub.sql` and the README.
- Do not commit secrets, environment files, virtual environments, caches,
  `node_modules/`, or generated scraper output. Keep reusable fixtures non-sensitive.
