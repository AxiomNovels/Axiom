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

# Optional admin-only Cloudflare GraphQL Analytics integration. Keep these
# values backend-only; they must never be included in runtime-config.js.
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_ZONE_ID = os.getenv("CLOUDFLARE_ZONE_ID")
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_ANALYTICS_HOSTS = tuple(
    host.strip().lower() for host in os.getenv(
        "CLOUDFLARE_ANALYTICS_HOSTS", "axiomnovels.com,www.axiomnovels.com"
    ).split(",") if host.strip()
)
CLOUDFLARE_ANALYTICS_TIMEZONE = os.getenv("CLOUDFLARE_ANALYTICS_TIMEZONE", "UTC")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "Missing SUPABASE_URL or SUPABASE_PUBLISHABLE_KEY in backend/.env"
    )
