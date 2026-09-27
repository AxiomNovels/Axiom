from fastapi import APIRouter, Depends, HTTPException, Response

from core.auth import get_current_user, get_optional_current_user
from core.database import create_service_client
from models.review import ReviewReplyCreate, ReviewUpsert


router = APIRouter(prefix="/api/novels", tags=["reviews"])

REVIEW_COLUMNS = "id, user_id, novel_id, rating, comment, created_at, updated_at"
REPLY_COLUMNS = "id, review_id, parent_reply_id, user_id, comment, created_at"


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


def _attach_replies(rows: list[dict], client) -> list[dict]:
    """Attach replies as a nested tree under each review.

    The database retains a simple parent id, which keeps replies easy to
    query and lets the client render an arbitrary reply depth without issuing
    one request per comment.
    """
    review_ids = [row["id"] for row in rows if row.get("id")]
    if not review_ids:
        return rows

    response = (
        client.table("review_replies")
        .select(REPLY_COLUMNS)
        .in_("review_id", review_ids)
        .order("created_at")
        .execute()
    )
    replies = _attach_public_profiles(response.data or [], client)
    replies_by_id = {reply["id"]: reply for reply in replies}
    roots_by_review: dict[int, list[dict]] = {review_id: [] for review_id in review_ids}

    for reply in replies:
        reply["replies"] = []
    for reply in replies:
        parent = replies_by_id.get(reply.get("parent_reply_id"))
        if parent and parent["review_id"] == reply["review_id"]:
            parent["replies"].append(reply)
        else:
            roots_by_review.setdefault(reply["review_id"], []).append(reply)

    for row in rows:
        row["replies"] = roots_by_review.get(row["id"], [])
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
    rows = _attach_replies(rows, client)
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


@router.post("/{novel_id}/reviews/{review_id}/replies", status_code=201)
def create_review_reply(
    novel_id: int,
    review_id: int,
    payload: ReviewReplyCreate,
    auth=Depends(get_current_user),
):
    """Add a reply to a review or to a reply already on that review."""
    user_id, client = auth
    service_client = create_service_client()
    try:
        review_response = (
            service_client.table("reviews")
            .select("id")
            .eq("id", review_id)
            .eq("novel_id", novel_id)
            .maybe_single()
            .execute()
        )
        if not review_response.data:
            raise HTTPException(status_code=404, detail="Review not found for this novel.")

        if payload.parent_reply_id is not None:
            parent_response = (
                service_client.table("review_replies")
                .select("id")
                .eq("id", payload.parent_reply_id)
                .eq("review_id", review_id)
                .maybe_single()
                .execute()
            )
            if not parent_response.data:
                raise HTTPException(status_code=404, detail="The reply you selected no longer exists.")

        response = (
            client.table("review_replies")
            .insert(
                {
                    "review_id": review_id,
                    "parent_reply_id": payload.parent_reply_id,
                    "user_id": user_id,
                    "comment": payload.comment,
                }
            )
            .execute()
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    if not response.data:
        raise HTTPException(status_code=500, detail="Reply could not be saved.")
    return response.data[0]
