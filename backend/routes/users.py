from fastapi import APIRouter, HTTPException

from core.database import create_service_client


router = APIRouter(prefix="/api/users", tags=["users"])

# Only the fields meant for other users to see. Deliberately excludes
# anything account-related (no email, no id beyond what's needed to route
# the request) -- this endpoint is public and unauthenticated by design.
PUBLIC_PROFILE_COLUMNS = "username, avatar_url, gender, city, country, about_me, tag_preferences"


@router.get("/{user_id}")
def get_public_profile(user_id: str):
    try:
        response = (
            create_service_client()
            .table("profiles")
            .select(PUBLIC_PROFILE_COLUMNS)
            .eq("id", user_id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="User not found.")

    if not response.data:
        raise HTTPException(status_code=404, detail="User not found.")

    return response.data


@router.get("/{user_id}/activity")
def get_public_activity(user_id: str):
    """Return a reader's public review history, newest activity first."""
    client = create_service_client()
    try:
        profile_response = (
            client.table("profiles")
            .select("id, username, avatar_url, created_at")
            .eq("id", user_id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="User not found.")

    try:
        reviews_response = (
            client.table("reviews")
            .select("id, novel_id, rating, comment, created_at, updated_at")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .execute()
        )
        reviews = reviews_response.data or []
        novel_ids = list({review["novel_id"] for review in reviews})
        novels_by_id = {}
        if novel_ids:
            novels_response = (
                client.table("novels")
                .select("id, title, author, cover_image_url")
                .in_("id", novel_ids)
                .execute()
            )
            novels_by_id = {novel["id"]: novel for novel in (novels_response.data or [])}
        for review in reviews:
            review["novel"] = novels_by_id.get(review["novel_id"])
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    ratings = [float(review["rating"]) for review in reviews]
    return {
        "profile": profile_response.data,
        "review_count": len(reviews),
        "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "activity": reviews,
    }
