from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator

from core.auth import get_current_user
from core.database import create_service_client
from profiler.prompt import MEASURES
from services.novel_profiling_service import generate_protagonist_preview


PROFILES = {
    "protagonist": ("protagonist_profiles", MEASURES),
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


def home_feature_table_error(error: Exception) -> HTTPException:
    """Turn the missing migration's PostgREST error into an actionable one."""
    if "home_feature" in str(error) and "schema cache" in str(error):
        return HTTPException(
            status_code=503,
            detail="Home-page publishing is not set up yet. Run database/home_feature.sql in the Supabase SQL editor, then try again.",
        )
    return HTTPException(status_code=500, detail="Home-page feature could not be loaded. Please try again.")


class BanUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    banned: StrictBool


class ProfileScores(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scores: dict[str, StrictInt]
    protagonist_name: str | None = None


class HomeFeatureUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    novel_id: int = Field(gt=0)
    inquiry: str = Field(min_length=10, max_length=240)
    description: str = Field(min_length=10, max_length=500)
    tags: list[str] = Field(default_factory=list, max_length=4)

    @field_validator("inquiry", "description")
    @classmethod
    def nonblank_copy(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be empty.")
        return value

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, tags: list[str]) -> list[str]:
        cleaned = [tag.strip() for tag in tags if tag.strip()]
        if len(cleaned) > 4 or any(len(tag) > 40 for tag in cleaned):
            raise ValueError("Use up to four tags, each no longer than 40 characters.")
        return cleaned


@router.get("/me")
def admin_me(admin=Depends(require_special)):
    return {"id": admin[0], "special": True}


@router.get("/home-feature")
def get_home_feature(admin=Depends(require_special)):
    client = admin[1]
    try:
        feature = client.table("home_feature").select("novel_id,inquiry,description,tags,updated_at").eq("id", True).maybe_single().execute().data
    except Exception as error:
        raise home_feature_table_error(error) from error
    if not feature:
        return {"feature": None}
    novel = find_novel(client, feature["novel_id"])
    return {"feature": {**feature, "novel": novel}}


@router.put("/home-feature")
def save_home_feature(payload: HomeFeatureUpdate, admin=Depends(require_special)):
    client = admin[1]
    find_novel(client, payload.novel_id)
    try:
        client.table("home_feature").upsert({"id": True, **payload.model_dump()}, on_conflict="id").execute()
    except Exception as error:
        raise home_feature_table_error(error) from error
    return {"saved": True}


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


@router.post("/novels/{novel_id}/profiles/protagonist/generate")
def generate_scores(novel_id: int, admin=Depends(require_special)):
    result = (
        admin[1].table("novels")
        .select("id,title,synopsis,genres,tags,reading_links,protagonist_profiles(protagonist_name)")
        .eq("id", novel_id).limit(1).execute()
    )
    if not result.data:
        raise HTTPException(404, "Novel not found.")
    profile = generate_protagonist_preview(result.data[0])
    if profile.get("status") != "ready":
        raise HTTPException(422 if profile.get("status") == "skipped" else 502,
                            profile.get("message") or "Gemini could not generate this profile. Try again.")
    return profile


@router.put("/novels/{novel_id}/profiles/{kind}")
def save_scores(novel_id: int, kind: Literal["protagonist"],
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
