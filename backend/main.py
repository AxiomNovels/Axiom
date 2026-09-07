from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routes.auth import router as auth_router
from routes.friendships import router as friendships_router
from routes.inbox import router as inbox_router
from routes.novels import router as novels_router
from routes.profile import router as profile_router
from routes.search import router as search_router
from routes.reading_lists import router as reading_lists_router
from routes.reading_progress import router as reading_progress_router
from routes.users import router as users_router
from routes.reviews import router as reviews_router
from core.config import FRONTEND_ORIGIN


app = FastAPI(title="Axiom Backend")

# Both addresses refer to the local frontend, but browsers treat them as
# different origins. Supporting both avoids a confusing CORS failure when the
# frontend is opened with the numeric loopback address.
frontend_origins = list(dict.fromkeys([
    FRONTEND_ORIGIN,
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]))

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Field names -> a friendly, human-readable description, used to build
# specific "please enter X" messages instead of FastAPI's raw, generic
# validation output (e.g. "field required").
FIELD_LABELS = {
    "identifier": "your email or username",
    "email": "your email",
    "username": "a username",
    "password": "your password",
}


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Turn FastAPI's raw validation error list into one clear sentence.

    Without this, any missing or invalid form field on signup or login
    surfaces to the user as a cryptic "field required" message with no
    indication of which field, or which page, it came from.
    """
    errors = exc.errors()
    first_error = errors[0] if errors else {}
    location = first_error.get("loc", [])
    field = location[-1] if location else None
    label = FIELD_LABELS.get(field, "the required information")
    error_type = first_error.get("type", "")

    if error_type == "missing":
        message = f"Please enter {label}."
    elif field == "email":
        message = "Please enter a valid email address."
    else:
        # Our own field validators (e.g. the username format check) raise
        # ValueError with a specific message; pydantic prefixes it with
        # "Value error, " which isn't meant for end users, so strip it.
        message = first_error.get("msg", "Please check the form and try again.")
        message = message.removeprefix("Value error, ")

    return JSONResponse(status_code=422, content={"detail": message})


app.include_router(auth_router)
app.include_router(reviews_router)
app.include_router(novels_router)
app.include_router(profile_router)
app.include_router(search_router)
app.include_router(reading_lists_router)
app.include_router(reading_progress_router)
app.include_router(users_router)
app.include_router(inbox_router)
app.include_router(friendships_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}