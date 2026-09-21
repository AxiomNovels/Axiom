from fastapi import APIRouter, Depends, HTTPException
from routes.novels import NOVEL_LIST_COLUMNS

from core.auth import get_optional_current_user
from core.database import create_service_client
from services.reading_list_review_service import attach_rating_summaries


router = APIRouter(prefix="/api/users", tags=["users"])

# Only the fields meant for other users to see. Deliberately excludes
# anything account-related (no email, no id beyond what's needed to route
# the request) -- this endpoint is public by design, viewable whether or
# not the caller is logged in. The raw social_* columns are fetched here
# too, but never returned as-is -- _build_social_links() converts them
# into the friend-aware "social_links" object below before the response
# goes out.
PUBLIC_PROFILE_COLUMNS = (
    "username, avatar_url, gender, city, country, about_me, tag_preferences, "
    "discord_username, discord_visibility, "
    "instagram_username, instagram_visibility, "
    "reddit_username, reddit_visibility, "
    "tiktok_username, tiktok_visibility"
)

SOCIAL_PLATFORMS = ("discord", "instagram", "reddit", "tiktok")


def _ordered_pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def _are_friends(client, user_a: str, user_b: str) -> bool:
    user_1, user_2 = _ordered_pair(user_a, user_b)
    try:
        response = (
            client.table("friendships")
            .select("id")
            .eq("user_id_1", user_1)
            .eq("user_id_2", user_2)
            .eq("status", "accepted")
            .limit(1)
            .execute()
        )
    except Exception:
        # If the check itself fails for some reason, fail closed --
        # treat the viewer as not a friend rather than risk leaking a
        # friends-only field.
        return False
    return bool(response.data)


def _build_social_links(profile: dict, can_see_friends_only: bool) -> dict:
    """Turns the raw discord_username/discord_visibility (etc.) columns
    into a per-platform object the frontend can render directly, without
    ever exposing a friends-only username to a viewer who isn't a friend
    (or the owner) of the profile.

    Each entry is one of:
      - {"state": "unset", "username": None}          -- field left blank
      - {"state": "visible", "username": "<value>"}   -- shown to this viewer
      - {"state": "hidden", "username": None}         -- set, but restricted
    """
    links = {}
    for platform in SOCIAL_PLATFORMS:
        username = (profile.get(f"{platform}_username") or "").strip()
        visibility = profile.get(f"{platform}_visibility") or "friends_only"

        if not username:
            links[platform] = {"state": "unset", "username": None}
            continue

        is_visible_to_viewer = visibility == "everyone" or can_see_friends_only
        if is_visible_to_viewer:
            links[platform] = {"state": "visible", "username": username}
        else:
            links[platform] = {"state": "hidden", "username": None}

    return links

def _visible_list_levels(client, viewer_id: str | None, owner_id: str) -> list[str]:
    """Which reading-list visibility levels this viewer may see."""
    if viewer_id and viewer_id == owner_id:
        return ["private", "friends", "public"]
    if viewer_id and _are_friends(client, viewer_id, owner_id):
        return ["friends", "public"]
    return ["public"]


def _get_owner_username(client, user_id: str) -> str:
    try:
        response = (
            client.table("profiles").select("username").eq("id", user_id).single().execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="User not found.")
    if not response.data:
        raise HTTPException(status_code=404, detail="User not found.")
    return response.data["username"]


