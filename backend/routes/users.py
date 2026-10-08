from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from routes.novels import NOVEL_LIST_COLUMNS

from core.auth import get_optional_current_user
from core.database import create_service_client
from services.reading_list_like_service import attach_like_summaries
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
    ", online_status_visibility"
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


def _is_special_account(client, user_id: str) -> bool:
    """Whether an account holds the public-facing Axiom admin badge."""
    try:
        user = client.auth.admin.get_user_by_id(user_id).user
        metadata = (user.app_metadata or {}) if user else {}
        return metadata.get("axiom_special") is True and metadata.get("axiom_banned") is not True
    except Exception:
        return False


def _online_user_ids(client, user_ids: list[str]) -> set[str]:
    if not user_ids:
        return set()
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    try:
        rows = (
            client.table("user_presence")
            .select("user_id")
            .in_("user_id", user_ids)
            .gte("last_heartbeat_at", cutoff)
            .execute()
            .data
            or []
        )
    except Exception:
        return set()
    return {str(row["user_id"]) for row in rows}


def _presence_by_user_id(client, user_ids: list[str]) -> dict[str, str]:
    """Latest check-in timestamp for each requested reader, if one exists."""
    if not user_ids:
        return {}
    try:
        rows = (
            client.table("user_presence")
            .select("user_id, last_heartbeat_at")
            .in_("user_id", user_ids)
            .execute()
            .data
            or []
        )
    except Exception:
        return {}
    return {str(row["user_id"]): row["last_heartbeat_at"] for row in rows}


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


@router.get("")
def list_public_users(
    q: str = "",
    sort: Literal["alphabetical", "last_online"] = "last_online",
    limit: int = Query(48, ge=1, le=100),
):
    """A compact, public directory of Axiom readers.

    This intentionally returns only the details needed to identify a profile;
    private account and social fields remain available only through the
    friend-aware profile endpoint below.
    """
    client = create_service_client()
    query = q.strip()
    safe_limit = limit

    try:
        request = (
            client.table("profiles")
            .select("id, username, avatar_url, about_me, country, tag_preferences, online_status_visibility")
            .order("username")
            .limit(100 if sort == "last_online" else safe_limit)
        )
        if query:
            request = request.ilike("username", f"%{query}%")
        profiles = request.execute().data or []
    except Exception:
        raise HTTPException(status_code=500, detail="Couldn't load the reader directory.")

    profile_ids = [str(profile["id"]) for profile in profiles]
    online_ids = _online_user_ids(client, profile_ids)
    last_heartbeat_by_user = _presence_by_user_id(client, profile_ids)
    users = []
    for profile in profiles:
        is_public = profile.pop("online_status_visibility", "public") == "public"
        users.append({
            **profile,
            "online": is_public and str(profile["id"]) in online_ids,
            "_public_presence": is_public,
        })

    if sort == "last_online":
        # A private reader is deliberately kept out of activity ordering, so
        # the directory cannot indirectly disclose when they were last here.
        # Stable passes preserve alphabetical order when check-ins tie.
        users.sort(key=lambda user: user.get("username", "").casefold())
        users.sort(
            key=lambda user: last_heartbeat_by_user.get(str(user["id"]), ""),
            reverse=True,
        )
        users.sort(key=lambda user: not user["_public_presence"])
        users = users[:safe_limit]
    for user in users:
        user.pop("_public_presence", None)
        # Badges do not affect ordering. Only look up accounts that will
        # actually be returned, after the activity sort and result limit.
        user["special"] = _is_special_account(client, user["id"])
    return {
        "users": users,
        "query": query,
        "sort": sort,
    }


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
    attach_like_summaries(client, lists, viewer_id)

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
    payload = {
        **rows[0],
        "owner": {"id": user_id, "username": username},
        "is_owner": viewer_id == user_id,
        "novels": [item["novels"] for item in items if item.get("novels")],
    }
    attach_like_summaries(client, [payload], viewer_id)
    return payload

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
    profile["special"] = _is_special_account(service_client, user_id)
    is_public = profile.pop("online_status_visibility", "public") == "public"
    profile["online"] = is_public and str(user_id) in _online_user_ids(service_client, [str(user_id)])

    # The raw social_* columns were only ever needed to build social_links
    # above -- drop them so the public API surface doesn't also expose the
    # visibility setting or a friends-only username by accident.
    for platform in SOCIAL_PLATFORMS:
        profile.pop(f"{platform}_username", None)
        profile.pop(f"{platform}_visibility", None)

    return profile


