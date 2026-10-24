"""Bounded, best-effort telemetry. Never block a reader on an analytics write."""
import ipaddress
import logging
import os
import queue
import re
import threading
import time
from datetime import datetime, timezone
from uuid import uuid4

from core.database import create_service_client

logger = logging.getLogger(__name__)
ENABLED = os.getenv("ANALYTICS_ENABLED", "false").lower() == "true"
LOG_IPS = os.getenv("ANALYTICS_LOG_IPS", "false").lower() == "true"
EDGE_SECRET = os.getenv("ANALYTICS_EDGE_SECRET", "")
pending = queue.Queue(maxsize=5000)
_lock = threading.Lock()
_started = False
_stats = {"accepted": 0, "dropped": 0, "write_failures": 0, "last_write": None}
_limits = {}
_last_prune = 0
PAGE_NAMES = frozenset("activity admin analytics-privacy finder friends inbox index list lists login mission novel profile protagonist-profile-info readers search shared-list signup team under-construction upload user vote".split())


def country(value):
    return value if value and re.fullmatch(r"[A-Z]{2}", value) else "XX"


def clean_path(value):
    """Never retain query strings, fragments, or arbitrary identifier paths."""
    path = str(value).split("?", 1)[0].split("#", 1)[0]
    if not path.startswith("/") or len(path) > 240 or re.search(r"[\x00-\x20\\]", path):
        return "/other"
    if path.startswith("/api/"):
        return path if "{" in path else "/api/other"
    page = path.strip("/").removesuffix(".html")
    if path == "/" or page in PAGE_NAMES:
        return path
    return "/assets/*" if path.startswith("/assets/") else "/other"


def allow(key, maximum=90):
    """Bounded per-process limiter; deploy an edge rate limit for multi-worker traffic."""
    global _last_prune
    now = time.monotonic()
    with _lock:
        if now-_last_prune >= 60 or len(_limits) >= 10000:
            for old in [k for k, v in _limits.items() if now-v[0] >= 60]:
                _limits.pop(old, None)
            _last_prune = now
        if len(_limits) >= 10000 and key not in _limits:
            return False
        start, count = _limits.get(key, (now, 0))
        if now-start >= 60:
            start, count = now, 0
        _limits[key] = (start, count+1)
        return count < maximum


def submit(record):
    global _started
    if not ENABLED:
        return False
    record = {"id": str(uuid4()), "country": "XX", "kind": "page", **record}
    record["path"] = clean_path(record.get("path", "/"))
    record["country"] = country(record.get("country"))
    if not LOG_IPS:
        record.pop("ip", None)
    elif record.get("ip"):
        try:
            record["ip"] = str(ipaddress.ip_address(record["ip"]))
        except ValueError:
            record.pop("ip", None)
    with _lock:
        if not _started:
            threading.Thread(target=_writer, name="axiom-analytics", daemon=True).start()
            _started = True
    try:
        pending.put_nowait(record)
        _stats["accepted"] += 1
        return True
    except queue.Full:
        _stats["dropped"] += 1
        return False


def _writer():
    while True:
        batch = [pending.get()]
        # Group concurrent activity; keep the database call off request threads.
        time.sleep(2)
        while len(batch) < 100:
            try:
                batch.append(pending.get_nowait())
            except queue.Empty:
                break
        try:
            create_service_client().rpc("analytics_ingest", {"p_events": batch}).execute()
            _stats["last_write"] = datetime.now(timezone.utc).isoformat()
        except Exception:
            _stats["write_failures"] += 1
            _stats["dropped"] += len(batch)
            # Never log event bodies, tokens, or IP addresses.
            logger.warning("Analytics batch write failed; check migration and service configuration.")
        finally:
            for _ in batch:
                pending.task_done()


def health():
    return {"enabled": ENABLED, "ip_logging": LOG_IPS, "edge_configured": bool(EDGE_SECRET),
            "queued": pending.qsize(), **_stats}
