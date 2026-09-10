from fastapi import APIRouter, Depends, HTTPException

from core.auth import get_current_user
from core.database import create_service_client


router = APIRouter(prefix="/api/reviews", tags=["review-likes"])


def _is_unique_violation(error: Exception) -> bool:
    message = str(error)
    return "23505" in message or "duplicate key value" in message


def _get_review(client, review_id: int) -> dict | None:
    try:
        response = (
            client.table("reviews")
            .select("id, user_id")
            .eq("id", review_id)
            .single()
            .execute()
        )
    except Exception:
        return None
    return response.data


def _count_likes(client, review_id: int) -> int:
    try:
        response = client.table("review_likes").select("id").eq("review_id", review_id).execute()
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
    return len(response.data or [])


@router.post("/{review_id}/like", status_code=201)
def like_review(review_id: int, auth=Depends(get_current_user)):
    """Like a review. Liking your own review is rejected; liking a review
    you've already liked is a no-op rather than an error, so a
    double-click or retried request can't fail.
    """
    user_id, _client = auth
    service_client = create_service_client()

    review = _get_review(service_client, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")

    if review["user_id"] == user_id:
        raise HTTPException(status_code=403, detail="You can't like your own review.")

    try:
        service_client.table("review_likes").insert(
            {"review_id": review_id, "user_id": user_id}
        ).execute()
    except Exception as error:
        if not _is_unique_violation(error):
            raise HTTPException(status_code=500, detail=str(error))
        # Already liked -- treat as success.

    return {"liked": True, "like_count": _count_likes(service_client, review_id)}


@router.delete("/{review_id}/like")
def unlike_review(review_id: int, auth=Depends(get_current_user)):
    """Withdraw a like. Removing a like that doesn't exist is also a
    no-op, for the same idempotency reason as like_review above.
    """
    user_id, _client = auth
    service_client = create_service_client()

    try:
        (
            service_client.table("review_likes")
            .delete()
            .eq("review_id", review_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    return {"liked": False, "like_count": _count_likes(service_client, review_id)}