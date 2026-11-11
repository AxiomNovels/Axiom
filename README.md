# Axiom

A novel discovery app designed to connect readers to Webnovels.

## Features

* Filtering based on title, description, tags, genre, and protagonist profile
* Protagonist profiling powered by Gemini API and trait voting
* Reader reviews and reading lists
* Notifications and a personalized inbox, including an email delivery system
* Social features such as friend system and profile customization

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