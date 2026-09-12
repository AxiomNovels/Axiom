from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from services.recommendation_service import recommend_novels
from core.auth import get_current_user
from core.database import create_service_client, supabase
from scraper.royalroad import scrape_royalroad
from scraper.transform import transform_royalroad, transform_wattpad, transform_webnovel
from scraper.wattpad import scrape_wattpad
from scraper.webnovel import scrape_webnovel


router = APIRouter(prefix="/api/novels", tags=["novels"])

# The list endpoint deliberately omits the larger profile payloads.
NOVEL_LIST_COLUMNS = "id, title, author, cover_image_url, synopsis, status, genres, chapter_count, view_count"

# The profile tables are embedded through their novel_id foreign keys.
NOVEL_DETAIL_COLUMNS = (
    "*, "
    "protagonist_profiles(*), "
    "philosophy_profiles(*), "
    "storytelling_style_profiles(*)"
)

# Maps the exact dropdown labels the frontend sends to the scraper/transform
# pair that already knows how to handle that source.
SOURCE_HANDLERS = {
    "Royal Road": (scrape_royalroad, transform_royalroad),
    "WebNovel": (scrape_webnovel, transform_webnovel),
    "Wattpad": (scrape_wattpad, transform_wattpad),
}

INVALID_SOURCE_MESSAGE = "URL is invalid or source is incorrect."


class NovelSourceRequest(BaseModel):
    url: str = Field(min_length=1)
    source: str


def _scrape_and_transform(payload: NovelSourceRequest) -> dict:
    """Run the matching scraper + transformer for a user-submitted URL.

    Any failure -- an unrecognized source, a URL from the wrong site, a
    dead link, or a page the parser can't make sense of -- collapses to
    the same user-facing message, since none of those are meaningfully
    distinguishable to someone pasting a link into the form.
    """
    handler = SOURCE_HANDLERS.get(payload.source)
    url = payload.url.strip()

    if not handler or not url:
        raise HTTPException(status_code=422, detail=INVALID_SOURCE_MESSAGE)

    scrape_fn, transform_fn = handler

    try:
        raw_payload = scrape_fn(url)
        novel = transform_fn(raw_payload)
    except Exception:
        raise HTTPException(status_code=422, detail=INVALID_SOURCE_MESSAGE)

    return novel


def _record_upload(client, user_id: str, novel_id: int) -> None:
    """Append novel_id to the uploading user's profiles.novels_uploaded.

    Best-effort: if this bookkeeping update fails for some reason, the
    novel itself has already been published successfully, so we don't
    fail the whole request over it.
    """
    try:
        profile_response = (
            client.table("profiles")
            .select("novels_uploaded")
            .eq("id", user_id)
            .single()
            .execute()
        )
        current_ids = (profile_response.data or {}).get("novels_uploaded") or []
        if novel_id not in current_ids:
            client.table("profiles").update(
                {"novels_uploaded": current_ids + [novel_id]}
            ).eq("id", user_id).execute()
    except Exception:
        pass


@router.get("/featured")
def get_featured_novels():
    try:
        response = (
            supabase.rpc(
                "get_featured_novels",
                {"result_limit": 10}
            )
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    return response.data

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


@router.get("/mine")
def list_my_novels(auth=Depends(get_current_user)):
    """Novels the current user has personally uploaded, for the upload
    form's "Your uploaded novels" list."""
    user_id, client = auth
    try:
        profile_response = (
            client.table("profiles")
            .select("novels_uploaded")
            .eq("id", user_id)
            .single()
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    novel_ids = (profile_response.data or {}).get("novels_uploaded") or []
    if not novel_ids:
        return []

    try:
        novels_response = (
            supabase.table("novels")
            .select("id, title")
            .in_("id", novel_ids)
            .order("title")
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    return novels_response.data or []


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


@router.get("/{novel_id}/similar")
def get_similar_novels(novel_id: int):
    source = get_novel(novel_id)
    if not source:
        raise HTTPException(status_code=404, detail="Novel not found")
    columns = (
        "id, title, author, cover_image_url, genres, "
        "protagonist_profiles(*), philosophy_profiles(*), storytelling_style_profiles(*)"
    )
    candidates = []
    try:
        # Explicit pages avoid silently limiting recommendations to the first
        # Supabase response page. Stable ID order keeps page boundaries intact.
        offset = 0
        while True:
            page = (supabase.table("novels").select(columns)
                    .neq("id", novel_id).order("id")
                    .range(offset, offset + 499).execute().data or [])
            candidates.extend(page)
            if len(page) < 500:
                break
            offset += 500
    except Exception as error:
        raise HTTPException(status_code=500, detail="Recommendations are temporarily unavailable") from error
    return recommend_novels(source, candidates)


@router.post("/scrape")
def preview_novel(payload: NovelSourceRequest, auth=Depends(get_current_user)):
    """Scrape a user-submitted URL and return normalized fields for review.

    This is read-only -- nothing is written to the database here.
    """
    return _scrape_and_transform(payload)


@router.post("", status_code=201)
def add_novel(payload: NovelSourceRequest, auth=Depends(get_current_user)):
    """Scrape, de-duplicate, and publish a novel a user has submitted.

    The URL is re-scraped here rather than trusting whatever the client
    displayed from /scrape, so the record that gets saved always reflects
    a fresh, server-verified fetch. Duplicates are rejected using the same
    title+author check scraper/publish.py uses for the batch pipeline.
    """
    user_id, client = auth
    novel = _scrape_and_transform(payload)

    title = novel["title"]
    author = novel.get("author")

    duplicate_query = supabase.table("novels").select("id, title, author").eq("title", title)
    duplicate_query = (
        duplicate_query.is_("author", "null")
        if not author
        else duplicate_query.eq("author", author)
    )

    try:
        duplicate_response = duplicate_query.limit(1).execute()
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    existing_rows = duplicate_response.data or []
    if existing_rows:
        existing_novel = existing_rows[0]
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Novel already exists",
                "novel_id": existing_novel["id"],
                "title": existing_novel["title"],
            },
        )

    try:
        insert_response = create_service_client().table("novels").insert(novel).execute()
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    if not insert_response.data:
        raise HTTPException(status_code=500, detail="Novel could not be saved.")

    inserted_novel = insert_response.data[0]
    _record_upload(client, user_id, inserted_novel["id"])

    return inserted_novel
