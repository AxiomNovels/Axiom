from fastapi import APIRouter, HTTPException

from core.database import supabase


router = APIRouter(prefix="/api/novels", tags=["novels"])

# The list endpoint deliberately omits the larger profile payloads.
NOVEL_LIST_COLUMNS = "id, title, author, cover_image_url, synopsis, status, genres"

# The profile tables are embedded through their novel_id foreign keys.
NOVEL_DETAIL_COLUMNS = (
    "*, "
    "protagonist_profiles(*), "
    "philosophy_profiles(*), "
    "storytelling_style_profiles(*)"
)


@router.get("")
def list_novels():
    try:
        response = (
            supabase.table("novels")
            .select(NOVEL_LIST_COLUMNS)
            .order("title")
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    return response.data


@router.get("/{novel_id}")
def get_novel(novel_id: int):
    try:
        response = (
            supabase.table("novels")
            .select(NOVEL_DETAIL_COLUMNS)
            .eq("id", novel_id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Novel not found")

    return response.data
