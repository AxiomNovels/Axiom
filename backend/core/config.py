import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY")
# A deployed frontend can have both its Workers URL and a custom domain during
# a domain cutover.  Render environment variables are plain text, so accept a
# comma-separated list while retaining the original single-URL setting.
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
FRONTEND_ORIGINS = tuple(
    origin.strip().rstrip("/")
    for origin in FRONTEND_ORIGIN.split(",")
    if origin.strip()
)

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "Missing SUPABASE_URL or SUPABASE_PUBLISHABLE_KEY in backend/.env"
    )
