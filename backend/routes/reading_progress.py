from fastapi import APIRouter, Depends, HTTPException

from core.auth import get_current_user
from models.reading_progress import ReadingProgressUpdate


router = APIRouter(prefix="/api/reading-progress", tags=["reading-progress"])


def _is_in_any_reading_list(client, user_id: str, novel_id: int) -> bool:
    """Chapter tracking is only ever shown/editable while the novel is
    currently in one of the user's reading lists. Progress rows may still
    exist for novels no longer on any list (retained, not deleted), but
    those are intentionally invisible until the novel is added again.
    """
    try:
        response = (
            client.table("reading_list_novels")
            .select("novel_id")
            .eq("novel_id", novel_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    return bool(response.data)


@router.get("/{novel_id}")
def get_reading_progress(novel_id: int, auth=Depends(get_current_user)):
    """Return the current chapter for this novel, if it's on one of the
    user's reading lists. Returns null if the novel isn't currently on any
    list (even if progress happens to be retained behind the scenes).
    """
    user_id, client = auth
    if not _is_in_any_reading_list(client, user_id, novel_id):
        return None

    try:
        response = (
            client.table("reading_progress")
            .select("current_chapter, updated_at")
            .eq("user_id", user_id)
            .eq("novel_id", novel_id)
            .limit(1)
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    rows = response.data or []
    if rows:
        return rows[0]

    # Defensive fallback: the ensure_reading_progress DB trigger should
    # have already created this row when the novel was added to a list,
    # but if it somehow hasn't, chapter 1 is the correct default to show.
    return {"current_chapter": 1, "updated_at": None}


@router.put("/{novel_id}")
def update_reading_progress(
    novel_id: int,
    payload: ReadingProgressUpdate,
    auth=Depends(get_current_user),
):
    """Manually set the current chapter for a novel on one of the user's
    reading lists. Upserts so this stays correct even if the defaulting
    trigger hasn't run yet for some reason.
    """
    user_id, client = auth
    if not _is_in_any_reading_list(client, user_id, novel_id):
        raise HTTPException(
            status_code=404,
            detail="Add this novel to a reading list before tracking its chapter.",
        )

    try:
        response = (
            client.table("reading_progress")
            .upsert(
                {
                    "user_id": user_id,
                    "novel_id": novel_id,
                    "current_chapter": payload.current_chapter,
                },
                on_conflict="user_id,novel_id",
            )
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    if not response.data:
        raise HTTPException(status_code=500, detail="Couldn't save your chapter progress.")

    return response.data[0]