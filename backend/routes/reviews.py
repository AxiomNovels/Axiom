from fastapi import APIRouter, Depends, HTTPException, Response

from core.auth import get_current_user, get_optional_current_user
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


def _attach_like_data(rows: list[dict], client, viewer_id: str | None) -> list[dict]:
    """Attach like_count (public) and viewer_has_liked (only meaningful
    for a logged-in viewer) to each review, using one batched query
    instead of one per review.
    """
    review_ids = [row["id"] for row in rows if row.get("id")]
    if not review_ids:
        return rows

    try:
        response = (
            client.table("review_likes")
            .select("review_id, user_id")
            .in_("review_id", review_ids)
            .execute()
        )
        like_rows = response.data or []
    except Exception:
        # Likes are secondary to the review itself -- don't fail the
        # whole reviews request if this lookup has trouble.
        like_rows = []

    counts: dict[str, int] = {}
    liked_by_viewer: set[str] = set()
    for like in like_rows:
        review_id = like["review_id"]
        counts[review_id] = counts.get(review_id, 0) + 1
        if viewer_id and like["user_id"] == viewer_id:
            liked_by_viewer.add(review_id)

    for row in rows:
        row["like_count"] = counts.get(row["id"], 0)
        row["viewer_has_liked"] = row["id"] in liked_by_viewer

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
def list_reviews(novel_id: int, auth=Depends(get_optional_current_user)):
    viewer_id, _viewer_client = auth
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

    rows = response.data or []
    rows = _attach_public_profiles(rows, client)
    rows = _attach_like_data(rows, client, viewer_id)
    return _review_payload(rows)


@router.put("/{novel_id}/reviews")
def save_review(novel_id: int, payload: ReviewUpsert, auth=Depends(get_current_user)):
    user_id, client = auth
    review = {
        "user_id": user_id,
        "novel_id": novel_id,
        "rating": payload.rating,
        "comment": payload.comment,
    }
    try:
        response = client.table("reviews").upsert(review, on_conflict="novel_id,user_id").execute()
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    if not response.data:
        raise HTTPException(status_code=500, detail="Review could not be saved.")
    return response.data[0]


@router.delete("/{novel_id}/reviews", status_code=204)
def delete_review(novel_id: int, auth=Depends(get_current_user)):
    user_id, client = auth
    try:
        client.table("reviews").delete().eq("novel_id", novel_id).eq("user_id", user_id).execute()
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
    return Response(status_code=204)
