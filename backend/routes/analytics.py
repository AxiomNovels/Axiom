"""Public event intake, trusted edge intake, and SPECIAL-only analytics reports."""
import csv
import hmac
import io
import logging
import re
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from core.auth import get_optional_current_user
from core.config import FRONTEND_ORIGINS
from models.analytics import BrowserEvent, EdgeRequest
from routes.admin import require_special
from services import analytics_service as analytics

router = APIRouter(prefix="/api", tags=["analytics"])
logger = logging.getLogger(__name__)


def trusted(request):
    supplied = request.headers.get("x-axiom-edge-secret", "")
    return bool(analytics.EDGE_SECRET and hmac.compare_digest(supplied.encode(), analytics.EDGE_SECRET.encode()))


@router.get("/analytics/config")
def public_config(response: Response):
    """Only the public collection flag; never expose edge or database credentials."""
    response.headers["Cache-Control"] = "no-store"
    return {"enabled": analytics.ENABLED}


@router.post("/analytics/events", status_code=202)
def collect(event: BrowserEvent, request: Request, auth=Depends(get_optional_current_user)):
    if not analytics.ENABLED:
        return {"accepted": False}
    edge = trusted(request)
    origin = request.headers.get("origin")
    # CORS alone does not prevent cross-site writes. Reject browser origins we do not serve.
    if origin and origin not in FRONTEND_ORIGINS and not re.fullmatch(r"http://(localhost|127\.0\.0\.1)(:\d+)?", origin):
        raise HTTPException(403, "Origin is not allowed.")
    address = request.headers.get("x-axiom-client-ip", "unknown") if edge else (request.client.host if request.client else "unknown")
    if not analytics.allow(("browser", address), 120):
        raise HTTPException(429, "Too many analytics events.")
    record = event.model_dump(mode="json")
    record.update(source="browser", user_id=str(auth[0]) if auth[0] else None,
                  country=request.headers.get("x-axiom-country") if edge else "XX")
    # Browser identity is established only by backend authentication, never payload fields.
    accepted = analytics.submit(record)
    return {"accepted": accepted}


@router.post("/analytics/edge", status_code=202)
def edge_request(event: EdgeRequest, request: Request):
    if not trusted(request):
        raise HTTPException(403, "Trusted edge access is required.")
    record = event.model_dump(mode="json")
    return {"accepted": analytics.submit({**record, "source": "frontend", "event": "request"})}


def report_data(client, start, end, country):
    if start > end or (end-start).days > 89 or end > datetime.now(timezone.utc).date():
        raise HTTPException(422, "Choose a date range of up to 90 days, ending today or earlier (UTC).")
    try:
        return client.rpc("analytics_report", {"p_start": start.isoformat(), "p_end": end.isoformat(), "p_country": country}).execute().data
    except Exception:
        logger.warning("Analytics report unavailable; check database migration.")
        raise HTTPException(503, "Analytics is not ready. Apply database/analytics.sql and check backend configuration.")


@router.get("/admin/analytics")
def report(start: date, end: date, country: str | None = Query(None, pattern=r"^[A-Z]{2}$"), admin=Depends(require_special)):
    return {"start": start, "end": end, "country": country,
            "report": report_data(admin[1], start, end, country), "collection": analytics.health()}


@router.get("/admin/analytics/export")
def export(start: date, end: date, country: str | None = Query(None, pattern=r"^[A-Z]{2}$"), admin=Depends(require_special)):
    data = report_data(admin[1], start, end, country)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date_utc", "page_views", "visits", "frontend_requests", "backend_requests", "active_seconds", "signups"])
    for row in data.get("daily", []):
        writer.writerow([row.get(key, "") for key in ("date", "page_views", "visits", "frontend_requests", "backend_requests", "active_seconds", "signups")])
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="axiom-analytics.csv"', "Cache-Control": "no-store"})


@router.get("/admin/analytics/ip-logs")
def ip_logs(page: int = Query(1, ge=1, le=1000), admin=Depends(require_special)):
    # Explicit access, no IPs in ordinary reports/exports. Log only the access, not its contents.
    logger.warning("Restricted analytics IP log accessed by SPECIAL account %s", admin[0])
    since = (datetime.now(timezone.utc)-timedelta(days=7)).isoformat()
    try:
        rows = admin[1].table("analytics_ip_logs").select("event_id,occurred_at,ip").gte("occurred_at", since).order("occurred_at", desc=True).range((page-1)*50, page*50-1).execute().data
        return {"rows": rows, "page": page}
    except Exception:
        raise HTTPException(503, "IP log is unavailable. Check the analytics migration.")
