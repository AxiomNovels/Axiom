from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from core.auth import get_current_user
from core.database import create_service_client


router = APIRouter(prefix="/api/presence", tags=["presence"])


@router.post("/heartbeat")
def heartbeat(auth=Depends(get_current_user)):
    """Record one lightweight check-in for a visible, logged-in browser tab."""
    user_id, _ = auth
    try:
        create_service_client().table("user_presence").upsert(
            {
                "user_id": str(user_id),
                "last_heartbeat_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="user_id",
        ).execute()
    except Exception as error:
        raise HTTPException(status_code=500, detail="Couldn't update presence.") from error

    return {"recorded": True}
