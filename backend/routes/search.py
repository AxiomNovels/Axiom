from fastapi import APIRouter, HTTPException

from routes.novels import NOVEL_LIST_COLUMNS
from core.database import supabase
from services.search_service import rank_novels


router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
def search_novels(q: str = ""):
    query = q.strip()
    if not query:
        return []

    try:
        response = (
            supabase.table("novels")
            .select(NOVEL_LIST_COLUMNS)
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    return rank_novels(response.data or [], query)
