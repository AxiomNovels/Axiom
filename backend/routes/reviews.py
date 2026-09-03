from fastapi import APIRouter, Depends, HTTPException, Response

from core.auth import get_current_user
from core.database import create_service_client
from models.review import ReviewUpsert


router = APIRouter(prefix="/api/novels", tags=["reviews"])

REVIEW_COLUMNS = "id, user_id, novel_id, rating, comment, created_at, updated_at"


def _attach_public_profiles(rows: list[dict], client) -> list[dict]:
    """Attach only public identity fields without relying on an embedded join.

    PostgREST can return a perfectly valid review with a null embedded profile
    when its relationship cache is stale.  A direct lookup is both more
    reliable and keeps the public surface deliberately small.
    """
    user_ids = list({row.get("user_id") for row in rows if row.get("user_id")})
    profiles_by_id = {}
    if user_ids:
        response = (
            client.table("profiles")
            .select("id, username, avatar_url")
            .in_("id", user_ids)
            .execute()
        )
        profiles_by_id = {profile["id"]: profile for profile in (response.data or [])}

    for row in rows:
        row["profiles"] = profiles_by_id.get(row.get("user_id"))
    return rows


def _review_payload(rows: list[dict]) -> dict:
    ratings = [float(row["rating"]) for row in rows]
    average = round(sum(ratings) / len(ratings), 2) if ratings else None
    return {
        "average_rating": average,
        "review_count": len(rows),
        "reviews": rows,
    }


@router.get("/{novel_id}/reviews")
def list_reviews(novel_id: int):
    try:
        client = create_service_client()
        response = (
            client.table("reviews")
            .select(REVIEW_COLUMNS)
            .eq("novel_id", novel_id)
            .order("updated_at", desc=True)
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    return _review_payload(_attach_public_profiles(response.data or [], client))


@router.put("/{novel_id}/reviews")
def save_review(
    novel_id: int,
    payload: ReviewUpsert,
    auth=Depends(get_current_user),
):
    user_id, client = auth
    review = {
        "user_id": user_id,
        "novel_id": novel_id,
        "rating": payload.rating,
        "comment": payload.comment,
    }

    try:
        response = (
            client.table("reviews")
            .upsert(review, on_conflict="novel_id,user_id")
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    if not response.data:
        raise HTTPException(status_code=500, detail="Review could not be saved.")
    return response.data[0]


@router.delete("/{novel_id}/reviews", status_code=204)
def delete_review(novel_id: int, auth=Depends(get_current_user)):
    user_id, client = auth
    try:
        response = (
            client.table("reviews")
            .delete()
            .eq("novel_id", novel_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    return Response(status_code=204)
