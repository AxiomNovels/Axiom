# Pull merge resolution — October 13, 2026

Compared the common ancestor `5342571` with both branch tips using Git logs,
commit diffs, and the conflict stages:

- Local `b2733f2`: editable Admin Hub trait definitions, transactional schema/data
  updates, dynamic clients, and revision-aware profiling/voting.
- Incoming `7a0ca74`: seven default traits and a new scoring rubric, plus a legacy
  schema migration. Incoming `ca44dd8` updates the team blog.

All 17 conflicted files are resolved. The seven defaults are intelligence,
charisma, moral integrity, kinship and friendship, romantic attachment, erotic
desire, and arrogance and conceit. Their incoming rubric is now in the editable
JSON/SQL seed. Runtime traits, prompts, labels, and eligibility still come from
the saved Admin Hub definition. Neither trait lists nor vote/profile writes have
been changed back to fixed, unversioned contracts.

## Resolution decisions

- Keep the dynamic implementation in the profiling CLI, regeneration, search,
  recommendations, voting, Admin Hub, novel view, Finder, and public guide.
  Adding/editing/deleting traits still updates the schema and clears affected
  scores, baselines, and votes transactionally, including locked profiles.
- Store incoming trait distinctions in the corresponding editable prompts.
  Derive the requested trait count from the current definition, so adding a trait
  cannot leave an instruction to generate exactly seven scores.
- Use the incoming “Arrogance & Conceit” label consistently in the default seed.
  Preserve older fallback labels and comment-selection terms for existing saved
  definitions, while adding the incoming evidence terms.
- Have the prompt playground use the production builder and revision snapshot;
  retain the old rubric as an explicitly unused historical reference.
- Retain the incoming team/blog file unchanged from `MERGE_HEAD`.
- Preserve both branches' regression coverage: seven-default assertions plus
  custom-trait rendering, definition editing, stale revisions, and permissions.

## Migration order

For a legacy installation adopting the seven defaults, apply the existing
profile/measures migrations, `protagonist_votes.sql`,
`protagonist_vote_controls.sql`, then `protagonist_profile_traits_v2.sql`.
The v2 migration intentionally clears legacy scores, votes, and baselines and
unlocks profiles. Apply `admin_hub.sql` before `manage_protagonist_profile.sql`,
then deploy the matching backend and frontend together. Rebuild profiles using
the existing tools.

If `protagonist_definition` already exists, the saved definition wins, including
custom or previous ten-trait definitions. Reapplying the bootstrap must not erase
administrative changes. Adopt the seven-trait rubric through Manage Protagonist
Profile if desired; `backend/profiler/default_definition.json` contains its text.
The legacy v2 migration now rejects this installation state before any writes,
preventing it from wiping custom data or restoring unversioned save/vote RPCs.

No live Supabase migration, deployment, Gemini call, or remote Git push was made.

## Verification

- Targeted API/profiling/search/voting suites: **144 passed**. After adding the
  playground snapshot check and retaining legacy evidence terms, the definition
  and profiler suites also passed (**45 tests**).
- Isolated Playwright voting/Admin Hub/Finder/guide suite: **11 passed**.
- All three isolated PGlite suites passed: legacy voting, dynamic definitions,
  and the newly added combined trait-migration suite. The latter verifies the
  legacy reset, seven-trait voting, dynamic editing, custom-definition
  preservation, stale-result rejection, and migration-order/permission guards.
- JavaScript syntax checks and Git whitespace checks passed.
- The full fast runner encounters an existing collection error in
  `tests/unit/test_auth_model.py`: it imports the removed `AuthRequest`.
  Running the remaining unit/integration tests gave **241 passed, 2 failed**:
  `test_source_refusal_stops_scraping_instead_of_retrying_pool[503]` expects a
  scraper abort, and `test_similar_endpoint_searches_beyond_first_page` expects
  genre-based ranking where the implementation uses tags. The affected tests
  and implementations are unchanged from the local parent. Assertions were not
  weakened to hide these failures.

Reproduce the isolated database checks with `npm.cmd run test:votes --prefix
tests`, `npm.cmd run test:definitions --prefix tests`, and `npm.cmd run
test:trait-migrations --prefix tests`. Browser checks use
`backend\.venv\Scripts\python.exe -m pytest -c tests/pytest.ini
tests/e2e/test_protagonist_voting.py -q -p no:cacheprovider`.

## Files reviewed and changed

Conflicts resolved in:

- `backend/profiler/{profile_novel,prompt,regenerate_profiles}.py`
- `backend/routes/{protagonist_votes,search}.py` and
  `backend/services/search_service.py`
- `database/PROTAGONIST_VOTING.md`
- `frontend/public/{admin-votes,finder,novel,protagonist-profile-info,protagonist-votes,search}.js`
  and `frontend/public/protagonist-profile-info.html`
- `tests/e2e/test_protagonist_voting.py` and
  `tests/unit/{test_profile_retirement,test_protagonist_votes}.py`

Additional integration changes or incoming changes retained in:

- `backend/profiler/{default_definition.json,QUICKSTART.txt,comments.py,prompt_playground.py,test_profiler.py}`
- `backend/services/novel_profiling_service.py`
- `database/{manage_protagonist_profile.sql,protagonist_profile_traits_v2.sql}`
- `frontend/public/{admin.js,team.html}`
- `tests/unit/{test_latency_paths,test_protagonist_definition,test_recommendation_service}.py`
- `tests/integration/{protagonist_definition_database,protagonist_trait_migration_database}.mjs`
- `tests/package.json`, `README.md`, `tests/README.md`, and the implementation
  and merge reports in `database/`.

Files resolved identically to the local parent do not appear in the merge's
first-parent diff. The uploaded `database/table_schema.js` remains unchanged.
