from fastapi import APIRouter, HTTPException

from core.database import supabase
from models.auth import AuthRequest


router = APIRouter(prefix="/api", tags=["authentication"])


def auth_error(error: Exception, default_status: int) -> HTTPException:
    message = str(error) or "Authentication request failed"
    lowered = message.lower()
    if "timed out" in lowered or "timeout" in lowered:
        return HTTPException(
            status_code=504,
            detail="Supabase did not respond in time. Check the backend's Supabase URL and network connection.",
        )
    return HTTPException(status_code=default_status, detail=message)


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
        raise auth_error(error, 400)

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
        raise auth_error(error, 401)

    return auth_response_payload(response)
