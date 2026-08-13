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
uvicorn main:app --port 8000
```