def _attach_counts_and_previews(client, lists: list[dict]) -> list[dict]:
    if not lists:
        return lists

    list_ids = [reading_list["id"] for reading_list in lists]
    try:
        memberships = (
            client.table("reading_list_novels")
            .select("reading_list_id, novel_id, added_at")
            .in_("reading_list_id", list_ids)
            .order("added_at", desc=True)
            .execute()
            .data
            or []
        )
        novel_ids = list(dict.fromkeys(row["novel_id"] for row in memberships))
        novels_by_id = {}
        if novel_ids:
            novels = (
                client.table("novels")
                .select("id, title, cover_image_url")
                .in_("id", novel_ids)
                .execute()
                .data
                or []
            )
            novels_by_id = {novel["id"]: novel for novel in novels}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    counts: dict = {}
    previews: dict = {}
    for row in memberships:
        list_id = row["reading_list_id"]
        counts[list_id] = counts.get(list_id, 0) + 1
        novel = novels_by_id.get(row["novel_id"])
        if novel and len(previews.setdefault(list_id, [])) < 3:
            previews[list_id].append(novel)

    for reading_list in lists:
        reading_list["novel_count"] = counts.get(reading_list["id"], 0)
        reading_list["preview_novels"] = previews.get(reading_list["id"], [])
    return lists


@router.get("/{user_id}/reading-lists")
def get_user_reading_lists(user_id: str, auth=Depends(get_optional_current_user)):
    """Reading lists of `user_id` that the current viewer is allowed to see."""
    viewer_id, _client = auth
    client = create_service_client()

    username = _get_owner_username(client, user_id)
    levels = _visible_list_levels(client, viewer_id, user_id)

    try:
        lists = (
            client.table("reading_lists")
            .select("id, name, created_at, visibility")
            .eq("user_id", user_id)
            .in_("visibility", levels)
            .order("created_at")
            .execute()
            .data
            or []
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    lists = _attach_counts_and_previews(client, lists)
    attach_rating_summaries(client, lists)

    return {
        "username": username,
        "is_owner": viewer_id == user_id,
        "lists": lists,
    }


@router.get("/{user_id}/reading-lists/{list_id}")
def get_user_reading_list(
    user_id: str, list_id: str, auth=Depends(get_optional_current_user)
):
    """One reading list, read-only. Returns 404 (not 403) when the viewer
    lacks permission, so the existence of private lists isn't revealed."""
    viewer_id, _client = auth
    client = create_service_client()

    username = _get_owner_username(client, user_id)
    levels = _visible_list_levels(client, viewer_id, user_id)

    try:
        rows = (
            client.table("reading_lists")
            .select("id, name, visibility")
            .eq("id", list_id)
            .eq("user_id", user_id)
            .in_("visibility", levels)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception:
        rows = []
    if not rows:
        raise HTTPException(status_code=404, detail="Reading list not found.")

    try:
        items = (
            client.table("reading_list_novels")
            .select(f"added_at, novels({NOVEL_LIST_COLUMNS})")
            .eq("reading_list_id", list_id)
            .order("added_at", desc=True)
            .execute()
            .data
            or []
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    # Deliberately no current_chapter here: reading progress stays private.
    return {
        **rows[0],
        "owner": {"id": user_id, "username": username},
        "is_owner": viewer_id == user_id,
        "novels": [item["novels"] for item in items if item.get("novels")],
    }

@router.get("/{user_id}")
def get_public_profile(user_id: str, auth=Depends(get_optional_current_user)):
    viewer_id, _client = auth
    service_client = create_service_client()

    try:
        response = (
            service_client.table("profiles")
            .select(PUBLIC_PROFILE_COLUMNS)
            .eq("id", user_id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="User not found.")

    profile = response.data
    if not profile:
        raise HTTPException(status_code=404, detail="User not found.")

    # A user always sees their own social fields in full (e.g. if they
    # navigate to their own public profile page); anyone who's actually
    # friends with the owner sees friends-only fields too. Everyone else
    # only sees fields set to "everyone".
    is_self = viewer_id == user_id
    can_see_friends_only = is_self or (
        viewer_id is not None and _are_friends(service_client, viewer_id, user_id)
    )

    profile["social_links"] = _build_social_links(profile, can_see_friends_only)

    # The raw social_* columns were only ever needed to build social_links
    # above -- drop them so the public API surface doesn't also expose the
    # visibility setting or a friends-only username by accident.
    for platform in SOCIAL_PLATFORMS:
        profile.pop(f"{platform}_username", None)
        profile.pop(f"{platform}_visibility", None)

    return profile


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
