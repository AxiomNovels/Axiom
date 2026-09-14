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




