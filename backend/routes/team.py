from fastapi import APIRouter

from core.database import create_service_client


router = APIRouter(prefix="/api", tags=["team"])


@router.get("/team")
def get_team_profiles():
    """Public identity details for the co-founder credits on the Team page."""
    try:
        client = create_service_client()
        rows = (
            client
            .table("profiles")
            .select("id, username, avatar_url")
            .in_("username", ["wafflehunter", "Shadowfax"])
            .execute()
            .data
            or []
        )
        for member in rows:
            try:
                user = client.auth.admin.get_user_by_id(member["id"]).user
                metadata = (user.app_metadata or {}) if user else {}
                member["special"] = (
                    metadata.get("axiom_special") is True
                    and metadata.get("axiom_banned") is not True
                )
            except Exception:
                member["special"] = False
            member.pop("id", None)
    except Exception:
        rows = []
    return {"members": rows}
