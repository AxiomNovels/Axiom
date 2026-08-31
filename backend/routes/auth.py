from fastapi import APIRouter, HTTPException

from core.database import create_service_client, supabase
from models.auth import LoginRequest, SignupRequest


router = APIRouter(prefix="/api", tags=["authentication"])


def humanize_auth_error(message: str) -> str:
    """Map common Supabase auth error text to clearer, user-facing wording."""
    lowered = message.lower()
    if "invalid login credentials" in lowered:
        return "Incorrect email/username or password."
    if "already registered" in lowered or "already exists" in lowered:
        return "An account with that email already exists."
    if "unable to validate email address" in lowered or "invalid email" in lowered:
        return "Please enter a valid email address."
    if "email not confirmed" in lowered:
        return "Please confirm your email address before logging in."
    if "password should be at least" in lowered:
        return message
    return message


def auth_error(error: Exception, default_status: int) -> HTTPException:
    message = str(error) or "Authentication request failed"
    lowered = message.lower()
    if "timed out" in lowered or "timeout" in lowered:
        return HTTPException(
            status_code=504,
            detail="Supabase did not respond in time. Check the backend's Supabase URL and network connection.",
        )
    return HTTPException(status_code=default_status, detail=humanize_auth_error(message))


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


def find_profile_id_by_username(username: str):
    response = (
        supabase.table("profiles")
        .select("id")
        .ilike("username", username)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0]["id"] if rows else None


@router.post("/signup", status_code=201)
def signup(payload: SignupRequest):
    if find_profile_id_by_username(payload.username) is not None:
        raise HTTPException(status_code=409, detail="That username is already taken.")

    try:
        response = supabase.auth.sign_up(
            {
                "email": payload.email,
                "password": payload.password,
                "options": {"data": {"username": payload.username}},
            }
        )
    except Exception as error:
        raise auth_error(error, 400)

    user = response.user
    if user:
        try:
            create_service_client().table("profiles").insert(
                {"id": user.id, "username": payload.username}
            ).execute()
        except Exception as error:
            # Almost always a duplicate username that slipped through the
            # check above in a race condition. Remove the auth account we
            # just created so a bad signup doesn't leave an orphaned user.
            try:
                create_service_client().auth.admin.delete_user(user.id)
            except Exception:
                pass
            raise HTTPException(
                status_code=409, detail="That username is already taken."
            ) from error

    return auth_response_payload(response)


@router.post("/login")
def login(payload: LoginRequest):
    identifier = payload.identifier.strip()

    if not identifier:
        raise HTTPException(status_code=422, detail="Please enter your email or username.")
    if not payload.password:
        raise HTTPException(status_code=422, detail="Please enter your password.")

    email = identifier

    if "@" not in identifier:
        profile_id = find_profile_id_by_username(identifier)
        if not profile_id:
            raise HTTPException(status_code=401, detail="Incorrect email/username or password.")

        try:
            user_response = create_service_client().auth.admin.get_user_by_id(profile_id)
        except Exception as error:
            raise auth_error(error, 500)

        user = getattr(user_response, "user", None)
        if not user or not user.email:
            raise HTTPException(status_code=401, detail="Incorrect email/username or password.")

        email = user.email

    try:
        response = supabase.auth.sign_in_with_password(
            {
                "email": email,
                "password": payload.password,
            }
        )
    except Exception as error:
        raise auth_error(error, 401)

    return auth_response_payload(response)