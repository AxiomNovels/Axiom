"""Durable, rate-limited protagonist-profile rebuild jobs for the admin hub."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from core.database import create_service_client
from profiler.prompt import MEASURES
from profiler.regenerate_profiles import regenerate


PAGE_SIZE = 500
DEFAULT_DELAY_SECONDS = 1.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rows(client, table: str, columns: str) -> list[dict]:
    rows, offset = [], 0
    while True:
        page = client.table(table).select(columns).order("id").range(offset, offset + PAGE_SIZE - 1).execute().data or []
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def candidate_novel_ids(client, include_complete: bool) -> list[int]:
    novel_ids = [row["id"] for row in _rows(client, "novels", "id")]
    if include_complete:
        return novel_ids
    complete = {
        row["novel_id"] for row in _rows(client, "protagonist_profiles", "novel_id," + ",".join(MEASURES))
        if all(row.get(measure) is not None for measure in MEASURES)
    }
    return [novel_id for novel_id in novel_ids if novel_id not in complete]


def create_job(requested_by: str, include_complete: bool) -> dict:
    client = create_service_client()
    active = client.table("protagonist_rebuild_jobs").select("id").in_("status", ["queued", "running"]).limit(1).execute().data or []
    if active:
        raise ValueError("A protagonist-profile rebuild is already running.")
    novel_ids = candidate_novel_ids(client, include_complete)
    job = client.table("protagonist_rebuild_jobs").insert({
        "requested_by": requested_by, "mode": "all" if include_complete else "outdated", "total": len(novel_ids),
    }).execute().data[0]
    for start in range(0, len(novel_ids), PAGE_SIZE):
        client.table("protagonist_rebuild_items").insert([
            {"job_id": job["id"], "novel_id": novel_id} for novel_id in novel_ids[start:start + PAGE_SIZE]
        ]).execute()
    return job


def job_status(job_id: str) -> dict | None:
    client = create_service_client()
    rows = client.table("protagonist_rebuild_jobs").select("*").eq("id", job_id).limit(1).execute().data or []
    return rows[0] if rows else None


def job_items(job_id: str) -> list[dict]:
    client = create_service_client()
    return (
        client.table("protagonist_rebuild_items")
        .select("novel_id,status,error,novels(title)")
        .eq("job_id", job_id).order("id").limit(1000).execute().data or []
    )


def run_job(job_id: str) -> None:
    """Run outside the request. Safe to retry: completed items are never selected."""
    client = create_service_client()
    client.table("protagonist_rebuild_jobs").update({"status": "running", "started_at": _now()}).eq("id", job_id).execute()
    while True:
        items = (client.table("protagonist_rebuild_items").select("id,novel_id")
                 .eq("job_id", job_id).eq("status", "queued").order("id").limit(1).execute().data or [])
        if not items:
            break
        item = items[0]
        client.table("protagonist_rebuild_items").update({"status": "running", "started_at": _now()}).eq("id", item["id"]).execute()
        status, error = "completed", None
        try:
            regenerate(item["novel_id"], minimum_confidence=75, fetch_comments=True, save=True)
        except Exception as exc:  # retain each failure for admin review/retry
            status, error = "failed", str(exc)[:1000]
        client.table("protagonist_rebuild_items").update({"status": status, "error": error, "finished_at": _now()}).eq("id", item["id"]).execute()
        counts = client.table("protagonist_rebuild_items").select("status").eq("job_id", job_id).execute().data or []
        completed = sum(row["status"] == "completed" for row in counts)
        failed = sum(row["status"] == "failed" for row in counts)
        client.table("protagonist_rebuild_jobs").update({"processed": completed + failed, "succeeded": completed, "failed": failed}).eq("id", job_id).execute()
        time.sleep(DEFAULT_DELAY_SECONDS)
    client.table("protagonist_rebuild_jobs").update({"status": "completed", "finished_at": _now()}).eq("id", job_id).execute()