def _reading_list_activity(client, user_id: str, viewer_id: str | None) -> dict:
    """A reader's reviews and replies on reading lists, for the Activity page.

    Reading lists have their own visibility, so this is filtered for the person
    *viewing* the page: a review or reply is only included when the viewer can
    currently see the list it was left on (the same rule the list pages use).
    Best-effort -- a problem here must never break the novel activity feed.
    """
    empty = {
        "list_activity": [],
        "list_review_count": 0,
        "list_reply_count": 0,
        "list_average_rating": None,
    }
    try:
        reviews = (
            client.table("reading_list_reviews")
            .select("id, reading_list_id, rating, comment, created_at, updated_at")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .execute()
            .data
            or []
        )
        replies = (
            client.table("reading_list_review_replies")
            .select("id, review_id, parent_reply_id, comment, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )

        # A reply only knows its review; the review knows which list it is on.
        reply_review_ids = list({reply["review_id"] for reply in replies})
        reviews_by_id = {}
        if reply_review_ids:
            rows = (
                client.table("reading_list_reviews")
                .select("id, reading_list_id")
                .in_("id", reply_review_ids)
                .execute()
                .data
                or []
            )
            reviews_by_id = {row["id"]: row for row in rows}

        list_ids = list(
            {review["reading_list_id"] for review in reviews}
            | {review["reading_list_id"] for review in reviews_by_id.values()}
        )
        if not list_ids:
            return empty

        lists = (
            client.table("reading_lists")
            .select("id, name, user_id, visibility")
            .in_("id", list_ids)
            .execute()
            .data
            or []
        )

        levels_by_owner: dict[str, list[str]] = {}
        visible_lists: dict[str, dict] = {}
        for reading_list in lists:
            owner_id = reading_list["user_id"]
            if owner_id not in levels_by_owner:
                levels_by_owner[owner_id] = _visible_list_levels(client, viewer_id, owner_id)
            if reading_list["visibility"] in levels_by_owner[owner_id]:
                visible_lists[reading_list["id"]] = reading_list
        if not visible_lists:
            return empty

        # Reuse the profile page's helper to get each list's preview covers.
        _attach_counts_and_previews(client, list(visible_lists.values()))
        owner_ids = list({reading_list["user_id"] for reading_list in visible_lists.values()})
        usernames = {
            row["id"]: row["username"]
            for row in (
                client.table("profiles").select("id, username").in_("id", owner_ids).execute().data or []
            )
        }
        summaries = {}
        for list_id, reading_list in visible_lists.items():
            previews = reading_list.get("preview_novels") or []
            summaries[list_id] = {
                "id": list_id,
                "name": reading_list["name"],
                "owner_id": reading_list["user_id"],
                "owner_username": usernames.get(reading_list["user_id"]),
                "cover_image_url": previews[0].get("cover_image_url") if previews else None,
            }

        activity = []
        visible_reviews = [review for review in reviews if review["reading_list_id"] in summaries]
        for review in visible_reviews:
            activity.append({"type": "review", **review, "list": summaries[review["reading_list_id"]]})

        visible_reply_count = 0
        for reply in replies:
            parent_review = reviews_by_id.get(reply["review_id"])
            if not parent_review or parent_review["reading_list_id"] not in summaries:
                continue
            visible_reply_count += 1
            activity.append(
                {
                    "type": "reply",
                    **reply,
                    "reading_list_id": parent_review["reading_list_id"],
                    "updated_at": reply["created_at"],
                    "list": summaries[parent_review["reading_list_id"]],
                }
            )
        activity.sort(key=lambda item: item["updated_at"], reverse=True)

        ratings = [float(review["rating"]) for review in visible_reviews]
        return {
            "list_activity": activity,
            "list_review_count": len(visible_reviews),
            "list_reply_count": visible_reply_count,
            "list_average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        }
    except Exception as error:
        print(f"[activity] failed to load reading-list activity for {user_id}: {error}")
        return empty


@router.get("/{user_id}/activity")
def get_public_activity(user_id: str, auth=Depends(get_optional_current_user)):
    """Return a reader's public review and reply history, newest first.

    Novel activity is public. Reading-list activity is filtered by who is
    viewing, so the viewer is resolved (optionally) from the bearer token.
    """
    viewer_id, _viewer_client = auth
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
        replies_response = (
            client.table("review_replies")
            .select("id, review_id, parent_reply_id, comment, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        replies = replies_response.data or []
        replied_review_ids = list({reply["review_id"] for reply in replies})
        reply_reviews_by_id = {}
        if replied_review_ids:
            replied_reviews_response = (
                client.table("reviews")
                .select("id, novel_id")
                .in_("id", replied_review_ids)
                .execute()
            )
            reply_reviews_by_id = {
                review["id"]: review for review in (replied_reviews_response.data or [])
            }

        novel_ids = list(
            {review["novel_id"] for review in reviews}
            | {review["novel_id"] for review in reply_reviews_by_id.values()}
        )
        novels_by_id = {}
        if novel_ids:
            novels_response = (
                client.table("novels")
                .select("id, title, author, cover_image_url")
                .in_("id", novel_ids)
                .execute()
            )
            novels_by_id = {novel["id"]: novel for novel in (novels_response.data or [])}
        activity = []
        for review in reviews:
            activity.append({"type": "review", **review, "novel": novels_by_id.get(review["novel_id"])})
        for reply in replies:
            parent_review = reply_reviews_by_id.get(reply["review_id"])
            if parent_review:
                activity.append(
                    {
                        "type": "reply",
                        **reply,
                        "novel_id": parent_review["novel_id"],
                        "updated_at": reply["created_at"],
                        "novel": novels_by_id.get(parent_review["novel_id"]),
                    }
                )
        activity.sort(key=lambda item: item["updated_at"], reverse=True)
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    ratings = [float(review["rating"]) for review in reviews]
    return {
        "profile": profile_response.data,
        "review_count": len(reviews),
        "reply_count": len(replies),
        "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "activity": activity,
        **_reading_list_activity(client, user_id, viewer_id),
    }
