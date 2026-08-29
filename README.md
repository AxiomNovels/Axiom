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

To list a tree structure of all files (ignoring those in .gitignore):
git ls-files -co --exclude-standard

