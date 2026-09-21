from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response

from core.auth import get_current_user, get_optional_current_user
from core.database import create_service_client
from models.review import ReviewUpsert
from routes.reviews import _attach_public_profiles, _review_payload
from routes.users import _visible_list_levels


router = APIRouter(prefix="/api/reading-lists", tags=["reading-list-reviews"])

REVIEW_COLUMNS = "id, reading_list_id, user_id, rating, comment, created_at, updated_at"


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