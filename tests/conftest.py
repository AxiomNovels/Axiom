import os
import sys
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

load_dotenv(ROOT / "tests" / ".env.test", override=True)

# Unit and integration tests do not contact Supabase. These defaults only let
# the application construct its client during test collection.
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_PUBLISHABLE_KEY", "test-publishable-key")
os.environ.setdefault("FRONTEND_ORIGIN", "http://localhost:3000")

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
