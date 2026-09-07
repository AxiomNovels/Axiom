from typing import Literal

from pydantic import BaseModel


class FriendshipRespondRequest(BaseModel):
    """Body for POST /api/friendships/{id}/respond."""

    action: Literal["accept", "reject"]