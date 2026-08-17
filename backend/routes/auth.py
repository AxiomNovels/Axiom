from fastapi import APIRouter, HTTPException

from core.database import supabase
from models.auth import AuthRequest


router = APIRouter(prefix="/api", tags=["authentication"])


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


@router.post("/signup", status_code=201)
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


@router.post("/login")
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
