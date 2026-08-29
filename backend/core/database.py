from supabase import create_client

from core.config import SUPABASE_KEY, SUPABASE_URL


supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def create_authenticated_client(access_token: str):
    """Create an isolated PostgREST client whose requests satisfy user RLS."""
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    client.options.headers["Authorization"] = f"Bearer {access_token}"
    return client
