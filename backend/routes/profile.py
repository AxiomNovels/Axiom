import base64
import binascii
import time

from fastapi import APIRouter, Depends, HTTPException

from core.auth import get_current_user
from core.config import SUPABASE_URL
from core.database import create_service_client
from models.profile import AvatarUpdate, ProfileUpdate


router = APIRouter(prefix="/api/profile", tags=["profile"])

PROFILE_COLUMNS = (
    "id, username, created_at, gender, city, country, about_me, tag_preferences, avatar_url, "
    "discord_username, discord_visibility, "
    "instagram_username, instagram_visibility, "
    "reddit_username, reddit_visibility, "
    "tiktok_username, tiktok_visibility"
)

AVATAR_BUCKET = "avatars"
MAX_AVATAR_BYTES = 5 * 1024 * 1024  # 5 MB -- generous, since the exported avatar is always a small, fixed-size image


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
                    "discord_username": payload.discord_username,
                    "discord_visibility": payload.discord_visibility,
                    "instagram_username": payload.instagram_username,
                    "instagram_visibility": payload.instagram_visibility,
                    "reddit_username": payload.reddit_username,
                    "reddit_visibility": payload.reddit_visibility,
                    "tiktok_username": payload.tiktok_username,
                    "tiktok_visibility": payload.tiktok_visibility,
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


@router.post("/avatar")
def update_my_avatar(payload: AvatarUpdate, auth=Depends(get_current_user)):
    """Save a cropped avatar image sent as a base64 data URL.

    Storage is written using the service-role client (the same privileged
    pattern routes/novels.py uses for publishing), bypassing the need for
    separate storage permission rules. This is safe here because
    get_current_user has already confirmed who is calling, and the upload
    path is always exactly that person's own user id -- so a user can
    only ever overwrite their own avatar file, never anyone else's.
    """
    user_id, client = auth

    header, _, encoded = payload.image_data.partition(",")
    if not encoded or "base64" not in header:
        raise HTTPException(status_code=422, detail="Avatar image data is invalid.")

    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="Avatar image data is invalid.")

    if not image_bytes:
        raise HTTPException(status_code=422, detail="Avatar image data is invalid.")
    if len(image_bytes) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=413, detail="Avatar image is too large.")

    storage_path = f"{user_id}.png"

    try:
        create_service_client().storage.from_(AVATAR_BUCKET).upload(
            path=storage_path,
            file=image_bytes,
            file_options={"content-type": "image/png", "upsert": "true"},
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Couldn't upload avatar: {error}")

    # Built manually rather than via a storage client helper method, since
    # that method's return shape differs across supabase-py versions --
    # Supabase's public object URL format itself is stable. The "updated"
    # query parameter forces browsers to fetch the new image instead of a
    # cached copy at this same path from before.
    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{AVATAR_BUCKET}/{storage_path}?updated={int(time.time())}"

    try:
        response = (
            client.table("profiles")
            .update({"avatar_url": public_url})
            .eq("id", user_id)
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    if not response.data:
        raise HTTPException(status_code=404, detail="Profile not found.")

    return response.data[0]