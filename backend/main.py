import os
import re

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_PUBLISHABLE_KEY in backend/.env")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(title="Axiom Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuthRequest(BaseModel):
    email: EmailStr
    password: str


def to_jsonable(value):
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    return value


def auth_response_payload(response):
    return {
        "user": to_jsonable(response.user),
        "session": to_jsonable(response.session),
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/signup", status_code=201)
def signup(payload: AuthRequest):
    try:
        response = supabase.auth.sign_up(
            {
                "email": payload.email,
                "password": payload.password,
            }
        )
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error))

    return auth_response_payload(response)


@app.post("/api/login")
def login(payload: AuthRequest):
    try:
        response = supabase.auth.sign_in_with_password(
            {
                "email": payload.email,
                "password": payload.password,
            }
        )
    except Exception as error:
        raise HTTPException(status_code=401, detail=str(error))

    return auth_response_payload(response)


# Novels

# Fields used for the home page grid -- deliberately lighter than the full
# detail payload (no profile scores needed just to render a card).
NOVEL_LIST_COLUMNS = "id, title, author, cover_image_url, synopsis, status, genres"

# The three profile tables are embedded via their novel_id foreign key.
# Each has a UNIQUE(novel_id) constraint, so PostgREST embeds them as a
# single object per novel rather than an array.
NOVEL_DETAIL_COLUMNS = (
    "*, "
    "protagonist_profiles(*), "
    "philosophy_profiles(*), "
    "storytelling_style_profiles(*)"
)


def searchable_text(value):
    """Return lowercase words suitable for small-catalogue relevance scoring."""
    return re.findall(r"[a-z0-9]+", str(value or "").lower())


def novel_relevance(novel, query):
    """Score a novel, favoring title and author matches over metadata/body text."""
    query_text = " ".join(searchable_text(query))
    query_terms = query_text.split()
    if not query_terms:
        return 0

    title = " ".join(searchable_text(novel.get("title")))
    author = " ".join(searchable_text(novel.get("author")))
    genres = " ".join(searchable_text(" ".join(novel.get("genres") or [])))
    synopsis = " ".join(searchable_text(novel.get("synopsis")))

    score = 0
    if title == query_text:
        score += 250
    elif title.startswith(query_text):
        score += 140
    elif query_text in title:
        score += 100

    if author == query_text:
        score += 100
    elif query_text in author:
        score += 60

    for term in query_terms:
        if term in title.split():
            score += 45
        elif any(word.startswith(term) for word in title.split()):
            score += 30

        if term in author.split():
            score += 22
        if term in genres.split():
            score += 16
        if term in synopsis.split():
            score += 5

    # Results matching more of the entered words should sort above partial matches.
    fields = f"{title} {author} {genres} {synopsis}"
    matched_terms = sum(term in fields.split() for term in query_terms)
    score += matched_terms * 8
    if matched_terms == len(query_terms):
        score += 25

    return score


@app.get("/api/novels")
def list_novels():
    try:
        response = (
            supabase.table("novels")
            .select(NOVEL_LIST_COLUMNS)
            .order("title")
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    return response.data


@app.get("/api/novels/{novel_id}")
def get_novel(novel_id: int):
    try:
        response = (
            supabase.table("novels")
            .select(NOVEL_DETAIL_COLUMNS)
            .eq("id", novel_id)
            .single()
            .execute()
        )
    except Exception as error:
        # supabase-py raises when .single() finds zero (or >1) rows
        raise HTTPException(status_code=404, detail="Novel not found")

    return response.data


@app.get("/api/search")
def search_novels(q: str = ""):
    query = q.strip()
    if not query:
        return []

    try:
        response = (
            supabase.table("novels")
            .select(NOVEL_LIST_COLUMNS)
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    ranked = []
    for novel in response.data or []:
        relevance = novel_relevance(novel, query)
        if relevance > 0:
            ranked.append((relevance, novel))

    ranked.sort(key=lambda item: (-item[0], item[1].get("title", "").lower()))
    return [novel for _, novel in ranked]
