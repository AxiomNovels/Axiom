from typing import Optional

from fastapi import Header, HTTPException

from core.database import create_authenticated_client, supabase


def get_current_user(authorization: Optional[str] = Header(None)):
    """Resolve the Supabase user id (and an RLS-scoped client) from a
    `Bearer <access_token>` header, the same header shape sent by the
    frontend's authFetch() helper.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="You must be logged in to do this.")

    access_token = authorization.split(" ", 1)[1].strip()

    try:
        user_response = supabase.auth.get_user(access_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Your session has expired. Please log in again.")

    user = getattr(user_response, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Your session has expired. Please log in again.")

    return user.id, create_authenticated_client(access_token)


def get_optional_current_user(authorization: Optional[str] = Header(None)):
    """Like get_current_user, but never raises: returns (None, supabase)
    when there's no bearer token, or when the token is missing/expired,
    instead of a 401.

    Used by endpoints that are public (anyone can view them, logged in or
    not) but need to know *who's viewing* to personalize the response --
    e.g. the public profile page, which shows friends-only social links
    only when the viewer is actually a friend.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return None, supabase

    access_token = authorization.split(" ", 1)[1].strip()

    try:
        user_response = supabase.auth.get_user(access_token)
    except Exception:
        return None, supabase

    user = getattr(user_response, "user", None)
    if not user:
        return None, supabase

    return user.id, create_authenticated_client(access_token)