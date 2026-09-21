from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, StrictBool, StrictInt

from core.auth import get_current_user
from core.database import create_service_client
from profiler.prompt import MEASURES, PHILOSOPHY_MEASURES, STORYTELLING_MEASURES


PROFILES = {
    "protagonist": ("protagonist_profiles", MEASURES),
    "philosophy": ("philosophy_profiles", PHILOSOPHY_MEASURES),
    "storytelling": ("storytelling_style_profiles", STORYTELLING_MEASURES),
}


def require_special(auth=Depends(get_current_user)):
    user_id, _ = auth
    client = create_service_client()
    user = client.auth.admin.get_user_by_id(user_id).user
    metadata = (user.app_metadata or {}) if user else {}
    if metadata.get("axiom_special") is not True or metadata.get("axiom_banned") is True:
        raise HTTPException(403, "SPECIAL account access is required.")
    return user_id, client


router = APIRouter(prefix="/api/admin", tags=["admin"])


class BanUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    banned: StrictBool


class ProfileScores(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scores: dict[str, StrictInt]
    protagonist_name: str | None = None


@router.get("/me")
def admin_me(admin=Depends(require_special)):
    return {"id": admin[0], "special": True}


@router.get("/users")
def users(q: str = Query("", max_length=100), page: int = Query(1, ge=1), admin=Depends(require_special)):
    _, client = admin
    query = client.table("profiles").select("id,username,created_at", count="exact")
    if q.strip():
        query = query.ilike("username", "%" + q.strip().replace("%", "\\%").replace("_", "\\_") + "%")
    result = query.order("username").order("id").range((page - 1) * 25, page * 25 - 1).execute()
    rows = []
    for profile in result.data or []:
        user = client.auth.admin.get_user_by_id(profile["id"]).user
        metadata = (user.app_metadata or {}) if user else {}
        rows.append({**profile, "special": metadata.get("axiom_special") is True,
                     "banned": metadata.get("axiom_banned") is True})
    return {"users": rows, "total": result.count, "page": page}


@router.patch("/users/{user_id}/ban")
def ban_user(user_id: UUID, payload: BanUpdate, admin=Depends(require_special)):
    actor_id, client = admin
    if str(user_id) == str(actor_id):
        raise HTTPException(409, "You cannot ban your own account.")
    try:
        target = client.auth.admin.get_user_by_id(str(user_id)).user
    except Exception:
        raise HTTPException(404, "Account not found.")
    if not target:
        raise HTTPException(404, "Account not found.")
    metadata = target.app_metadata or {}
    if metadata.get("axiom_special") is True:
        raise HTTPException(409, "SPECIAL accounts cannot be banned. Remove their privilege first.")
    client.auth.admin.update_user_by_id(str(user_id), {
        "ban_duration": "876000h" if payload.banned else "none",
        "app_metadata": {**metadata, "axiom_banned": payload.banned},
    })
    return {"id": str(user_id), "banned": payload.banned}


@router.get("/novels")
def novels(q: str = Query("", max_length=150), page: int = Query(1, ge=1), admin=Depends(require_special)):
    query = admin[1].table("novels").select("id,title,author", count="exact")
    if q.strip():
        query = query.ilike("title", "%" + q.strip().replace("%", "\\%").replace("_", "\\_") + "%")
    result = query.order("title").order("id").range((page - 1) * 25, page * 25 - 1).execute()
    return {"novels": result.data or [], "total": result.count, "page": page}


def find_novel(client, novel_id):
    result = client.table("novels").select("id,title").eq("id", novel_id).limit(1).execute()
    if not result.data:
        raise HTTPException(404, "Novel not found.")
    return result.data[0]


@router.get("/novels/{novel_id}/profiles")
def novel_profiles(novel_id: int, admin=Depends(require_special)):
    client = admin[1]
    novel = find_novel(client, novel_id)
    profiles = {}
    for kind, (table, measures) in PROFILES.items():
        result = client.table(table).select("*").eq("novel_id", novel_id).limit(1).execute()
        row = result.data[0] if result.data else {}
        profiles[kind] = {"scores": {key: row.get(key) for key in measures}}
        if kind == "protagonist":
            profiles[kind]["protagonist_name"] = row.get("protagonist_name", "")
    return {"novel": novel, "profiles": profiles}


@router.put("/novels/{novel_id}/profiles/{kind}")
def save_scores(novel_id: int, kind: Literal["protagonist", "philosophy", "storytelling"],
                payload: ProfileScores, admin=Depends(require_special)):
    table, measures = PROFILES[kind]
    if set(payload.scores) != set(measures) or any(not 0 <= value <= 100 for value in payload.scores.values()):
        raise HTTPException(422, "Supply every score in this profile as a whole number from 0 to 100.")
    row = {"novel_id": novel_id, **payload.scores}
    if kind == "protagonist":
        name = (payload.protagonist_name or "").strip()
        if not name or len(name) > 200:
            raise HTTPException(422, "Enter a protagonist name of 1–200 characters.")
        row["protagonist_name"] = name
    elif payload.protagonist_name is not None:
        raise HTTPException(422, "Only the protagonist profile accepts a protagonist name.")
    find_novel(admin[1], novel_id)
    admin[1].table(table).upsert(row, on_conflict="novel_id").execute()
    return {"saved": True}
