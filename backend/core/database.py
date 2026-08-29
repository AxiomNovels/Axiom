import os

from supabase import create_client

from core.config import SUPABASE_KEY, SUPABASE_URL


supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def create_authenticated_client(access_token: str):
    """Create an isolated PostgREST client whose requests satisfy user RLS."""
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    client.options.headers["Authorization"] = f"Bearer {access_token}"
    return client


def create_service_client():
    """Create a Supabase client authorized with the service-role secret key.

    Used for privileged writes (e.g. publishing a novel a user has
    submitted) that should not depend on end-user RLS policies. Mirrors
    the secret-key clients already used by scraper/staging.py,
    scraper/publish.py, and profiler/profile_novel.py.
    """
    secret_key = os.getenv("SUPABASE_SECRET_KEY")
    if not secret_key:
        raise RuntimeError("Missing SUPABASE_SECRET_KEY in backend/.env")
    return create_client(SUPABASE_URL, secret_key)