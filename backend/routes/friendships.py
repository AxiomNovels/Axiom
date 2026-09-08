from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from core.auth import get_current_user
from core.database import create_service_client
from core.notifications import create_notification
from models.friendship import FriendshipRespondRequest


router = APIRouter(prefix="/api/friendships", tags=["friendships"])

# How long someone must wait before sending another request to a reader
# who rejected them. Keeps a "no" from being immediately retried into a
# spam loop. Purely a constant -- tune freely.
FRIEND_REQUEST_COOLDOWN_HOURS = 24

FRIENDSHIP_COLUMNS = "id, user_id_1, user_id_2, requested_by, status, created_at, responded_at"


def _ordered_pair(a: str, b: str) -> tuple[str, str]:
    """Friendships are always stored with the smaller id first, so (A, B)
    and (B, A) are guaranteed to be the same row rather than two."""
    return (a, b) if a < b else (b, a)


def _is_unique_violation(error: Exception) -> bool:
    message = str(error)
    return "23505" in message or "duplicate key value" in message


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _get_profile(client, user_id: str) -> dict | None:
    """Looks up a public profile row, or None if the account doesn't
    exist (including a since-deleted account) -- callers use this to
    fail gracefully instead of creating requests/notifications aimed at
    nobody."""
    try:
        response = client.table("profiles").select("id, username").eq("id", user_id).single().execute()
    except Exception:
        return None
    return response.data


def _get_friendship_row(client, friendship_id: str) -> dict | None:
    try:
        response = (
            client.table("friendships")
            .select(FRIENDSHIP_COLUMNS)
            .eq("id", friendship_id)
            .single()
            .execute()
        )
    except Exception:
        return None
    return response.data


