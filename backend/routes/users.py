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