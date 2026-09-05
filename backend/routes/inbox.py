from fastapi import APIRouter, Depends, HTTPException

from core.auth import get_current_user
from models.notification import NotificationUpdate


router = APIRouter(prefix="/api/inbox", tags=["inbox"])

NOTIFICATION_COLUMNS = "id, subject, body, is_read, created_at"


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

    return response.data or []


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