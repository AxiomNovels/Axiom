import os

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
