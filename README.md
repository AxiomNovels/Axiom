# Philosophy Book Recommender

A hybrid recommendation system that recommends philosophical fiction based on users' protagonist, philosophical, and storytelling interests.

## Features

* Content-based filtering
* Semantic embeddings
* Philosophy ontology
* Collaborative filtering
* Explainable recommendations

## Local frontend

The basic login page lives in `frontend/`.

```bash
cd frontend
npm.cmd run dev
```

Then open http://localhost:3000.

## Local backend

The backend lives in `backend/`.

```bash
cd backend
copy .env.example .env
uvicorn main:app --port 8000
```

On first setup, replace the placeholder Supabase values in `backend/.env`.
Verify the backend with `http://localhost:8000/api/health`, then verify finder
metadata with `http://localhost:8000/api/search/options`.

## WebNovel upload access

WebNovel may serve Cloudflare's "Just a moment..." verification page instead of
book HTML. This depends on the request's network fingerprint and outbound IP,
so a URL can work on one machine and be refused on another. It is not evidence
that the URL is invalid or that Supabase is misconfigured.

Install the backend dependencies on each machine and in the backend deployment:

```powershell
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

The scraper preserves successful plain requests and retries a 403 or detected
challenge once using `curl_cffi` with consistent Chrome TLS/HTTP settings.
Challenge HTML, including HTTP 200 challenges, is rejected as a source-access
failure (502), rather than parsed or reported as an invalid link. HTTP 404 remains
an invalid-link response (422). Neither transport solves interactive challenges
or guarantees access from an IP that WebNovel blocks.

If a deployment remains blocked, set `WEBNOVEL_PROXY_URL` in `backend/.env` or
the backend hosting environment to an outbound proxy you control and are
authorized to use (format `http://username:password@proxy-host:port`). When set,
WebNovel book-page requests use Chrome transport through that proxy directly.
This setting is optional and stays on the backend; never commit its credentials.
Restart the backend after changing it. Browser/proxy requests retain TLS
certificate verification.

From `backend/`, check the actual scraper with:

```powershell
.\.venv\Scripts\python.exe -m scraper.diagnose_scrape "WebNovel" "https://www.webnovel.com/book/shadow-slave_22196546206090805"
```

The raw diagnostic is a plain-request baseline and can still show 403 when the
real scrape succeeds through the fallback. It reports proxy configuration
without printing credentials. Deploy the updated backend and its requirements
together; the existing frontend already displays the API's source-access message.

## Generate novel profiles

From `backend/`, generate all three profiles with one command:

```bash
python -m profiler.profile_all NOVEL_ID --save
```

Each profile also has its own command:

```bash
python -m profiler.profile_protagonist NOVEL_ID --save
python -m profiler.profile_philosophy NOVEL_ID --save
python -m profiler.profile_storytelling NOVEL_ID --save
```

Omit `--save` for a preview, or add `--yes` with `--save` for a
non-interactive run.

<img width="1897" height="867" alt="image" src="https://github.com/user-attachments/assets/12f80dbe-02d0-430d-8269-db0b03bec5cb" />

<img width="1870" height="852" alt="image" src="https://github.com/user-attachments/assets/da312f4b-6d8f-4422-9caf-74abc0a09f85" />

<img width="778" height="861" alt="image" src="https://github.com/user-attachments/assets/0f6e57cd-9784-4351-9ef3-d4e466b59978" />

<img width="540" height="883" alt="image" src="https://github.com/user-attachments/assets/51f65908-542f-44e3-9d6c-dd1f009152fa" />

<img width="562" height="275" alt="image" src="https://github.com/user-attachments/assets/77fa7d42-7867-49c2-ab42-98e1f2e1d295" />

<img width="832" height="856" alt="image" src="https://github.com/user-attachments/assets/d817dbcd-6de3-498d-a925-de30ff5b019e" />

<img width="912" height="831" alt="image" src="https://github.com/user-attachments/assets/211e30ed-5bb9-462e-b100-1f5ed06a9cf8" />

<img width="917" height="816" alt="image" src="https://github.com/user-attachments/assets/b1cfc342-924b-442f-9b9a-3eeb5df6a79b" />





## Admin hub

Run `database/admin_hub.sql` once in the Supabase SQL editor. It grants SPECIAL
access to the existing **wafflehunter** account, locks catalog profile writes to
the backend, and blocks banned accounts through existing public-table RLS policies.
The migration fails without changing anything if wafflehunter does not exist.
Ensure `SUPABASE_SECRET_KEY` is configured in `backend/.env` (never in the frontend).
Restart the backend and open `/admin.html`, or choose **Admin hub** in the account menu.

The hub lists/searches accounts with pagination, bans/unbans ordinary accounts,
and searches novels to edit all three profiles. Scores must be integers from
0–100; each profile is saved separately. SPECIAL accounts cannot be banned.
Bans block new Supabase logins and authenticated backend actions, including
existing sessions. Public content remains available while signed out.

SPECIAL access uses server-owned `auth.users.raw_app_meta_data.axiom_special`;
usernames, user-editable metadata, and browser storage never authorize access.
To grant your co-developer access later, use their verified account UUID with the
commented SQL at the bottom of the migration. Set the flag to false to revoke.
For new RLS-protected tables, also add the restrictive `axiom_banned_accounts`
policy shown in the migration. Service-role operations bypass RLS and must
continue to use the shared backend authentication dependency.
