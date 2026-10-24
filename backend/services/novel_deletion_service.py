"""Atomic catalogue removal and Inbox delivery through a service-only RPC."""
import logging

from fastapi import HTTPException


logger = logging.getLogger(__name__)


def delete_novel(client, novel_id: int, actor_id: str) -> dict:
    try:
        return client.rpc("delete_novel", {
            "p_novel_id": novel_id, "p_actor_id": str(actor_id),
        }).execute().data
    except Exception as error:
        code = getattr(error, "code", None)
        if code == "P0002":
            raise HTTPException(404, "Novel not found. It may already have been deleted.") from error
        if code == "42501":
            raise HTTPException(403, "Novel deletion requires an active SPECIAL account.") from error
        if code == "PGRST202":
            raise HTTPException(503, "Novel deletion is not set up yet. Apply database/delete_novel.sql in Supabase.") from error
        logger.exception("Couldn't delete novel %s", novel_id)
        raise HTTPException(500, "The novel could not be deleted. Please try again.") from error
