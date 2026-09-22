from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response

from core.auth import get_current_user, get_optional_current_user
from core.database import create_service_client
from models.review import ReviewUpsert
from routes.reviews import _attach_public_profiles, _review_payload
from routes.users import _visible_list_levels


router = APIRouter(prefix="/api/reading-lists", tags=["reading-list-reviews"])

REVIEW_COLUMNS = "id, reading_list_id, user_id, rating, comment, created_at, updated_at"
LIKES_TABLE = "reading_list_review_likes"


def _is_unique_violation(error: Exception) -> bool:
    message = str(error)
    return "23505" in message or "duplicate key value" in message


def _attach_like_data(rows: list[dict], client, viewer_id: str | None) -> list[dict]:
    """Attach like_count (public) and viewer_has_liked (logged-in viewers only)
    to each list review, using one batched query instead of one per review.
    Mirrors routes.reviews._attach_like_data, but for reading_list_review_likes.
    """
    review_ids = [row["id"] for row in rows if row.get("id") is not None]
    for row in rows:
        row["like_count"] = 0
        row["viewer_has_liked"] = False
    if not review_ids:
        return rows

    try:
        like_rows = (
            client.table(LIKES_TABLE)
            .select("review_id, user_id")
            .in_("review_id", review_ids)
            .execute()
            .data
            or []
        )
    except Exception:
        # Likes are secondary to the review itself -- don't fail the whole
        # reviews request if this lookup has trouble.
        like_rows = []

    counts: dict = {}
    liked_by_viewer: set = set()
    for like in like_rows:
        counts[like["review_id"]] = counts.get(like["review_id"], 0) + 1
        if viewer_id and like["user_id"] == viewer_id:
            liked_by_viewer.add(like["review_id"])

    for row in rows:
        row["like_count"] = counts.get(row["id"], 0)
        row["viewer_has_liked"] = row["id"] in liked_by_viewer
    return rows


def _get_review_on_list(client, list_id: str, review_id: int) -> dict:
    """Fetch a review only if it belongs to this list, else 404. Stops a valid
    list id from being paired with a review that lives on a different list."""
    try:
        rows = (
            client.table("reading_list_reviews")
            .select("id, user_id")
            .eq("id", review_id)
            .eq("reading_list_id", list_id)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception:
        rows = []
    if not rows:
        raise HTTPException(status_code=404, detail="Review not found.")
    return rows[0]


def _count_likes(client, review_id: int) -> int:
    try:
        response = client.table(LIKES_TABLE).select("id").eq("review_id", review_id).execute()
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
    return len(response.data or [])


def _load_viewable_list(client, list_id: str, viewer_id: str | None) -> tuple[dict, bool]:
    """Return (list row, viewer_is_owner), or raise 404.

    This is the single gate for every read AND write below. It's evaluated
    against the list's *current* visibility on every request, which is what
    makes a reviewer lose access the moment the owner tightens the setting.
    A missing list, a malformed id, and a list the viewer can't see all
    return the same 404, so a private list's existence isn't revealed.
    """
    try:
        rows = (
            client.table("reading_lists")
            .select("id, user_id, visibility")
            .eq("id", list_id)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception:
        rows = []

    if not rows:
        raise HTTPException(status_code=404, detail="Reading list not found.")

    reading_list = rows[0]
    owner_id = reading_list["user_id"]
    if reading_list["visibility"] not in _visible_list_levels(client, viewer_id, owner_id):
        raise HTTPException(status_code=404, detail="Reading list not found.")

    return reading_list, viewer_id == owner_id


@router.get("/{list_id}/reviews")
def list_reading_list_reviews(list_id: str, auth=Depends(get_optional_current_user)):
    viewer_id, _client = auth
    client = create_service_client()
    _reading_list, is_owner = _load_viewable_list(client, list_id, viewer_id)

    try:
        response = (
            client.table("reading_list_reviews")
            .select(REVIEW_COLUMNS)
            .eq("reading_list_id", list_id)
            .order("updated_at", desc=True)
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    rows = _attach_public_profiles(response.data or [], client)
    rows = _attach_like_data(rows, client, viewer_id)
    payload = _review_payload(rows)
    payload["is_owner"] = is_owner
    return payload


@router.put("/{list_id}/reviews")
def save_reading_list_review(
    list_id: str, payload: ReviewUpsert, auth=Depends(get_current_user)
):
    user_id, _client = auth
    client = create_service_client()
    _reading_list, is_owner = _load_viewable_list(client, list_id, user_id)

    if is_owner:
        raise HTTPException(status_code=403, detail="You can't review your own reading list.")

    review = {
        "reading_list_id": list_id,
        "user_id": user_id,  # always the authenticated user, never client-supplied
        "rating": payload.rating,
        "comment": payload.comment,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        response = (
            client.table("reading_list_reviews")
            .upsert(review, on_conflict="reading_list_id,user_id")
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    if not response.data:
        raise HTTPException(status_code=500, detail="Review could not be saved.")
    return response.data[0]


@router.delete("/{list_id}/reviews", status_code=204)
def delete_reading_list_review(list_id: str, auth=Depends(get_current_user)):
    user_id, _client = auth
    client = create_service_client()
    # A reviewer who has lost access gets a 404 here and cannot delete.
    _load_viewable_list(client, list_id, user_id)

    try:
        (
            client.table("reading_list_reviews")
            .delete()
            .eq("reading_list_id", list_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
    return Response(status_code=204)


@router.post("/{list_id}/reviews/{review_id}/like", status_code=201)
def like_reading_list_review(list_id: str, review_id: int, auth=Depends(get_current_user)):
    """Like a review on a reading list.

    Gated exactly like reading and writing reviews: the viewer must be able to
    see the list right now. Liking your own review is rejected; liking a review
    you've already liked is a no-op so a double-click can't fail.
    """
    user_id, _client = auth
    client = create_service_client()
    _load_viewable_list(client, list_id, user_id)
    review = _get_review_on_list(client, list_id, review_id)

    if review["user_id"] == user_id:
        raise HTTPException(status_code=403, detail="You can't like your own review.")

    try:
        client.table(LIKES_TABLE).insert({"review_id": review_id, "user_id": user_id}).execute()
    except Exception as error:
        if not _is_unique_violation(error):
            raise HTTPException(status_code=500, detail=str(error))
        # Already liked -- treat as success.

    return {"liked": True, "like_count": _count_likes(client, review_id)}


@router.delete("/{list_id}/reviews/{review_id}/like")
def unlike_reading_list_review(list_id: str, review_id: int, auth=Depends(get_current_user)):
    """Withdraw a like. Removing a like that doesn't exist is also a no-op."""
    user_id, _client = auth
    client = create_service_client()
    # A viewer who has lost access to the list gets a 404 here as well.
    _load_viewable_list(client, list_id, user_id)
    _get_review_on_list(client, list_id, review_id)

    try:
        (
            client.table(LIKES_TABLE)
            .delete()
            .eq("review_id", review_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    return {"liked": False, "like_count": _count_likes(client, review_id)}