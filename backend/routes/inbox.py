from fastapi import APIRouter, Depends, HTTPException

from core.auth import get_current_user
from models.notification import NotificationUpdate


router = APIRouter(prefix="/api/inbox", tags=["inbox"])

NOTIFICATION_COLUMNS = "id, subject, body, type, data, is_read, created_at"


def _attach_live_friendship_status(notifications: list[dict], client) -> None:
    """friend_request notifications carry a friendship_id in their data.

    Rather than trust a status snapshot taken when the notification was
    created (which would go stale the moment the request is accepted,
    rejected, or the underlying friendship row is removed via cascade
    delete), this looks up the *current* status from the friendships
    table every time the inbox is loaded and attaches it as
    data.friendship_status. This is what lets the inbox correctly hide
    the Accept/Reject buttons once a request has already been resolved
    -- even if it was resolved from a different tab, device, or after
    the sender's account was deleted.
    """
    friendship_ids = [
        (notification.get("data") or {}).get("friendship_id")
        for notification in notifications
        if notification.get("type") == "friend_request"
    ]
    friendship_ids = [value for value in friendship_ids if value]
    if not friendship_ids:
        return

    try:
        response = (
            client.table("friendships")
            .select("id, status")
            .in_("id", friendship_ids)
            .execute()
        )
    except Exception:
        return

    status_by_id = {row["id"]: row["status"] for row in (response.data or [])}

    for notification in notifications:
        if notification.get("type") != "friend_request":
            continue
        data = dict(notification.get("data") or {})
        friendship_id = data.get("friendship_id")
        # Falls back to "not_found" when the friendship row is gone
        # entirely (e.g. the sender's account was deleted), so the
        # frontend can show a graceful "no longer available" message
        # instead of a broken Accept/Reject action.
        data["friendship_status"] = status_by_id.get(friendship_id, "not_found")
        notification["data"] = data


@router.get("")
def list_notifications(auth=Depends(get_current_user)):
    """All of the current user's notifications, newest first.

    This is a read-only inbox: there is no create/delete/reply endpoint.
    Notifications only ever originate from the system (see
    core/notifications.py).
    """
    user_id, client = auth
    try:
        response = (
            client.table("notifications")
            .select(NOTIFICATION_COLUMNS)
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    notifications = response.data or []
    _attach_live_friendship_status(notifications, client)
    return notifications


@router.get("/unread-count")
def get_unread_count(auth=Depends(get_current_user)):
    """Lightweight count used to badge the Inbox icon in the header,
    without pulling every message on every page load."""
    user_id, client = auth
    try:
        response = (
            client.table("notifications")
            .select("id")
            .eq("user_id", user_id)
            .eq("is_read", False)
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    return {"unread_count": len(response.data or [])}


@router.patch("/{notification_id}")
def update_notification(
    notification_id: str,
    payload: NotificationUpdate,
    auth=Depends(get_current_user),
):
    """Mark a single notification read or unread. This doubles as the
    "open a message" action (the frontend calls it with is_read=true
    when a message is opened) and the manual read/unread toggle."""
    user_id, client = auth
    try:
        response = (
            client.table("notifications")
            .update({"is_read": payload.is_read})
            .eq("id", notification_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    if not response.data:
        raise HTTPException(status_code=404, detail="Notification not found.")

    return response.data[0]