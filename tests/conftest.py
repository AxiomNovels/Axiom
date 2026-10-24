import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

# Unit and integration tests do not contact Supabase. These defaults only let
# the application construct its client during test collection.
if os.environ.get("AXIOM_LIVE_TESTS") != "1":
    os.environ.update({
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": "test-publishable-key",
        "SUPABASE_SECRET_KEY": "test-secret-key",
        "GEMINI_API_KEY": "test-gemini-key",
        "FRONTEND_ORIGIN": "http://localhost:3000",
    })

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
