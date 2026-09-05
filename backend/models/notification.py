from pydantic import BaseModel


class NotificationUpdate(BaseModel):
    """Body for PATCH /api/inbox/{id} -- the only mutation users can make
    to a notification is toggling whether they've read it."""

    is_read: bool