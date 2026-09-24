from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictBool
from postgrest.exceptions import APIError

from core.auth import get_current_user, get_optional_current_user
from core.database import create_service_client
from routes.admin import find_novel, require_special


router = APIRouter(prefix="/api", tags=["protagonist votes"])
Trait = Literal["impulsivity", "arrogance_pride", "kinship_friendship",
                "romantic_attachment", "sexual_desire", "selflessness"]


class Vote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    score: StrictInt = Field(ge=0, le=100)


class ScoreLock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    locked: StrictBool


@router.patch("/admin/novels/{novel_id}/protagonist-score-lock")
def set_score_lock(novel_id: int, payload: ScoreLock, admin=Depends(require_special)):
    client = admin[1]
    find_novel(client, novel_id)
    try:
        client.rpc("set_protagonist_score_lock", {
            "p_novel_id": novel_id, "p_locked": payload.locked,
        }).execute()
    except APIError as error:
        if error.code == "P0001":
            raise HTTPException(409, "Create a protagonist profile before locking scores.") from error
        raise
    return summary(client, novel_id)


def summary(client, novel_id, user_id=None):
    return client.rpc("protagonist_vote_summary", {
        "p_novel_id": novel_id, "p_user_id": str(user_id) if user_id else None,
    }).execute().data


@router.get("/novels/{novel_id}/protagonist-votes")
def get_votes(novel_id: int, auth=Depends(get_optional_current_user)):
    client = create_service_client()
    find_novel(client, novel_id)
    return summary(client, novel_id, auth[0])


@router.put("/novels/{novel_id}/protagonist-votes/{trait}")
def vote(novel_id: int, trait: Trait, payload: Vote, auth=Depends(get_current_user)):
    client = create_service_client()
    find_novel(client, novel_id)
    try:
        client.rpc("cast_protagonist_vote", {
            "p_novel_id": novel_id, "p_user_id": str(auth[0]),
            "p_trait": trait, "p_score": payload.score,
        }).execute()
    except APIError as error:
        if error.code == "P0001":
            raise HTTPException(409, "Voting opens when all six protagonist scores are filled in.") from error
        raise
    return summary(client, novel_id, auth[0])


@router.delete("/novels/{novel_id}/protagonist-votes/{trait}")
def withdraw_vote(novel_id: int, trait: Trait, auth=Depends(get_current_user)):
    client = create_service_client()
    find_novel(client, novel_id)
    client.table("protagonist_votes").delete().eq("novel_id", novel_id).eq(
        "user_id", str(auth[0])).eq("trait", trait).execute()
    return summary(client, novel_id, auth[0])


@router.get("/admin/novels/{novel_id}/protagonist-votes")
def novel_votes(novel_id: int, page: int = Query(1, ge=1), admin=Depends(require_special)):
    client = admin[1]
    novel = find_novel(client, novel_id)
    result = (client.table("protagonist_votes")
              .select("*,profiles(username)", count="exact").eq("novel_id", novel_id)
              .order("id").range((page - 1) * 25, page * 25 - 1).execute())
    return {"novel": novel, "summary": summary(client, novel_id),
            "votes": result.data or [], "total": result.count, "page": page}


@router.get("/admin/users/{user_id}/protagonist-votes")
def user_votes(user_id: UUID, page: int = Query(1, ge=1), admin=Depends(require_special)):
    result = (admin[1].table("protagonist_votes")
              .select("*,novels:protagonist_baselines(novels(title))", count="exact")
              .eq("user_id", str(user_id)).order("id")
              .range((page - 1) * 25, page * 25 - 1).execute())
    return {"votes": result.data or [], "total": result.count, "page": page}


@router.delete("/admin/protagonist-votes/{vote_id}")
def delete_vote(vote_id: int, admin=Depends(require_special)):
    result = admin[1].table("protagonist_votes").delete().eq("id", vote_id).execute()
    if not result.data:
        raise HTTPException(404, "Vote not found.")
    return {"deleted": len(result.data)}


@router.delete("/admin/users/{user_id}/protagonist-votes")
def delete_user_votes(user_id: UUID, admin=Depends(require_special)):
    # One SQL statement: the trigger recalculates every affected novel in the
    # same transaction, including votes beyond the admin listing's current page.
    admin[1].table("protagonist_votes").delete().eq("user_id", str(user_id)).execute()
    return {"deleted": True}