def _latest_friendship_between(client, user_1: str, user_2: str) -> dict | None:
    try:
        response = (
            client.table("friendships")
            .select(FRIENDSHIP_COLUMNS)
            .eq("user_id_1", user_1)
            .eq("user_id_2", user_2)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
    rows = response.data or []
    return rows[0] if rows else None


@router.get("/status/{other_user_id}")
def get_friendship_status(other_user_id: str, auth=Depends(get_current_user)):
    """The relationship between the caller and other_user_id, from the
    caller's point of view -- drives the Add friend / Request sent /
    Friends button on the profile page. Computed fresh from the database
    on every call; the frontend never decides this state on its own.
    """
    user_id, client = auth

    if user_id == other_user_id:
        return {"status": "self"}

    user_1, user_2 = _ordered_pair(user_id, other_user_id)
    row = _latest_friendship_between(client, user_1, user_2)

    if not row:
        return {"status": "none"}
    if row["status"] == "accepted":
        return {"status": "friends", "friendship_id": row["id"]}
    if row["status"] == "pending":
        direction = "outgoing" if row["requested_by"] == user_id else "incoming"
        return {"status": "pending", "direction": direction, "friendship_id": row["id"]}

    # Most recent record is a rejected request. As far as the profile
    # button is concerned that's the same as never having asked -- the
    # cooldown itself is only enforced when a *new* request is sent.
    return {"status": "none"}


@router.get("/incoming-count")
def get_incoming_request_count(auth=Depends(get_current_user)):
    """Lightweight count used to badge the account avatar and the
    "Friends" dropdown link with the number of *incoming* pending
    requests -- i.e. requests waiting on this user to accept or reject,
    not ones they've sent themselves. Deliberately separate from the
    fuller GET "" response so every page load (which calls this via
    script.js) doesn't need to pull full profile data for every friend
    and pending request just to render a badge.
    """
    user_id, client = auth
    try:
        response = (
            client.table("friendships")
            .select("id, requested_by")
            .or_(f"user_id_1.eq.{user_id},user_id_2.eq.{user_id}")
            .eq("status", "pending")
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    rows = response.data or []
    incoming_count = sum(1 for row in rows if row["requested_by"] != user_id)
    return {"incoming_count": incoming_count}


@router.get("")
def list_my_friendships(auth=Depends(get_current_user)):
    """Everything needed for the "Your friends" page in one call: the
    user's accepted friends and their pending requests (both directions),
    each sorted alphabetically by username. Both lists share the same
    shape -- {"friendship_id": ..., "user": {...}} (plus "direction" for
    pending) -- so the frontend has the friendship_id it needs to power
    the Remove-friend button without a second lookup.

    Uses the RLS-scoped client for the friendships read (the same
    guarantee as get_friendship_status: a user only ever sees rows where
    they're a participant) and the service-role client only for the
    batched profile lookup, matching the public-profile pattern already
    used in routes/users.py.
    """
    user_id, client = auth

    try:
        response = (
            client.table("friendships")
            .select(FRIENDSHIP_COLUMNS)
            .or_(f"user_id_1.eq.{user_id},user_id_2.eq.{user_id}")
            .in_("status", ["accepted", "pending"])
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    rows = response.data or []
    other_ids = list({
        row["user_id_2"] if row["user_id_1"] == user_id else row["user_id_1"]
        for row in rows
    })

    profiles_by_id: dict[str, dict] = {}
    if other_ids:
        service_client = create_service_client()
        try:
            profiles_response = (
                service_client.table("profiles")
                .select("id, username, avatar_url")
                .in_("id", other_ids)
                .execute()
            )
            profiles_by_id = {profile["id"]: profile for profile in (profiles_response.data or [])}
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error))

    friends: list[dict] = []
    pending: list[dict] = []

    for row in rows:
        other_id = row["user_id_2"] if row["user_id_1"] == user_id else row["user_id_1"]
        profile = profiles_by_id.get(other_id)
        if not profile:
            # The other account no longer exists (deleted/deactivated) --
            # skip it silently rather than showing a broken entry.
            continue

        if row["status"] == "accepted":
            friends.append({"friendship_id": row["id"], "user": profile})
        elif row["status"] == "pending":
            direction = "outgoing" if row["requested_by"] == user_id else "incoming"
            pending.append({
                "friendship_id": row["id"],
                "direction": direction,
                "user": profile,
            })

    friends.sort(key=lambda entry: (entry["user"].get("username") or "").casefold())
    pending.sort(key=lambda entry: (entry["user"].get("username") or "").casefold())

    return {"friends": friends, "pending": pending}


@router.post("/{target_user_id}", status_code=201)
def send_friend_request(target_user_id: str, auth=Depends(get_current_user)):
    user_id, _client = auth

    if user_id == target_user_id:
        raise HTTPException(status_code=422, detail="You can't send a friend request to yourself.")

    service_client = create_service_client()

    target_profile = _get_profile(service_client, target_user_id)
    if not target_profile:
        raise HTTPException(status_code=404, detail="That user could not be found.")

    sender_profile = _get_profile(service_client, user_id)
    sender_username = (sender_profile or {}).get("username") or "A reader"

    user_1, user_2 = _ordered_pair(user_id, target_user_id)
    existing = _latest_friendship_between(service_client, user_1, user_2)

    if existing and existing["status"] == "accepted":
        raise HTTPException(status_code=409, detail="You're already friends with this reader.")

    if existing and existing["status"] == "pending":
        if existing["requested_by"] == user_id:
            raise HTTPException(status_code=409, detail="You've already sent a request to this reader.")

        # Mutual interest: they had already sent *us* a request. Treat
        # this as acceptance instead of blocking a legitimate action, or
        # creating a second, conflicting row for the same pair.
        try:
            accept_response = (
                service_client.table("friendships")
                .update({"status": "accepted", "responded_at": datetime.now(timezone.utc).isoformat()})
                .eq("id", existing["id"])
                .eq("status", "pending")
                .execute()
            )
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error))

        if not accept_response.data:
            # Resolved by someone else in the instant between our read
            # and this write -- ask the caller to retry rather than
            # guessing at the outcome.
            raise HTTPException(status_code=409, detail="This request just changed. Please try again.")

        return {"status": "friends", "friendship_id": existing["id"]}

    if existing and existing["status"] == "rejected" and existing.get("responded_at"):
        responded_at = _parse_timestamp(existing["responded_at"])
        cooldown_ends = responded_at + timedelta(hours=FRIEND_REQUEST_COOLDOWN_HOURS)
        now = datetime.now(timezone.utc)
        if now < cooldown_ends:
            hours_left = max(1, int((cooldown_ends - now).total_seconds() // 3600) + 1)
            raise HTTPException(
                status_code=429,
                detail=f"You can send this reader another request in about {hours_left} hour(s).",
            )

    # If the most recent row is "removed" (a former friendship that was
    # ended via remove_friend), none of the branches above apply, and
    # execution falls through to here -- a fresh request is created
    # immediately, with no cooldown, exactly as if they'd never been
    # friends.
    try:
        insert_response = (
            service_client.table("friendships")
            .insert(
                {
                    "user_id_1": user_1,
                    "user_id_2": user_2,
                    "requested_by": user_id,
                    "status": "pending",
                }
            )
            .execute()
        )
    except Exception as error:
        # The partial unique index is the final backstop against a
        # concurrent duplicate slipping past the checks above (e.g. two
        # rapid clicks, or two requests racing each other).
        if _is_unique_violation(error):
            raise HTTPException(
                status_code=409,
                detail="A friend request or friendship already exists between you two.",
            )
        raise HTTPException(status_code=500, detail=str(error))

    if not insert_response.data:
        raise HTTPException(status_code=500, detail="Couldn't send the friend request.")

    friendship = insert_response.data[0]

    create_notification(
        target_user_id,
        f"{sender_username} wants to be friends!",
        f"{sender_username} wants to be friends! Accept their request to connect.",
        notif_type="friend_request",
        data={
            "friendship_id": friendship["id"],
            "sender_id": user_id,
            "sender_username": sender_username,
        },
    )

    return {"status": "pending", "direction": "outgoing", "friendship_id": friendship["id"]}


@router.post("/{friendship_id}/respond")
def respond_to_friend_request(
    friendship_id: str,
    payload: FriendshipRespondRequest,
    auth=Depends(get_current_user),
):
    user_id, _client = auth
    service_client = create_service_client()

    row = _get_friendship_row(service_client, friendship_id)
    if not row:
        raise HTTPException(status_code=404, detail="This friend request no longer exists.")

    if user_id not in (row["user_id_1"], row["user_id_2"]):
        raise HTTPException(status_code=403, detail="You don't have permission to respond to this request.")

    if row["requested_by"] == user_id:
        raise HTTPException(status_code=403, detail="You can't respond to your own request.")

    if row["status"] != "pending":
        raise HTTPException(status_code=409, detail="This request has already been responded to.")

    new_status = "accepted" if payload.action == "accept" else "rejected"

    try:
        update_response = (
            service_client.table("friendships")
            .update({"status": new_status, "responded_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", friendship_id)
            .eq("status", "pending")
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    if not update_response.data:
        # A concurrent responder (a double-click, two open tabs, etc.)
        # already changed the status between our read above and this
        # write. This atomic conditional update is what guarantees only
        # one of two simultaneous accept/reject actions actually wins.
        raise HTTPException(status_code=409, detail="This request has already been responded to.")

    return update_response.data[0]


@router.delete("/{friendship_id}")
def remove_friend(friendship_id: str, auth=Depends(get_current_user)):
    """Unfriend someone. Either participant of an accepted friendship can
    do this to the other -- there is no notification, no confirmation
    needed from the other side, and no cooldown afterward (see
    database/friend_removal.sql). The only way the other person finds
    out is by noticing the friendship is gone from their own list.
    """
    user_id, _client = auth
    service_client = create_service_client()

    row = _get_friendship_row(service_client, friendship_id)
    if not row:
        raise HTTPException(status_code=404, detail="This friendship no longer exists.")

    if user_id not in (row["user_id_1"], row["user_id_2"]):
        raise HTTPException(status_code=403, detail="You don't have permission to remove this friendship.")

    if row["status"] == "removed":
        # Already removed -- by the other participant, or a duplicate
        # click from this same user. The desired end state (not being
        # friends) already holds, so this is a success, not an error.
        return {"status": "none"}

    if row["status"] != "accepted":
        raise HTTPException(status_code=409, detail="You're not currently friends with this reader.")

    try:
        update_response = (
            service_client.table("friendships")
            .update({"status": "removed", "responded_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", friendship_id)
            .eq("status", "accepted")
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    if not update_response.data:
        # The other participant (or a second click) removed the
        # friendship in the instant between our read above and this
        # write -- again, the desired end state already holds.
        return {"status": "none"}

    return {"status": "none"}