from fastapi import APIRouter, Depends, HTTPException

from core.auth import get_current_user
from core.database import supabase
from models.profile import ProfileUpdate


router = APIRouter(prefix="/api/profile", tags=["profile"])

PROFILE_COLUMNS = "id, username, created_at, gender, city, country, about_me, tag_preferences"


@router.get("")
def get_my_profile(auth=Depends(get_current_user)):
    user_id, client = auth
    try:
        response = (
            client.table("profiles")
            .select(PROFILE_COLUMNS)
            .eq("id", user_id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Profile not found.")

    return response.data


@router.patch("")
def update_my_profile(payload: ProfileUpdate, auth=Depends(get_current_user)):
    user_id, client = auth
    try:
        response = (
            client.table("profiles")
            .update(
                {
                    "gender": payload.gender,
                    "city": payload.city,
                    "country": payload.country,
                    "about_me": payload.about_me,
                    "tag_preferences": payload.tag_preferences,
                }
            )
            .eq("id", user_id)
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    if not response.data:
        raise HTTPException(status_code=404, detail="Profile not found.")

    return response.data[0]